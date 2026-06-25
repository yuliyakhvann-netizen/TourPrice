import asyncio
from sqlalchemy import select, desc
from app.database import AsyncSessionLocal
from app.models.normalized_tour import NormalizedTour
from app.models.search_profile import SearchProfile

async def test():
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(SearchProfile).where(
                SearchProfile.country == 'Vietnam',
                SearchProfile.departure_city == 'Almaty',
                SearchProfile.children == 0,
            ).order_by(desc(SearchProfile.id))
        )
        p0 = r.scalars().first()

        r = await db.execute(
            select(SearchProfile).where(
                SearchProfile.country == 'Vietnam',
                SearchProfile.departure_city == 'Almaty',
                SearchProfile.children == 1,
            ).order_by(desc(SearchProfile.id))
        )
        p1 = r.scalars().first()

        print('Profile no_child: id=%s, date=%s' % (p0.id, p0.departure_date))
        print('Profile with_child: id=%s, date=%s' % (p1.id, p1.departure_date))

        subq0 = (
            select(NormalizedTour.scrape_run_id)
            .where(NormalizedTour.profile_id == p0.id)
            .order_by(NormalizedTour.scraped_at.desc())
            .limit(1).scalar_subquery()
        )
        r0 = await db.execute(select(NormalizedTour).where(
            NormalizedTour.profile_id == p0.id,
            NormalizedTour.scrape_run_id == subq0,
        ))
        t0 = r0.scalars().all()

        subq1 = (
            select(NormalizedTour.scrape_run_id)
            .where(NormalizedTour.profile_id == p1.id)
            .order_by(NormalizedTour.scraped_at.desc())
            .limit(1).scalar_subquery()
        )
        r1 = await db.execute(select(NormalizedTour).where(
            NormalizedTour.profile_id == p1.id,
            NormalizedTour.scrape_run_id == subq1,
        ))
        t1 = r1.scalars().all()

        print('Tours no_child: %d, tours with_child: %d' % (len(t0), len(t1)))

        if t1:
            sample = t1[0]
            room_norm = sample.room_type.removesuffix(' - FIX').strip()
            print('Sample with_child hotel=%s room=%s norm=%s date=%s' % (
                sample.hotel, sample.room_type, room_norm, sample.departure_date))
            match = [t for t in t0 if t.hotel == sample.hotel
                     and t.room_type.removesuffix(' - FIX').strip() == room_norm
                     and t.departure_date == sample.departure_date]
            print('Matches in no_child: %d' % len(match))
            if not match:
                by_hotel = [t for t in t0 if t.hotel == sample.hotel]
                print('By hotel only: %d' % len(by_hotel))
                if by_hotel:
                    print('no_child room_types: %s' % str(set(t.room_type for t in by_hotel)))

asyncio.run(test())
