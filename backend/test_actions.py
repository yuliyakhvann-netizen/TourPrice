import asyncio, httpx

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        for action in ['TOWNSTO', 'RESORT', 'RESORTS', 'HOTELS', 'HOTEL', 'HOTELSEARCH', 'TOWNSSEARCH']:
            r = await client.get('https://online.kz.kompastour.com/search_tour',
                params={'samo_action': action, 'TOWNFROMINC': 9, 'STATEINC': 32})
            has_inc = 'inc:' in r.text
            print('%s: status=%d has_inc=%s len=%d' % (action, r.status_code, has_inc, len(r.text)))

asyncio.run(test())
