import asyncio
from sqlalchemy import select, desc
from app.database import AsyncSessionLocal
from app.models.normalized_tour import NormalizedTour
from app.models.search_profile import SearchProfile

async def test():
    async with AsyncSessionLocal() as db:
        # Все профили Vietnam/Almaty
        r = await db.execute(
            select(SearchProfile).where(
                SearchProfile.country == 'Vietnam',
                SearchProfile.departure_city == 'Almaty',
            ).order_by(desc(SearchProfile.id))
        )
        profiles = r.scalars().all()
        for p in profiles:
            print('Profile id=%d children=%d date=%s nights=%d' % (p.id, p.children, p.departure_date, p.nights))

        no_child_ids = [p.id for p in profiles if p.children == 0]
        with_child_ids = [p.id for p in profiles if p.children == 1]
        print('no_child_ids:', no_child_ids)
        print('with_child_ids:', with_child_ids)

        # Последний scrape_run по всем no_child профилям
        subq0 = (
            select(NormalizedTour.scrape_run_id)
            .where(NormalizedTour.profile_id.in_(no_child_ids))
            .order_by(NormalizedTour.scraped_at.desc())
            .limit(1).scalar_subquery()
        )
        r0 = await db.execute(select(NormalizedTour).where(
            NormalizedTour.profile_id.in_(no_child_ids),
            NormalizedTour.scrape_run_id == subq0,
        ))
        t0 = r0.scalars().all()

        subq1 = (
            select(NormalizedTour.scrape_run_id)
            .where(NormalizedTour.profile_id.in_(with_child_ids))
            .order_by(NormalizedTour.scraped_at.desc())
            .limit(1).scalar_subquery()
        )
        r1 = await db.execute(select(NormalizedTour).where(
            NormalizedTour.profile_id.in_(with_child_ids),
            NormalizedTour.scrape_run_id == subq1,
        ))
        t1 = r1.scalars().all()

        print('Tours no_child: %d, tours with_child: %d' % (len(t0), len(t1)))
        if t0:
            print('no_child sample: hotel=%s room=%s date=%s' % (t0[0].hotel, t0[0].room_type, t0[0].departure_date))
        if t1:
            print('with_child sample: hotel=%s room=%s date=%s' % (t1[0].hotel, t1[0].room_type, t1[0].departure_date))

        # Пробуем матчинг
        def norm(s):
            return s.removesuffix(' - FIX').strip()

        matches = 0
        for t in t1:
            key1 = (t.hotel, norm(t.room_type), t.meal_type, t.departure_date, t.nights, t.operator_id)
            for t2 in t0:
                key2 = (t2.hotel, norm(t2.room_type), t2.meal_type, t2.departure_date, t2.nights, t2.operator_id)
                if key1 == key2:
                    matches += 1
                    break
        print('Matched pairs: %d' % matches)

asyncio.run(test())
