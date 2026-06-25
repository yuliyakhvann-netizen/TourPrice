import asyncio, httpx, re

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get('https://online.kz.kompastour.com/search_tour',
            params={'samo_action': 'INIT', 'TOWNFROMINC': 9})
        idx = r.text.find('STATEINC')
        end = r.text.find(']);', idx)
        block = r.text[idx:end]
        countries = re.findall(r"inc: '(\d+)', title: '([^']+)'", block)
        print('Total countries: %d' % len(countries))
        for inc, title in countries:
            print('  %s: %s' % (inc, title))

asyncio.run(test())
