from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.operator import Operator
from app.models.samo_catalog import SamoDepartureCity
from app.operators.kompas.catalog_importer import import_kompas_countries
from app.operators.pegas.catalog_importer import (
    import_pegas_catalog,
    import_pegas_departure_locations,
)
from app.operators.playwright_session.login import fetch_pegas_session_cookies
from app.operators.playwright_session.session_manager import PlaywrightSessionManager
from app.operators.samo.departure_cities import fetch_samo_departure_cities
router = APIRouter(prefix="/operators", tags=["operators"])


@router.get("/")
async def list_operators(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Operator))
    operators = result.scalars().all()
    return [
        {
            "id": op.id,
            "code": op.code,
            "name": op.name,
            "is_active": op.is_active,
            "health_status": op.health_status,
            "last_login_at": op.last_login_at,
            "last_health_check_at": op.last_health_check_at,
        }
        for op in operators
    ]


@router.post("/pegas/import-catalog")
async def trigger_pegas_catalog_import(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Запускает полный импорт каталога Pegas:
    1. Города вылета (pegas_departure_location)
    2. Страны / курорты / отели / авиалинии (seed countries)

    Вызывать вручную при первом запуске и при обновлении каталога
    (рекомендуется раз в неделю — отели открываются/закрываются).
    """
    result = await db.execute(select(Operator).where(Operator.code == "pegas"))
    pegas_op = result.scalar_one_or_none()
    if pegas_op is None:
        raise HTTPException(status_code=404, detail="Operator 'pegas' not found in DB")

    session_manager = PlaywrightSessionManager(db)
    cookies = await session_manager.get_valid_cookies(
        operator_id=pegas_op.id,
        login_fn=lambda: fetch_pegas_session_cookies(
            settings.pegas_login, settings.pegas_password
        ),
    )

    op_id = pegas_op.id
    saved_cookies = cookies

    async def run_import():
        async with AsyncSessionLocal() as bg_db:
            dep_count = await import_pegas_departure_locations(bg_db, saved_cookies)
            catalog_counts = await import_pegas_catalog(bg_db, saved_cookies, operator_id=op_id)
            print(f"[pegas_import] COMPLETE: {dep_count} locations, {catalog_counts}", flush=True)

    background_tasks.add_task(run_import)
    return {"status": "started", "message": "Импорт Pegas запущен в фоне"}
@router.post("/kompas/import-catalog")
async def trigger_kompas_catalog_import(db: AsyncSession = Depends(get_db)):
    """
    Импортирует список стран Kompas из samo_action=INIT.
    Курорты накапливаются автоматически при поиске.
    """
    result = await db.execute(select(Operator).where(Operator.code == "kompas"))
    kompas_op = result.scalar_one_or_none()
    if kompas_op is None:
        raise HTTPException(status_code=404, detail="Operator 'kompas' not found in DB")

    count = await import_kompas_countries(db)
    return {"new_countries": count}


@router.post("/kompas/discover-resorts")
async def trigger_kompas_resort_discovery(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Запускает фоновый сбор курортов по всем странам Kompas.
    Возвращает сразу — прогресс виден в логах бэкенда.
    Занимает 5-15 минут. Запускать раз в неделю.
    """
    from app.database import AsyncSessionLocal
    from app.operators.kompas.catalog_importer import discover_kompas_resorts

    result = await db.execute(select(Operator).where(Operator.code == "kompas"))
    kompas_op = result.scalar_one_or_none()
    if kompas_op is None:
        raise HTTPException(status_code=404, detail="Operator 'kompas' not found in DB")

    op_id = kompas_op.id

    async def run_discovery():
        async with AsyncSessionLocal() as bg_db:
            totals = await discover_kompas_resorts(bg_db, operator_id=op_id)
            total = sum(totals.values())
            print(f"[discover_resorts] COMPLETE: {total} resorts total", flush=True)

    background_tasks.add_task(run_discovery)
    return {"status": "started", "message": "Сбор курортов запущен в фоне, следите за логами"}
    """
    Импортирует список стран Kompas из samo_action=INIT.
    Курорты накапливаются автоматически при поиске.
    """
    result = await db.execute(select(Operator).where(Operator.code == "kompas"))
    kompas_op = result.scalar_one_or_none()
    if kompas_op is None:
        raise HTTPException(status_code=404, detail="Operator 'kompas' not found in DB")

    count = await import_kompas_countries(db)
    return {"new_countries": count}
@router.post("/scheduler/run/{job_id}")
async def scheduler_run_now(job_id: str, background_tasks: BackgroundTasks):
    """
    Запускает джоб scheduler вручную немедленно.
    job_id: 'discovery' или 'refresh'
    """
    from app.scheduler import run_discovery, run_refresh

    jobs = {"discovery": run_discovery, "refresh": run_refresh}
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found. Available: {list(jobs.keys())}")

    background_tasks.add_task(jobs[job_id])
    return {"status": "started", "job_id": job_id}


@router.get("/scheduler/status")
async def scheduler_status():
    """Показывает статус и список джобов scheduler."""
    from app.scheduler import get_scheduler
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": scheduler.running, "jobs": jobs}


@router.get("/pegas/departure-locations")
async def get_departure_locations(db: AsyncSession = Depends(get_db)):
    """Список городов вылета из pegas_departure_location."""
    from app.models.pegas_catalog import PegasDepartureLocation
    result = await db.execute(
        select(PegasDepartureLocation).order_by(PegasDepartureLocation.name)
    )
    locations = result.scalars().all()
    return [{"id": loc.id, "name": loc.name} for loc in locations]


@router.post("/samo/discover-departure-cities")
async def discover_samo_departure_cities(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Обходит все активные САМО-операторы, вызывает samo_action=INIT,
    сохраняет города вылета в samo_departure_city.
    Запускается в фоне.
    """
    background_tasks.add_task(_discover_samo_cities_task)
    return {"status": "started"}


async def _discover_samo_cities_task() -> None:
    """
    Фоновая задача: для каждого активного САМО-оператора
    получает города вылета и сохраняет в samo_departure_city.
    """
    from app.operators.registry import OPERATOR_CONNECTORS

    SAMO_CONFIGS = {
        "kompas": ("app.operators.kompas.config", "kompas"),
        "selfie": ("app.operators.selfie.config", "selfie"),
        "funsun": ("app.operators.funsun.config", "funsun"),
    }

    async with AsyncSessionLocal() as db:
        operators_result = await db.execute(
            select(Operator.id, Operator.code).where(Operator.is_active == True)  # noqa
        )
        operators = operators_result.all()

        for op_id, op_code in operators:
            if op_code not in SAMO_CONFIGS:
                continue

            module_path, _ = SAMO_CONFIGS[op_code]
            try:
                import importlib
                cfg = importlib.import_module(module_path)
                cities = await fetch_samo_departure_cities(
                    base_url=cfg.BASE_URL,
                    town_from_inc=cfg.TOWN_FROM_ALMATY,
                )
            except Exception as e:
                print(f"[samo_cities] op={op_code} FAILED: {e}", flush=True)
                continue

            from app.models.mappings import CityMapping
            from datetime import datetime, timezone

            for city_inc, city_name in cities.items():
                # 1. Upsert в samo_departure_city
                existing = await db.execute(
                    select(SamoDepartureCity).where(
                        SamoDepartureCity.operator_id == op_id,
                        SamoDepartureCity.city_inc == city_inc,
                    )
                )
                row = existing.scalar_one_or_none()
                if row is None:
                    db.add(SamoDepartureCity(
                        operator_id=op_id,
                        city_inc=city_inc,
                        name=city_name,
                    ))
                else:
                    row.name = city_name

                # 2. Upsert в city_mapping с confirmed=True
                cm_existing = await db.execute(
                    select(CityMapping).where(
                        CityMapping.operator_id == op_id,
                        CityMapping.raw_value == str(city_inc),
                    )
                )
                cm_row = cm_existing.scalar_one_or_none()
                if cm_row is None:
                    db.add(CityMapping(
                        operator_id=op_id,
                        raw_value=str(city_inc),
                        normalized_value=city_name,
                        confirmed=True,
                        confirmed_at=datetime.now(timezone.utc),
                    ))
                else:
                    cm_row.normalized_value = city_name
                    if not cm_row.confirmed:
                        cm_row.confirmed = True
                        cm_row.confirmed_at = datetime.now(timezone.utc)

            await db.commit()
            print(f"[samo_cities] op={op_code} saved {len(cities)} cities", flush=True)


@router.get("/countries")
async def get_countries(db: AsyncSession = Depends(get_db)):
    """Список стран из country_mapping WHERE confirmed=true."""
    from app.models.mappings import CountryMapping
    result = await db.execute(
        select(CountryMapping.normalized_value)
        .where(CountryMapping.confirmed == True)  # noqa
        .distinct()
        .order_by(CountryMapping.normalized_value)
    )
    return [row[0] for row in result.all()]


@router.get("/departure-cities")
async def get_confirmed_departure_cities(db: AsyncSession = Depends(get_db)):
    """
    Возвращает уникальные города вылета.
    Источник: samo_departure_city + pegas_departure_location.
    Исключает названия которые есть в country_mapping (это страны назначения, не города).
    """
    from app.models.samo_catalog import SamoDepartureCity
    from app.models.pegas_catalog import PegasDepartureLocation
    from app.models.mappings import CountryMapping

    from app.models.kompas_catalog import KompasCountry
    from app.models.pegas_catalog import PegasCountry

    # Собираем все известные названия стран из всех источников
    country_names: set[str] = set()

    r1 = await db.execute(select(CountryMapping.normalized_value).distinct())
    country_names.update(row[0] for row in r1.all())

    r2 = await db.execute(select(KompasCountry.name).distinct())
    country_names.update(row[0] for row in r2.all())

    r3 = await db.execute(select(PegasCountry.name).distinct())
    country_names.update(row[0] for row in r3.all())

    # САМО города
    samo_result = await db.execute(
        select(SamoDepartureCity.name).distinct()
    )
    names = {row[0] for row in samo_result.all() if row[0] not in country_names}

    # Pegas города (только КЗ — они точно не страны)
    pegas_result = await db.execute(
        select(PegasDepartureLocation.name).distinct()
    )
    for row in pegas_result.all():
        if row[0] not in country_names:
            names.add(row[0])

    return sorted(names)


@router.post("/kazunion/discover-resorts")
async def trigger_kazunion_resort_discovery(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Запускает фоновый сбор курортов по всем странам Kazunion.
    Upsert стран из конфига + broad PRICES search для каждой страны.
    Возвращает сразу — прогресс виден в логах бэкенда.
    """
    from app.database import AsyncSessionLocal
    from app.operators.kazunion.catalog_importer import discover_kazunion_resorts

    result = await db.execute(select(Operator).where(Operator.code == "kazunion"))
    kazunion_op = result.scalar_one_or_none()
    if kazunion_op is None:
        raise HTTPException(status_code=404, detail="Operator 'kazunion' not found in DB")

    op_id = kazunion_op.id

    async def run_discovery():
        async with AsyncSessionLocal() as bg_db:
            totals = await discover_kazunion_resorts(bg_db, operator_id=op_id)
            total = sum(totals.values())
            print(f"[kazunion_discover] COMPLETE: {total} resorts total", flush=True)

    background_tasks.add_task(run_discovery)
    return {"status": "started", "message": "Сбор курортов Kazunion запущен в фоне, следите за логами"}


@router.post("/kompas/import-destination-towns")
async def trigger_kompas_destination_towns_import(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Импортирует TOWNS ID (города прибытия внутри страны) для всех стран Kompas.
    Нужны для детского поиска: TOWNS_ANY=0&TOWNS=<id1,id2,...>
    Запускать после import-catalog.
    """
    from app.operators.kompas.destination_towns_importer import import_all_destination_towns

    async def run_import():
        async with AsyncSessionLocal() as bg_db:
            stats = await import_all_destination_towns(bg_db)
            total = sum(stats.values())
            print(f"[destination_towns] COMPLETE: {total} towns across {len(stats)} countries", flush=True)
            for country, count in stats.items():
                if count > 0:
                    print(f"  {country}: {count} towns", flush=True)

    background_tasks.add_task(run_import)
    return {"status": "started", "message": "Импорт городов прибытия запущен в фоне, следите за логами"}


@router.get("/resorts")
async def get_resorts(country: str, db: AsyncSession = Depends(get_db)):
    """
    Возвращает уникальные названия курортов для страны.
    Объединяет kompas_resort и pegas_resort.
    """
    from app.models.kompas_catalog import KompasCountry, KompasResort
    from app.models.pegas_catalog import PegasCountry, PegasResort
    from sqlalchemy import union_all, literal_column

    # Kompas resorts
    kompas_q = (
        select(KompasResort.name)
        .join(KompasCountry, KompasResort.country_id == KompasCountry.id)
        .where(KompasCountry.name == country)
    )
    # Pegas resorts
    pegas_q = (
        select(PegasResort.name)
        .join(PegasCountry, PegasResort.country_id == PegasCountry.id)
        .where(PegasCountry.name == country)
    )

    from app.models.kazunion_catalog import KazunionCountry, KazunionResort
    kazunion_q = (
        select(KazunionResort.name)
        .join(KazunionCountry, KazunionResort.country_samo_id == KazunionCountry.samo_id)
        .where(KazunionCountry.name == country)
    )

    kompas_result = await db.execute(kompas_q)
    pegas_result = await db.execute(pegas_q)
    kazunion_result = await db.execute(kazunion_q)

    names = set()
    for row in kompas_result.all():
        names.add(row[0])
    for row in pegas_result.all():
        names.add(row[0])
    for row in kazunion_result.all():
        names.add(row[0])

    return sorted(names)