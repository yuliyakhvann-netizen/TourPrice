"""
Direct-HTTP login for Pegas, bypassing Playwright entirely.

BACKGROUND: Pegas' login form is a Vue SPA. Despite trying eight+ distinct
Playwright input techniques (fill, keyboard.type, locator.press_sequentially,
direct JS value-setting via the native HTMLInputElement prototype setter +
dispatched input/change events, character-by-character keyboard.press with
delays, playwright-stealth) - the username/password fields remained
genuinely empty at the DOM level (confirmed via direct
document.querySelector(...).value reads, bypassing Playwright's own
input_value() API) every single time, in headless Chromium. A manual login
in a real browser works fine and was used to capture the real request shape
below. We were unable to identify the root cause (likely some
automation-detection mechanism specific to this headless environment that
playwright-stealth's evasions don't cover), and stopped guessing further
input techniques in favor of bypassing the browser UI entirely.

This module instead replays the login as a plain HTTP exchange:
1. GET the login page to obtain the ASP.NET Core antiforgery cookie
   (`.AspNetCore.Antiforgery.*`) and the matching RequestVerificationToken
   value embedded in the page's hidden <input>.
2. POST to /Account/Login with that token as a request header (NOT in the
   body - confirmed via DevTools), Username/Password as a small JSON body,
   and `X-Requested-With: XMLHttpRequest` (the server appears to require
   this AJAX marker).
3. The response sets `.AspNetCore.Cookies`, which is what authenticates
   subsequent search requests.

Captured real request (DevTools, manual login):
  POST https://kz.pegast.asia/Account/Login
  Content-Type: application/json; charset=UTF-8
  X-Requested-With: XMLHttpRequest
  RequestVerificationToken: <token from hidden input>
  Cookie: .AspNetCore.Antiforgery.<suffix>=<value>; ...
  Body: {"Username": "...", "Password": "..."}  (~45 bytes)

If Pegas changes their login flow, the Playwright-based path is still the
conceptually "right" approach long-term (it doesn't depend on guessing
internal request shapes) - this module is a pragmatic workaround for a
specific, unexplained headless-input failure, not a rejection of Playwright
in general. Revisit if this endpoint shape stops working.
"""
from __future__ import annotations

import re

import httpx

LOGIN_PAGE_URL = "https://kz.pegast.asia/Account/Login?ReturnUrl=%2FPackageSearch"
LOGIN_POST_URL = "https://kz.pegast.asia/Account/Login"

# The antiforgery token is NOT a plain <input> tag in the raw server HTML.
# It's HTML-entity-escaped inside a data-anti-forgery-html attribute, e.g.:
#   data-anti-forgery-html="&lt;input id=&quot;RequestVerificationToken&quot;
#     type=&quot;hidden&quot; value=&quot;TOKEN_HERE&quot;/&gt;"
# (confirmed via raw httpx GET — Playwright's page.content() apparently
# renders the decoded <input> tag instead, which is why earlier patterns
# based on that output didn't match the real server response.)
# Два варианта — entity-encoded (локально) и decoded (Railway/продакшен)
TOKEN_PATTERN = re.compile(
    r'RequestVerificationToken&quot;\s+type=&quot;hidden&quot;\s+'
    r'value=&quot;([^&]+)&quot;'
)
TOKEN_PATTERN_DECODED = re.compile(
    r'RequestVerificationToken["\s]+[^>]*value=["\']([^"\']+)["\']'
)


class PegasLoginError(Exception):
    """Raised when Pegas login fails or the antiforgery token cannot be found."""


async def fetch_pegas_session_cookies(username: str, password: str) -> list[dict]:
    """
    Logs into the Pegas B2B portal via a direct HTTP exchange (see module
    docstring for why this bypasses Playwright) and returns the resulting
    cookies as a list of dicts shaped like Playwright's cookie format
    (name, value, domain, path) so callers (PlaywrightSessionManager,
    PegasOperator) don't need to know which mechanism produced them.

    Raises PegasLoginError if the antiforgery token can't be parsed out of
    the login page, or if the login POST doesn't come back with an
    .AspNetCore.Cookies cookie (i.e. login was rejected — wrong credentials,
    flow changed server-side, etc).
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        page_response = await client.get(LOGIN_PAGE_URL)
        page_response.raise_for_status()

        token_match = TOKEN_PATTERN.search(page_response.text)
        if token_match is None:
            token_match = TOKEN_PATTERN_DECODED.search(page_response.text)
        if token_match is None:
            raise PegasLoginError(
                "Could not find RequestVerificationToken in the login page HTML — "
                "Pegas may have changed their login form."
            )
        verification_token = token_match.group(1)

        login_response = await client.post(
            LOGIN_POST_URL,
            json={"username": username, "password": password},
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "RequestVerificationToken": verification_token,
                "Origin": "https://kz.pegast.asia",
                "Referer": LOGIN_PAGE_URL,
            },
        )
        login_response.raise_for_status()

        auth_cookie = client.cookies.get(".AspNetCore.Cookies")
        if auth_cookie is None:
            raise PegasLoginError(
                "Login POST succeeded (HTTP "
                f"{login_response.status_code}) but no .AspNetCore.Cookies "
                "cookie was set — login was likely rejected (check credentials)."
            )

        return [
            {"name": name, "value": value, "domain": "kz.pegast.asia", "path": "/"}
            for name, value in client.cookies.items()
        ]