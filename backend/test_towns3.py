import asyncio, httpx, re

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get('https://online.kz.kompastour.com/search_tour',
            params={
                'samo_action': 'TOWNS',
                'TOWNFROMINC': 9,
                'STATEINC': 32,
                'FREIGHTTYPE': 0,
                'TOURINC': 0,
                'PROGRAMGROUPINC': 0,
                'CHECKIN_BEG': '20260624',
                'NIGHTS_FROM': 5,
                'CHECKIN_END': '20260625',
                'NIGHTS_TILL': 14,
                'ADULT': 2,
                'CURRENCY': 1,
                'CHILD': 0,
                'TOWNS_ANY': 1,
                'HOTELS_ANY': 1,
                'MEALS_ANY': 1,
                'ROOMS_ANY': 1,
                'FREIGHT': 1,
                'FILTER': 1,
                'PARTITION_PRICE': 160,
            })
        print('Length:', len(r.text))
        controls = re.findall(r'controls\.(\w+)\)\.addOptions', r.text)
        print('Controls:', list(set(controls)))
        
        if 'controls.TOWNS' in r.text:
            idx = r.text.find('controls.TOWNS')
            end = r.text.find(']);', idx)
            block = r.text[idx:end]
            towns = re.findall(r"inc: '(\d+)', title: '([^']+)'", block)
            print('Towns (%d):' % len(towns))
            for inc, title in towns[:20]:
                print('  %s: %s' % (inc, title))
        else:
            print('No TOWNS control found')

asyncio.run(test())
