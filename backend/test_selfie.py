import asyncio, httpx, time, re
from bs4 import BeautifulSoup

async def test():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get('https://b2b.selfietravel.kz/search_tour', params={
            'samo_action': 'PRICES', 'TOWNFROMINC': 1344, 'STATEINC': 43,
            'FREIGHTTYPE': 0, 'CHECKIN_BEG': '20260810', 'CHECKIN_END': '20260817',
            'NIGHTS_FROM': 7, 'NIGHTS_TILL': 7, 'ADULT': 2, 'CURRENCY': 1,
            'CHILD': 0, 'TOWNS_ANY': 1, 'STARS_ANY': 1, 'HOTELS_ANY': 1,
            'MEALS_ANY': 1, 'ROOMS_ANY': 1, 'FREIGHT': 1, 'FILTER': 1,
            'PARTITION_PRICE': 160, 'PRICEPAGE': 1, 'DYN_SEPARATE': 1,
            'rev': int(time.time()), '_': int(time.time()*1000),
        })
        match = re.search(r'ehtml\("(.*?)"\)', r.text, re.DOTALL)
        if not match:
            print('no ehtml found')
            return
        raw = match.group(1)
        # unescape
        content = raw.replace('\\"', '"').replace('\\/', '/').replace('\\n', '\n').replace('\\t', '\t')
        soup = BeautifulSoup(content, 'html.parser')
        rows = soup.find_all('tr', class_=re.compile('price_info'))
        print('result rows:', len(rows))
        if rows:
            cells = rows[0].find_all('td')
            print('cells count:', len(cells))
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)[:60]
                print('  cell[%d]: %r' % (i, text))

asyncio.run(test())
