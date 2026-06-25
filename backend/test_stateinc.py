import asyncio, httpx, re

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get('https://online.kz.kompastour.com/search_tour',
            params={
                'samo_action': 'STATEINC',
                'TOWNFROMINC': 9,
                'STATEINC': 32,
                'FREIGHTTYPE': 0,
                'CHECKIN_BEG': '20260624',
                'NIGHTS_FROM': 5,
                'CHECKIN_END': '20260625',
                'NIGHTS_TILL': 15,
                'ADULT': 2,
                'CHILD': 0,
            })
        print('Length:', len(r.text))
        # Ищем все addOptions блоки
        controls = re.findall(r'controls\.(\w+)\)\.addOptions', r.text)
        print('Controls with addOptions:', list(set(controls)))
        
        # Ищем все inc/title пары
        all_options = re.findall(r"inc: '(\d+)', title: '([^']+)'", r.text)
        # Фильтруем — только не числовые title (не ночи/взрослые)
        non_numeric = [(inc, title) for inc, title in all_options if not title.isdigit()]
        print('Non-numeric options (%d):' % len(non_numeric))
        for inc, title in non_numeric[:30]:
            print('  %s: %s' % (inc, title))

asyncio.run(test())
