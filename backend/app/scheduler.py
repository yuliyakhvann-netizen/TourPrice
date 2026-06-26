"""
APScheduler-based background job runner.

Jobs:
- discovery (daily 03:00): scans all known countries for each operator,
  collects resorts/hotels into catalog tables.
- refresh (every 3 hours): re-runs live search for all active profiles,
  updates normalized_tours and comparison_results.

Both jobs are async and use their own DB sessions (not the request-scoped
ones from FastAPI deps) so they don't interfere with live API requests.
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

def _log(msg: str) -> None:
    """Print-based logging для scheduler — structlog не захватывает стандартный logging."""
    print(f"[scheduler] {msg}", flush=True)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Almaty")
    return _scheduler


async def run_discovery() -> None:
    """
    Daily discovery: collects resorts for all SAMO operators and
    re-imports Pegas catalog.
    """
    from app.database import AsyncSessionLocal
    from app.models.operator import Operator
    from sqlalchemy import select

    _log("discovery job started")

    # Kompas discovery
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Operator).where(Operator.code == "kompas"))
            op = result.scalar_one_or_none()
            if op and op.is_active:
                from app.operators.kompas.catalog_importer import discover_kompas_resorts
                totals = await discover_kompas_resorts(db, operator_id=op.id)
                logger.info("[scheduler] kompas discovery: %s", totals)
    except Exception as e:
        logger.error("[scheduler] kompas discovery FAILED: %s", e)

    # Selfie discovery — same SAMO structure, reuse kompas catalog functions
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Operator).where(Operator.code == "selfie"))
            op = result.scalar_one_or_none()
            if op and op.is_active:
                from app.operators.selfie.catalog_importer import discover_selfie_resorts
                totals = await discover_selfie_resorts(db, operator_id=op.id)
                logger.info("[scheduler] selfie discovery: %s", totals)
    except Exception as e:
        logger.error("[scheduler] selfie discovery FAILED: %s", e)

    # Kazunion discovery — САМО-based, no login required
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Operator).where(Operator.code == "kazunion"))
            op = result.scalar_one_or_none()
            if op and op.is_active:
                from app.operators.kazunion.catalog_importer import discover_kazunion_resorts
                totals = await discover_kazunion_resorts(db, operator_id=op.id)
                logger.info("[scheduler] kazunion discovery: %s", totals)
    except Exception as e:
        logger.error("[scheduler] kazunion discovery FAILED: %s", e)

    # Pegas re-import
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Operator).where(Operator.code == "pegas"))
            op = result.scalar_one_or_none()
            if op and op.is_active:
                from app.core.config import settings
                from app.operators.pegas.catalog_importer import import_pegas_catalog, import_pegas_departure_locations
                from app.operators.playwright_session.login import fetch_pegas_session_cookies
                from app.operators.playwright_session.session_manager import PlaywrightSessionManager
                session_manager = PlaywrightSessionManager(db)
                cookies = await session_manager.get_valid_cookies(
                    operator_id=op.id,
                    login_fn=lambda: fetch_pegas_session_cookies(
                        settings.pegas_login, settings.pegas_password
                    ),
                )
                await import_pegas_departure_locations(db, cookies)
                await import_pegas_catalog(db, cookies, operator_id=op.id)
                logger.info("[scheduler] pegas catalog re-import complete")
    except Exception as e:
        logger.error("[scheduler] pegas discovery FAILED: %s", e)

    # Расширяем горизонт данных
    try:
        await run_horizon_expansion()
    except Exception as e:
        logger.error("[scheduler] horizon_expansion FAILED: %s", e)

    # Авто-матч отелей — запускаем после каждого discovery
    try:
        from app.database import AsyncSessionLocal
        from app.repositories.mapping_repo import HotelMappingRepository
        async with AsyncSessionLocal() as db:
            repo = HotelMappingRepository(db)
            count = await repo.run_auto_match(threshold=90)
            logger.info("[scheduler] auto_match complete: %d pairs", count)
    except Exception as e:
        logger.error("[scheduler] auto_match FAILED: %s", e)

    logger.info("[scheduler] discovery job complete")


async def run_refresh() -> None:
    """
    Every 3 hours: re-runs dual search for each active country.
    One broad search per country covers all dates in the next 120 days.
    Much faster than per-profile refresh.
    """
    import datetime as dt
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.mappings import CountryMapping

    DEPARTURE_CITY = "Алматы"
    ADULTS = 2
    CHILD_AGE = 4

    logger.info("[scheduler] refresh job started")

    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(CountryMapping.normalized_value)
            .where(CountryMapping.confirmed == True)  # noqa
            .distinct()
        )
        countries = [row[0] for row in r.all()]

    logger.info("[scheduler] refresh: %d countries", len(countries))

    today = dt.date.today()

    # Разбиваем на месячные окна — операторы не отдают данные за 6 месяцев сразу
    monthly_windows = []
    for month_offset in range(6):
        window_beg = today + dt.timedelta(days=1) if month_offset == 0 else (
            today.replace(day=1) + dt.timedelta(days=32 * month_offset)
        ).replace(day=1)
        next_month = (window_beg.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        window_end = next_month - dt.timedelta(days=1)
        monthly_windows.append((window_beg, window_end))

    for country in countries:
        for window_beg, window_end in monthly_windows:
            await asyncio.sleep(2)
            try:
                from app.api.v1.search import _run_country_refresh
                await asyncio.wait_for(
                    _run_country_refresh(
                        country=country,
                        departure_city=DEPARTURE_CITY,
                        checkin_beg=window_beg,
                        checkin_end=window_end,
                        nights_from=7,
                        nights_till=14,
                        adults=ADULTS,
                        child_age=CHILD_AGE,
                    ),
                    timeout=300,  # 5 минут на месяц
                )
                logger.info("[scheduler] refresh: %s %s..%s done", country, window_beg, window_end)
            except asyncio.TimeoutError:
                logger.error("[scheduler] refresh: %s %s TIMED OUT", country, window_beg)
            except Exception as e:
                logger.error("[scheduler] refresh: %s %s FAILED: %s", country, window_beg, e)

    logger.info("[scheduler] refresh job complete")


def start_scheduler() -> None:
    scheduler = get_scheduler()

    scheduler.add_job(
        run_discovery,
        CronTrigger(hour=3, minute=0, timezone="Asia/Almaty"),
        id="discovery",
        name="Daily catalog discovery",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_refresh,
        IntervalTrigger(hours=3),
        id="refresh",
        name="Profile refresh every 3h",
        replace_existing=True,
        misfire_grace_time=600,
    )

    scheduler.start()
    logger.info("[scheduler] started: discovery@03:00, refresh@every3h")


async def run_horizon_expansion() -> None:
    """
    Создаёт профили поиска на даты которых ещё нет в БД.
    Горизонт: сегодня + 120 дней.
    Запускается из run_discovery раз в сутки.
    """
    import datetime as dt
    from sqlalchemy import select, and_
    from app.database import AsyncSessionLocal
    from app.models.search_profile import SearchProfile
    from app.models.mappings import CountryMapping, CityMapping
    from app.models.operator import Operator

    HORIZON_DAYS = 120
    NIGHTS_FROM = 7
    NIGHTS_TILL = 14
    ADULTS = 2
    DEPARTURE_CITY = "Алматы"

    today = dt.date.today()
    target_end = today + dt.timedelta(days=HORIZON_DAYS)

    _log(f"horizon_expansion: filling dates up to {target_end}")

    async with AsyncSessionLocal() as db:
        # Берём все подтверждённые страны
        r = await db.execute(
            select(CountryMapping.normalized_value)
            .where(CountryMapping.confirmed == True)  # noqa
            .distinct()
        )
        countries = [row[0] for row in r.all()]

        created = 0
        for country in countries:
            # Проверяем какие недели уже есть в БД для этой страны
            r = await db.execute(
                select(SearchProfile.departure_date).where(
                    and_(
                        SearchProfile.country == country,
                        SearchProfile.departure_city == DEPARTURE_CITY,
                        SearchProfile.adults == ADULTS,
                        SearchProfile.children == 0,
                        SearchProfile.departure_date >= today,
                        SearchProfile.departure_date <= target_end,
                    )
                )
            )
            existing_dates = {row[0] for row in r.all()}

            # Создаём профили на каждую неделю которой нет
            check_date = today + dt.timedelta(days=7)
            while check_date <= target_end:
                if check_date not in existing_dates:
                    # Профиль без детей
                    db.add(SearchProfile(
                        name=f"{country} from {DEPARTURE_CITY} ({check_date})",
                        country=country,
                        departure_city=DEPARTURE_CITY,
                        departure_date=check_date,
                        nights=NIGHTS_FROM,
                        adults=ADULTS,
                        children=0,
                        is_active=True,
                    ))
                    # Профиль с ребёнком
                    db.add(SearchProfile(
                        name=f"{country} from {DEPARTURE_CITY} ({check_date}) +child",
                        country=country,
                        departure_city=DEPARTURE_CITY,
                        departure_date=check_date,
                        nights=NIGHTS_FROM,
                        adults=ADULTS,
                        children=1,
                        is_active=True,
                    ))
                    created += 2
                check_date += dt.timedelta(days=7)

        await db.commit()
        _log(f"horizon_expansion: created {created} new profiles")


def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] stopped")