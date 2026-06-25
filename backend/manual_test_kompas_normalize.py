"""
Diagnostic: why does NormalizationService produce 0 NormalizedTour rows
for a broad Kompas search that the connector itself returns hundreds of
rows for? Not a pytest test - delete after diagnosis.
"""
import asyncio

from app.database import AsyncSessionLocal
from app.operators.kompas.connector import KompasOperator
from app.services.normalization_service import NormalizationService
from sqlalchemy import select
from app.models.operator import Operator


async def main():
    operator = KompasOperator()
    rows = await operator.search(
        town_from_inc=9,
        state_inc=32,
        checkin_beg="20260701",
        checkin_end="20260702",
        nights_from=7,
        nights_till=14,
        adults=2,
        children=0,
    )
    print(f"Connector returned: {len(rows)} rows")

    parse_warnings = sum(1 for r in rows if r.get("_parse_warning"))
    not_bookable = sum(1 for r in rows if r.get("is_bookable") is False)
    no_price = sum(1 for r in rows if r.get("price_value") is None)
    print(f"  with _parse_warning: {parse_warnings}")
    print(f"  is_bookable=False: {not_bookable}")
    print(f"  price_value is None: {parse_warnings}")

    if parse_warnings:
        sample = next(r for r in rows if r.get("_parse_warning"))
        print(f"  sample warning: {sample.get('_parse_warning')}")

    good_row = next(
        (r for r in rows if not r.get("_parse_warning") and r.get("is_bookable") is not False and r.get("price_value") is not None),
        None,
    )
    print(f"First usable row: {good_row}")

    async with AsyncSessionLocal() as session:
        kompas_id = (
            await session.execute(select(Operator.id).where(Operator.code == "kompas"))
        ).scalar_one()

        service = NormalizationService(session)
        if good_row:
            tour_key, fields = await service._build_tour_key(kompas_id, good_row)
            print(f"_build_tour_key result: tour_key={tour_key}, fields={fields}")


if __name__ == "__main__":
    asyncio.run(main())