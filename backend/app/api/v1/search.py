"""
Live search: resolves a person's plain-language filters (country,
departure city, dates) into a price comparison across every connector
in OPERATOR_CONNECTORS.

Flow: find-or-create a SearchProfile matching the filters -> if a
comparison newer than CACHE_FRESHNESS_HOURS already exists for it,
return that -> otherwise hit every operator live, normalize, compare,
and return the fresh result.

Operators with no confirmed CityMapping/CountryMapping for the
requested names are silently skipped, not fabricated - per the
project's principle of never guessing operator-specific codes. The
response includes which operators were actually searched so the
frontend can show "Kompas: код города не подтверждён" instead of
quietly showing a one-sided comparison.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_city_mapping_repo,
    get_comparison_service,
    get_country_mapping_repo,
    get_db,
    get_normalization_service,
)
from app.core.config import settings
from app.models.comparison_result import ComparisonResult
from app.models.normalized_tour import NormalizedTour
from app.models.operator import Operator
from app.models.pegas_catalog import PegasDepartureLocation
from app.models.search_profile import SearchProfile
from app.operators.pegas.config import OPERATOR_CODE as PEGAS_OPERATOR_CODE
from app.operators.playwright_session.login import fetch_pegas_session_cookies
from app.operators.playwright_session.session_manager import PlaywrightSessionManager
from app.operators.registry import OPERATOR_CONNECTORS
from app.repositories.mapping_repo import CityMappingRepository, CountryMappingRepository
from app.schemas.comparison import ComparisonResultResponse, DualSearchTourResult, OperatorDualPrice
from app.schemas.search import DualSearchRequest, LiveSearchRequest
from app.services.comparison_service import ComparisonService
from app.services.normalization_service import NormalizationService

router = APIRouter(prefix="/search", tags=["search"])

CACHE_FRESHNESS_HOURS = 2
PEGAS_DEFAULT_DEPARTURE_LOCATION_ID = 553  # Алматы — fallback если город не найден в БД


def _date_range(start: date, end: date) -> list[str]:
    """Список ISO-дат от start до end включительно."""
    return [
        (start + timedelta(days=i)).isoformat()
        for i in range((end - start).days + 1)
    ]


@router.post("/live", response_model=list[ComparisonResultResponse])
async def live_search(
    body: LiveSearchRequest,
    db: AsyncSession = Depends(get_db),
    city_repo: CityMappingRepository = Depends(get_city_mapping_repo),
    country_repo: CountryMappingRepository = Depends(get_country_mapping_repo),
    normalization_service: NormalizationService = Depends(get_normalization_service),
    comparison_service: ComparisonService = Depends(get_comparison_service),
):
    profile = await _find_or_create_profile(db, body)

    cached = await _get_fresh_comparison(db, profile.id)
    if cached:
        return cached

    operators_result = await db.execute(
        select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa: E712
    )
    operators = operators_result.all()

    for op_id, op_code in operators:
        connector = OPERATOR_CONNECTORS.get(op_code)
        if connector is None:
            continue

        town_from_raw = await city_repo.get_raw_value(op_id, body.departure_city)
        state_raw = await country_repo.get_raw_value(op_id, body.country)
        if town_from_raw is None or state_raw is None:
            continue

        try:
            if op_code == PEGAS_OPERATOR_CODE:
                coro = _search_pegas(
                    connector=connector,
                    db=db,
                    op_id=op_id,
                    resort_id=int(town_from_raw),
                    destination_country_id=int(state_raw),
                    body=body,
                )
            else:
                coro = connector.search(
                    town_from_inc=int(town_from_raw),
                    state_inc=int(state_raw),
                    checkin_beg=body.checkin_beg.strftime("%Y%m%d"),
                    checkin_end=body.checkin_end.strftime("%Y%m%d"),
                    nights_from=body.nights_from,
                    nights_till=body.nights_till,
                    adults=body.adults,
                    children=body.children,
                )

            rows = await asyncio.wait_for(coro, timeout=OPERATOR_SEARCH_TIMEOUT)

        except asyncio.TimeoutError:
            print(
                f"[live_search] operator={op_code} "
                f"TIMEOUT after {OPERATOR_SEARCH_TIMEOUT}s — skipping",
                flush=True,
            )
            continue
        except Exception as exc:
            print(f"[live_search] operator={op_code} FAILED: {exc}", flush=True)
            continue

        raw_result, normalized_tours = await normalization_service.ingest_search_results(
            operator_id=op_id, profile_id=profile.id, rows=rows, operator_code=op_code
        )
        print(
            f"[live_search] operator={op_code} fetched={len(rows)} "
            f"normalized={len(normalized_tours)}",
            flush=True,
        )

    await comparison_service.run_for_profile(profile.id)
    await db.commit()

    return await _get_fresh_comparison(db, profile.id) or []


async def _find_or_create_profile(db: AsyncSession, body: LiveSearchRequest) -> SearchProfile:
    name = f"{body.country} from {body.departure_city} ({body.checkin_beg})"
    from sqlalchemy import desc
    existing = await db.execute(
        select(SearchProfile).where(
            SearchProfile.country == body.country,
            SearchProfile.departure_city == body.departure_city,
            SearchProfile.departure_date == body.checkin_beg,
            SearchProfile.nights == body.nights_from,
            SearchProfile.adults == body.adults,
            SearchProfile.children == body.children,
        ).order_by(desc(SearchProfile.id))
    )
    profile = existing.scalars().first()
    if profile:
        return profile

    profile = SearchProfile(
        name=name,
        country=body.country,
        departure_city=body.departure_city,
        departure_date=body.checkin_beg,
        nights=body.nights_from,
        adults=body.adults,
        children=body.children,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _get_fresh_comparison(
    db: AsyncSession, profile_id: int
) -> list[ComparisonResult] | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_FRESHNESS_HOURS)
    subq = (
        select(ComparisonResult.scrape_run_id)
        .where(
            ComparisonResult.profile_id == profile_id,
            ComparisonResult.created_at >= cutoff,
        )
        .order_by(ComparisonResult.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    result = await db.execute(
        select(ComparisonResult).where(
            ComparisonResult.profile_id == profile_id,
            ComparisonResult.scrape_run_id == subq,
        )
    )
    rows = list(result.scalars().all())
    return rows if rows else None


async def _search_pegas(
    *,
    connector,
    db: AsyncSession,
    op_id: int,
    resort_id: int,
    destination_country_id: int,
    body: LiveSearchRequest,
) -> list[dict]:
    """
    Pegas требует сессионные куки и имеет другую сигнатуру поиска.
    Получаем/обновляем сессию через PlaywrightSessionManager,
    затем вызываем PegasOperator.search().

    departure_location_id ищется в pegas_departure_location по имени города.
    Если город не найден — fallback на Алматы (553).

    child_ages: схема пока хранит только количество детей (body.children),
    возраст не задаётся — используем 4 года как дефолт.
    Будет уточнено в задаче dual-passenger search.
    """
    session_manager = PlaywrightSessionManager(db)
    cookies = await session_manager.get_valid_cookies(
        operator_id=op_id,
        login_fn=lambda: fetch_pegas_session_cookies(
            settings.pegas_login, settings.pegas_password
        ),
    )

    dep_result = await db.execute(
        select(PegasDepartureLocation).where(
            PegasDepartureLocation.name == body.departure_city
        )
    )
    dep_loc = dep_result.scalar_one_or_none()
    departure_location_id = dep_loc.id if dep_loc else PEGAS_DEFAULT_DEPARTURE_LOCATION_ID
    if dep_loc is None:
        print(
            f"[live_search] pegas: departure city '{body.departure_city}' not found "
            f"in pegas_departure_location, falling back to Алматы (553)",
            flush=True,
        )

    child_ages = [4] * body.children  # TODO: уточнить в dual-passenger задаче

    return await connector.search(
        db=db,
        cookies=cookies,
        departure_location_id=departure_location_id,
        destination_country_id=destination_country_id,
        resort_id=resort_id,
        departure_dates=_date_range(body.checkin_beg, body.checkin_end),
        durations_in_nights=list(range(body.nights_from, body.nights_till + 1)),
        adults=body.adults,
        child_ages=child_ages,
    )

@router.post("/dual", response_model=list[DualSearchTourResult])
async def dual_search(
    body: DualSearchRequest,
    db: AsyncSession = Depends(get_db),
    city_repo: CityMappingRepository = Depends(get_city_mapping_repo),
    country_repo: CountryMappingRepository = Depends(get_country_mapping_repo),
    normalization_service: NormalizationService = Depends(get_normalization_service),
):
    """
    Dual-passenger search: запускает каждого оператора дважды
    (children=0 и children=1) и возвращает все варианты туров
    с diff по каждой комбинации (отель, номер, питание, дата, ночи).

    Оба прогона пишутся в normalized_tours как обычно.
    Результат агрегируется на лету через JOIN по явным полям —
    в comparison_results не пишем (там hardcoded per-operator колонки).
    """
    # Создаём два профиля — без детей и с ребёнком
    body_no_child = LiveSearchRequest(
        country=body.country,
        departure_city=body.departure_city,
        checkin_beg=body.checkin_beg,
        checkin_end=body.checkin_end,
        nights_from=body.nights_from,
        nights_till=body.nights_till,
        adults=body.adults,
        children=0,
    )
    body_with_child = LiveSearchRequest(
        country=body.country,
        departure_city=body.departure_city,
        checkin_beg=body.checkin_beg,
        checkin_end=body.checkin_end,
        nights_from=body.nights_from,
        nights_till=body.nights_till,
        adults=body.adults,
        children=1,
    )

    profile_no_child = await _find_or_create_profile(db, body_no_child)
    profile_with_child = await _find_or_create_profile(db, body_with_child)

    operators_result = await db.execute(
        select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa: E712
    )
    operators = operators_result.all()

    # Прогон 1: без детей — собираем scrape_run_ids
    run_ids_no_child: list[str] = []
    for op_id, op_code in operators:
        run_id = await _run_operator_search(
            db=db,
            op_id=op_id,
            op_code=op_code,
            body=body_no_child,
            child_age=None,
            profile=profile_no_child,
            city_repo=city_repo,
            country_repo=country_repo,
            normalization_service=normalization_service,
        )
        if run_id:
            run_ids_no_child.append(run_id)

    # Прогон 2: с ребёнком — собираем scrape_run_ids
    run_ids_with_child: list[str] = []
    for op_id, op_code in operators:
        run_id = await _run_operator_search(
            db=db,
            op_id=op_id,
            op_code=op_code,
            body=body_with_child,
            child_age=body.child_age,
            profile=profile_with_child,
            city_repo=city_repo,
            country_repo=country_repo,
            normalization_service=normalization_service,
        )
        if run_id:
            run_ids_with_child.append(run_id)

    await db.commit()

    # Для op_code_map нужны ВСЕ операторы, не только активные
    all_operators_result = await db.execute(select(Operator.id, Operator.code))
    all_operators = all_operators_result.all()

    # Находим все профили с теми же параметрами поиска
    r_no = await db.execute(
        select(SearchProfile.id).where(
            SearchProfile.country == body.country,
            SearchProfile.departure_city == body.departure_city,
            SearchProfile.departure_date == body.checkin_beg,
            SearchProfile.nights == body.nights_from,
            SearchProfile.adults == body.adults,
            SearchProfile.children == 0,
        )
    )
    all_no_child_ids = [row[0] for row in r_no.all()]

    r_with = await db.execute(
        select(SearchProfile.id).where(
            SearchProfile.country == body.country,
            SearchProfile.departure_city == body.departure_city,
            SearchProfile.departure_date == body.checkin_beg,
            SearchProfile.nights == body.nights_from,
            SearchProfile.adults == body.adults,
            SearchProfile.children == 1,
        )
    )
    all_with_child_ids = [row[0] for row in r_with.all()]

    return await _build_dual_results(
        db=db,
        run_ids_no_child=run_ids_no_child,
        all_no_child_ids=all_no_child_ids or [profile_no_child.id],
        run_ids_with_child=run_ids_with_child,
        all_with_child_ids=all_with_child_ids or [profile_with_child.id],
        operators=all_operators,
        body=body_no_child,
    )


OPERATOR_SEARCH_TIMEOUT = 120.0  # 2 минуты на оператора — если сайт лежит, не ждём вечно


async def _run_operator_search(
    *,
    db: AsyncSession,
    op_id: int,
    op_code: str,
    body: LiveSearchRequest,
    child_age: int | None,
    profile,
    city_repo: CityMappingRepository,
    country_repo: CountryMappingRepository,
    normalization_service: NormalizationService,
) -> str | None:
    """
    Один прогон одного оператора, результат пишется в normalized_tours.
    Возвращает scrape_run_id этого прогона, или None если поиск не запустился.
    """
    connector = OPERATOR_CONNECTORS.get(op_code)
    if connector is None:
        return None

    town_from_raw = await city_repo.get_raw_value(op_id, body.departure_city)
    state_raw = await country_repo.get_raw_value(op_id, body.country)
    if town_from_raw is None or state_raw is None:
        return None

    # Проверяем свежие данные в normalized_tours (не старше 4 часов)
    # Ищем по стране+датам+оператору — не по profile_id,
    # потому что scheduler пишет под широким профилем (весь диапазон дат),
    # а фронт создаёт узкий профиль под конкретную дату.
    cache_cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    fresh_run = await db.execute(
        select(NormalizedTour.scrape_run_id)
        .join(SearchProfile, NormalizedTour.profile_id == SearchProfile.id)
        .where(
            NormalizedTour.operator_id == op_id,
            NormalizedTour.scraped_at >= cache_cutoff,
            SearchProfile.country == body.country,
            SearchProfile.departure_city == body.departure_city,
            SearchProfile.children == body.children,
            NormalizedTour.departure_date >= body.checkin_beg,
            NormalizedTour.departure_date <= body.checkin_end,
        )
        .order_by(NormalizedTour.scraped_at.desc())
        .limit(1)
    )
    fresh_run_id = fresh_run.scalar_one_or_none()
    if fresh_run_id:
        print(
            f"[dual_search] operator={op_code} children={body.children} "
            f"CACHE HIT (country-wide) scrape_run_id={fresh_run_id}",
            flush=True,
        )
        return fresh_run_id

    try:
        if op_code == PEGAS_OPERATOR_CODE:
            pegas_child_ages = [child_age] if child_age is not None and body.children > 0 else []
            from app.models.pegas_catalog import PegasResort
            resorts_result = await db.execute(
                select(PegasResort.id).where(
                    PegasResort.country_id == int(state_raw)
                )
            )
            pegas_resort_ids = [row[0] for row in resorts_result.all()]
            if not pegas_resort_ids:
                print(
                    f"[dual_search] pegas: no resorts for country_id={state_raw} — skipping",
                    flush=True,
                )
                return None

            all_rows: list[dict] = []
            for resort_id in pegas_resort_ids:
                try:
                    resort_rows = await asyncio.wait_for(
                        _search_pegas_with_child_ages(
                            connector=connector,
                            db=db,
                            op_id=op_id,
                            resort_id=resort_id,
                            destination_country_id=int(state_raw),
                            body=body,
                            child_ages=pegas_child_ages,
                        ),
                        timeout=OPERATOR_SEARCH_TIMEOUT,
                    )
                    all_rows.extend(resort_rows)
                except Exception as e:
                    print(f"[dual_search] pegas resort_id={resort_id} FAILED: {e}", flush=True)

            rows = all_rows
        else:
            samo_child_ages = [child_age] if child_age is not None and body.children > 0 else []

            coro = connector.search(
                town_from_inc=int(town_from_raw),
                state_inc=int(state_raw),
                checkin_beg=body.checkin_beg.strftime("%Y%m%d"),
                checkin_end=body.checkin_end.strftime("%Y%m%d"),
                nights_from=body.nights_from,
                nights_till=body.nights_till,
                adults=body.adults,
                children=body.children,
                child_ages=samo_child_ages,
                db=db,
            )
            rows = await asyncio.wait_for(coro, timeout=OPERATOR_SEARCH_TIMEOUT)

    except asyncio.TimeoutError:
        print(
            f"[dual_search] operator={op_code} children={body.children} "
            f"TIMEOUT after {OPERATOR_SEARCH_TIMEOUT}s — skipping",
            flush=True,
        )
        return None
    except Exception as exc:
        print(f"[dual_search] operator={op_code} children={body.children} FAILED: {exc}", flush=True)
        return None

    raw_result, normalized_tours = await normalization_service.ingest_search_results(
        operator_id=op_id, profile_id=profile.id, rows=rows, operator_code=op_code
    )
    print(
        f"[dual_search] operator={op_code} children={body.children} "
        f"fetched={len(rows)} normalized={len(normalized_tours)}",
        flush=True,
    )
    return raw_result.scrape_run_id


async def _search_pegas_with_child_ages(
    *,
    connector,
    db: AsyncSession,
    op_id: int,
    resort_id: int,
    destination_country_id: int,
    body: LiveSearchRequest,
    child_ages: list[int],
) -> list[dict]:
    """Pegas-поиск с явным списком возрастов детей."""
    session_manager = PlaywrightSessionManager(db)
    cookies = await session_manager.get_valid_cookies(
        operator_id=op_id,
        login_fn=lambda: fetch_pegas_session_cookies(
            settings.pegas_login, settings.pegas_password
        ),
    )

    dep_result = await db.execute(
        select(PegasDepartureLocation).where(
            PegasDepartureLocation.name == body.departure_city
        )
    )
    dep_loc = dep_result.scalar_one_or_none()
    departure_location_id = dep_loc.id if dep_loc else PEGAS_DEFAULT_DEPARTURE_LOCATION_ID

    return await connector.search(
        db=db,
        cookies=cookies,
        departure_location_id=departure_location_id,
        destination_country_id=destination_country_id,
        resort_id=resort_id,
        departure_dates=_date_range(body.checkin_beg, body.checkin_end),
        durations_in_nights=list(range(body.nights_from, body.nights_till + 1)),
        adults=body.adults,
        child_ages=child_ages,
    )


async def _build_dual_results(
    *,
    db: AsyncSession,
    run_ids_no_child: list[str],
    all_no_child_ids: list[int],
    run_ids_with_child: list[str],
    all_with_child_ids: list[int],
    operators: list,
    body: LiveSearchRequest,
) -> list[DualSearchTourResult]:
    """
    Агрегирует normalized_tours в dual-результат.
    Приоритет: scrape_run_id текущего прогона.
    Fallback: последние данные из профиля если текущий прогон упал.
    JOIN по (hotel, room_type, meal_type, departure_date, nights, operator_id).
    """
    async def load_tours(run_ids: list[str], profile_ids: list[int], children_val: int) -> list:
        # Всегда ищем по стране/датам — это даёт все данные независимо от профиля
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        result = await db.execute(
            select(NormalizedTour)
            .join(SearchProfile, NormalizedTour.profile_id == SearchProfile.id)
            .where(
                SearchProfile.country == body.country,
                SearchProfile.departure_city == body.departure_city,
                SearchProfile.children == children_val,
                NormalizedTour.departure_date >= body.checkin_beg,
                NormalizedTour.departure_date <= body.checkin_end,
                NormalizedTour.nights >= body.nights_from,
                NormalizedTour.nights <= body.nights_till,
                NormalizedTour.scraped_at >= cutoff,
            )
        )
        return result.scalars().all()

    tours_no_child = await load_tours(run_ids_no_child, all_no_child_ids, children_val=0)
    tours_with_child = await load_tours(run_ids_with_child, all_with_child_ids, children_val=1)
    
    if not tours_no_child and not tours_with_child:
        return []

    # operator_id -> code
    op_code_map = {op_id: op_code for op_id, op_code in operators}

    # Индексируем по (hotel, room_type, meal_type, departure_date, nights, operator_id)
    # Для каждого ключа берём минимальную цену (может быть несколько scrape_run)
    MatchKey = tuple  # (hotel, room_type, meal_type, departure_date, nights, operator_id)

    def _normalize_room_type(room_type: str) -> str:
        """SAMO добавляет ' - FIX' к room_type при поиске с детьми — убираем для матчинга."""
        return room_type.removesuffix(" - FIX").strip()

    def build_index(tours) -> dict[MatchKey, Decimal]:
        index: dict[MatchKey, Decimal] = {}
        for t in tours:
            key = (t.hotel, _normalize_room_type(t.room_type), t.meal_type, t.departure_date, t.nights, t.operator_id)
            if key not in index or t.price < index[key]:
                index[key] = t.price
        return index

    # Индекс resort: (hotel, room_type, meal_type, departure_date, nights) -> resort
    def build_resort_index(tours) -> dict[tuple, str]:
        index: dict[tuple, str] = {}
        for t in tours:
            key = (t.hotel, _normalize_room_type(t.room_type), t.meal_type, t.departure_date, t.nights)
            if key not in index and t.resort:
                index[key] = t.resort
        return index

    index_no_child = build_index(tours_no_child)
    index_with_child = build_index(tours_with_child)
    resort_index = build_resort_index(list(tours_no_child) + list(tours_with_child))


    # Объединяем все ключи
    all_keys = set(index_no_child.keys()) | set(index_with_child.keys())

    # Группируем по (hotel, room_type, meal_type, departure_date, nights)
    from collections import defaultdict
    groups: dict[tuple, dict[int, OperatorDualPrice]] = defaultdict(dict)

    for key in all_keys:
        hotel, room_type, meal_type, departure_date, nights, operator_id = key
        group_key = (hotel, room_type, meal_type, departure_date, nights)

        price_no = index_no_child.get(key)
        price_with = index_with_child.get(key)
        diff = (price_with - price_no) if (price_no is not None and price_with is not None) else None

        op_code = op_code_map.get(operator_id, str(operator_id))
        groups[group_key][operator_id] = OperatorDualPrice(
            operator_code=op_code,
            price_adults_only=price_no,
            price_with_child=price_with,
            child_diff=diff,
        )

    # Собираем финальный список, сортируем по отелю и дате
    results = []
    for (hotel, room_type, meal_type, departure_date, nights), op_prices in sorted(groups.items()):
        group_key = (hotel, room_type, meal_type, departure_date, nights)
        results.append(DualSearchTourResult(
            hotel=hotel,
            resort=resort_index.get(group_key, ""),
            room_type=room_type,
            meal_type=meal_type,
            departure_date=departure_date,
            nights=nights,
            operators=sorted(op_prices.values(), key=lambda x: x.operator_code),
        ))

    return results
async def _run_live_search_for_profile(profile_id: int) -> None:
    """
    Запускает live search для конкретного профиля.
    Используется scheduler'ом для периодического обновления.
    Создаёт собственную DB сессию — не зависит от request-scope.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.mapping_repo import CityMappingRepository, CountryMappingRepository
    from app.services.comparison_service import ComparisonService
    from app.services.normalization_service import NormalizationService

    async with AsyncSessionLocal() as db:
        profile = await db.get(SearchProfile, profile_id)
        if profile is None:
            logger.warning("[refresh] profile_id=%d not found", profile_id)
            return

        # Конвертируем профиль в LiveSearchRequest
        body = LiveSearchRequest(
            country=profile.country,
            departure_city=profile.departure_city,
            checkin_beg=profile.departure_date,
            checkin_end=profile.departure_date + timedelta(days=7),
            nights_from=profile.nights,
            nights_till=profile.nights,
            adults=profile.adults,
            children=profile.children,
        )

        city_repo = CityMappingRepository(db)
        country_repo = CountryMappingRepository(db)
        normalization_service = NormalizationService(db)
        comparison_service = ComparisonService(db)

        operators_result = await db.execute(
            select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa: E712
        )
        operators = operators_result.all()

        for op_id, op_code in operators:
            connector = OPERATOR_CONNECTORS.get(op_code)
            if connector is None:
                continue

            town_from_raw = await city_repo.get_raw_value(op_id, body.departure_city)
            state_raw = await country_repo.get_raw_value(op_id, body.country)
            if town_from_raw is None or state_raw is None:
                continue

            try:
                if op_code == PEGAS_OPERATOR_CODE:
                    coro = _search_pegas(
                        connector=connector,
                        db=db,
                        op_id=op_id,
                        resort_id=int(town_from_raw),
                        destination_country_id=int(state_raw),
                        body=body,
                    )
                else:
                    coro = connector.search(
                        town_from_inc=int(town_from_raw),
                        state_inc=int(state_raw),
                        checkin_beg=body.checkin_beg.strftime("%Y%m%d"),
                        checkin_end=body.checkin_end.strftime("%Y%m%d"),
                        nights_from=body.nights_from,
                        nights_till=body.nights_till,
                        adults=body.adults,
                        children=body.children,
                        db=db,
                    )

                rows = await asyncio.wait_for(coro, timeout=OPERATOR_SEARCH_TIMEOUT)

            except asyncio.TimeoutError:
                logger.warning("[refresh] op=%s profile=%d TIMEOUT", op_code, profile_id)
                continue
            except Exception as exc:
                logger.error("[refresh] op=%s profile=%d FAILED: %s", op_code, profile_id, exc)
                continue

            _, normalized_tours = await normalization_service.ingest_search_results(
                operator_id=op_id, profile_id=profile.id, rows=rows, operator_code=op_code
            )
            logger.info("[refresh] op=%s profile=%d normalized=%d", op_code, profile_id, len(normalized_tours))

        await comparison_service.run_for_profile(profile.id)
        await db.commit()
        logger.info("[refresh] profile=%d complete", profile_id)


async def _run_dual_search_for_profile(profile_id: int) -> None:
    """
    Запускает dual search для конкретного профиля.
    Используется scheduler'ом для периодического обновления.
    Создаёт собственную DB сессию.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.mapping_repo import CityMappingRepository, CountryMappingRepository
    from app.services.normalization_service import NormalizationService

    async with AsyncSessionLocal() as db:
        profile = await db.get(SearchProfile, profile_id)
        if profile is None:
            logger.warning("[refresh_dual] profile_id=%d not found", profile_id)
            return

        body_no_child = LiveSearchRequest(
            country=profile.country,
            departure_city=profile.departure_city,
            checkin_beg=profile.departure_date,
            checkin_end=profile.departure_date + timedelta(days=7),
            nights_from=profile.nights,
            nights_till=profile.nights,
            adults=profile.adults,
            children=0,
        )
        body_with_child = LiveSearchRequest(
            country=profile.country,
            departure_city=profile.departure_city,
            checkin_beg=profile.departure_date,
            checkin_end=profile.departure_date + timedelta(days=7),
            nights_from=profile.nights,
            nights_till=profile.nights,
            adults=profile.adults,
            children=1,
        )
        profile_no_child = await _find_or_create_profile(db, body_no_child)
        profile_with_child = await _find_or_create_profile(db, body_with_child)

        city_repo = CityMappingRepository(db)
        country_repo = CountryMappingRepository(db)
        normalization_service = NormalizationService(db)

        operators_result = await db.execute(
            select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa: E712
        )
        operators = operators_result.all()

        for op_id, op_code in operators:
            for body, prof in [(body_no_child, profile_no_child), (body_with_child, profile_with_child)]:
                try:
                    await _run_operator_search(
                        db=db,
                        op_id=op_id,
                        op_code=op_code,
                        body=body,
                        child_age=4 if body.children > 0 else None,
                        profile=prof,
                        city_repo=city_repo,
                        country_repo=country_repo,
                        normalization_service=normalization_service,
                    )
                except Exception as e:
                    logger.error("[refresh_dual] op=%s profile=%d FAILED: %s", op_code, profile_id, e)

        await db.commit()
        logger.info("[refresh_dual] profile=%d complete", profile_id)


async def _run_country_refresh(
    *,
    country: str,
    departure_city: str,
    checkin_beg,
    checkin_end,
    nights_from: int,
    nights_till: int,
    adults: int,
    child_age: int,
) -> None:
    """
    Один широкий dual search по стране на весь диапазон дат.
    Покрывает все профили страны за один запрос к операторам.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.mapping_repo import CityMappingRepository, CountryMappingRepository
    from app.services.normalization_service import NormalizationService

    body_no_child = LiveSearchRequest(
        country=country,
        departure_city=departure_city,
        checkin_beg=checkin_beg,
        checkin_end=checkin_end,
        nights_from=nights_from,
        nights_till=nights_till,
        adults=adults,
        children=0,
    )
    body_with_child = LiveSearchRequest(
        country=country,
        departure_city=departure_city,
        checkin_beg=checkin_beg,
        checkin_end=checkin_end,
        nights_from=nights_from,
        nights_till=nights_till,
        adults=adults,
        children=1,
    )

    async with AsyncSessionLocal() as db:
        profile_no_child = await _find_or_create_profile(db, body_no_child)
        profile_with_child = await _find_or_create_profile(db, body_with_child)

        city_repo = CityMappingRepository(db)
        country_repo = CountryMappingRepository(db)
        normalization_service = NormalizationService(db)

        operators_result = await db.execute(
            select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa
        )
        operators = operators_result.all()

        for op_id, op_code in operators:
            for body, prof in [
                (body_no_child, profile_no_child),
                (body_with_child, profile_with_child),
            ]:
                try:
                    await _run_operator_search(
                        db=db,
                        op_id=op_id,
                        op_code=op_code,
                        body=body,
                        child_age=child_age if body.children > 0 else None,
                        profile=prof,
                        city_repo=city_repo,
                        country_repo=country_repo,
                        normalization_service=normalization_service,
                    )
                except Exception as e:
                    logger.error("[country_refresh] op=%s country=%s FAILED: %s", op_code, country, e)

        await db.commit()