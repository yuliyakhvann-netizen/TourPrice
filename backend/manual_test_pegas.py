"""
Manual one-off test for the Pegas connector (mirrors how FunSun/Kompas were
verified - create, run, delete). Not part of the test suite.

Run from inside the backend container:
    docker compose exec backend python manual_test_pegas.py

What this does, in order:
1. Logs into Pegas via Playwright and stores the session (or reuses a
   still-valid one already in operator_session).
2. Imports the catalog for the seed countries (writes pegas_country/
   pegas_resort/pegas_hotel/pegas_airline, and registers each resort name
   as an unconfirmed city_mapping row for the Pegas operator).
3. Picks one resort (Нячанг, Vietnam) and runs a live Search for a handful
   of upcoming departure dates, printing a summary of what came back.

Prerequisites:
- operators table must already have a row with code="pegas" (insert one
  manually if it doesn't exist yet - this script does not create it).
- .env must have PEGAS_LOGIN / PEGAS_PASSWORD set.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.models.operator import Operator
from app.models.pegas_catalog import PegasResort
from app.operators.pegas.catalog_importer import import_pegas_catalog, import_pegas_departure_locations
from app.operators.pegas.connector import PegasOperator
from app.operators.playwright_session.login import fetch_pegas_session_cookies
from app.operators.playwright_session.session_manager import PlaywrightSessionManager


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Operator).where(Operator.code == "pegas"))
        pegas_operator_row = result.scalar_one_or_none()
        if pegas_operator_row is None:
            print(
                "ERROR: no operators row with code='pegas' found. "
                "Insert one manually before running this script."
            )
            return
        operator_id = pegas_operator_row.id

        async def login_fn() -> list[dict]:
            return await fetch_pegas_session_cookies(
                settings.pegas_login, settings.pegas_password
            )

        session_manager = PlaywrightSessionManager(db)
        cookies = await session_manager.get_valid_cookies(operator_id, login_fn)
        print(f"Got {len(cookies)} session cookies.")

        print("Importing Pegas departure locations...")
        dep_count = await import_pegas_departure_locations(db, cookies)
        print(f"Departure locations imported: {dep_count}")

        print("Importing Pegas catalog (seed countries)...")
        counts = await import_pegas_catalog(db, cookies, operator_id=operator_id)
        print(f"Catalog import counts: {counts}")

        # Find Nha Trang (Нячанг) among the imported Vietnam resorts.
        result = await db.execute(
            select(PegasResort).where(PegasResort.name == "Нячанг")
        )
        nha_trang = result.scalar_one_or_none()
        if nha_trang is None:
            print("ERROR: could not find 'Нячанг' resort after import - check catalog data.")
            return
        print(f"Resolved resort: id={nha_trang.id}, name={nha_trang.name}")

        today = dt.date.today()
        departure_dates = [
            (today + dt.timedelta(days=offset)).isoformat() for offset in (10, 11, 12)
        ]

        pegas = PegasOperator()
        print(f"Searching Pegas for resort_id={nha_trang.id}, dates={departure_dates}...")
        items = await pegas.search(
            db=db,
            cookies=cookies,
            departure_location_id=553,  # Almaty, confirmed in original Search dump
            destination_country_id=156,  # Vietnam
            resort_id=nha_trang.id,
            departure_dates=departure_dates,
            durations_in_nights=[5, 6, 7],
            adults=2,
        )

        print(f"Search returned {len(items)} items.")
        for item in items[:5]:
            price = item.get("Price")
            currency_id = item.get("CurrencyId")
            hotel_services = item.get("HotelServices", [])
            hotel_id = hotel_services[0].get("HotelId") if hotel_services else None
            print(f"  hotel_id={hotel_id}, price={price}, currency_id={currency_id}")


if __name__ == "__main__":
    asyncio.run(main())