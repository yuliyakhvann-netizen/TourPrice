import asyncio, httpx, re

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Пробуем получить курорты для Вьетнама (32)
        r = await client.get('https://online.kz.kompastour.com/search_tour',
            params={
                'samo_action': 'TOWNS',
                'TOWNFROMINC': 9,
                'STATEINC': 32,
            })
        print('TOWNS status:', r.status_code)
        print('first 1000:', r.text[:1000])

asyncio.run(test())
