"""
Reuses an authenticated operator session (cookies) across plain-httpx
searches, refreshing it via Playwright only when needed.

Usage from a connector:

    cookies = await session_manager.get_valid_cookies(
        operator_id=PEGAS_OPERATOR_ID,
        login_fn=lambda: fetch_pegas_session_cookies(username, password),
    )
    # ... use cookies in an httpx.Client/AsyncClient ...
    # If a search request comes back looking unauthenticated:
    cookies = await session_manager.force_refresh(
        operator_id=PEGAS_OPERATOR_ID,
        login_fn=lambda: fetch_pegas_session_cookies(username, password),
    )

login_fn is injected by the caller (rather than hardcoded here) so this
manager stays operator-agnostic and reusable for Anex later.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operator_session import OperatorSession

logger = logging.getLogger(__name__)

LoginFn = Callable[[], Awaitable[list[dict]]]

# Safety margin: treat a session as expired this many seconds before its
# actual cookie expiry, to avoid racing a request against expiry mid-flight.
EXPIRY_SAFETY_MARGIN_SECONDS = 120


def _extract_auth_cookie_expiry(cookies: list[dict], auth_cookie_name: str) -> dt.datetime:
    """
    Finds the named auth cookie among Playwright's cookie list and converts
    its Unix-timestamp `expires` field to an aware UTC datetime.

    Falls back to "expires in 1 hour from now" if the cookie is missing an
    expiry (session cookie with no Max-Age) — better to refresh too often
    than to silently treat it as eternal.
    """
    for cookie in cookies:
        if cookie.get("name") == auth_cookie_name:
            expires = cookie.get("expires")
            if expires and expires > 0:
                return dt.datetime.fromtimestamp(expires, tz=dt.timezone.utc)
            break

    logger.warning(
        "Auth cookie %r has no usable expiry; defaulting to 1 hour TTL",
        auth_cookie_name,
    )
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)


class PlaywrightSessionManager:
    def __init__(self, db: AsyncSession, auth_cookie_name: str = ".AspNetCore.Cookies"):
        self.db = db
        self.auth_cookie_name = auth_cookie_name

    async def get_valid_cookies(self, operator_id: int, login_fn: LoginFn) -> list[dict]:
        """
        Returns cookies for operator_id, reusing a stored session if it is
        still valid (with safety margin), otherwise logging in fresh via
        login_fn and persisting the result.
        """
        result = await self.db.execute(
            select(OperatorSession).where(OperatorSession.operator_id == operator_id)
        )
        session_row = result.scalar_one_or_none()

        now = dt.datetime.now(dt.timezone.utc)
        margin = dt.timedelta(seconds=EXPIRY_SAFETY_MARGIN_SECONDS)

        if session_row is not None and session_row.expires_at > now + margin:
            return session_row.cookies

        return await self._login_and_store(operator_id, login_fn, session_row)

    async def force_refresh(self, operator_id: int, login_fn: LoginFn) -> list[dict]:
        """
        Unconditionally logs in again via login_fn and overwrites the stored
        session. Call this when a search request indicates the session was
        rejected server-side (401, redirect to login) even though our local
        expires_at said it should still be valid.
        """
        result = await self.db.execute(
            select(OperatorSession).where(OperatorSession.operator_id == operator_id)
        )
        session_row = result.scalar_one_or_none()
        return await self._login_and_store(operator_id, login_fn, session_row)

    async def _login_and_store(
        self,
        operator_id: int,
        login_fn: LoginFn,
        session_row: OperatorSession | None,
    ) -> list[dict]:
        logger.info("Logging in via Playwright for operator_id=%s", operator_id)
        cookies = await login_fn()
        expires_at = _extract_auth_cookie_expiry(cookies, self.auth_cookie_name)

        if session_row is None:
            session_row = OperatorSession(
                operator_id=operator_id,
                cookies=cookies,
                expires_at=expires_at,
            )
            self.db.add(session_row)
        else:
            session_row.cookies = cookies
            session_row.expires_at = expires_at

        await self.db.commit()
        return cookies