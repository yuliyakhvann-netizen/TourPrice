import asyncio, httpx, re

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get('https://online.kz.kompastour.com/search_tour',
            params={'samo_action': 'TOWNS', 'TOWNFROMINC': 9, 'STATEINC': 32})
        
        # Ищем TOWNS controls
        if 'controls.TOWNS' in r.text:
            idx = r.text.find('controls.TOWNS')
            end = r.text.find(']);', idx)
            block = r.text[idx:end]
            towns = re.findall(r"inc: '(\d+)', title: '([^']+)'", block)
            print('Towns for Vietnam (%d):' % len(towns))
            for inc, title in towns[:20]:
                print('  %s: %s' % (inc, title))
        else:
            print('controls.TOWNS not found')
            # Что есть?
            controls = re.findall(r'controls\.(\w+)\)', r.text)
            print('Controls found:', list(set(controls)))

asyncio.run(test())
