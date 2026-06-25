"""
Quick validation of parser.py against realistic SAMO response shapes:
  1. The literal "no results" response (real sample, byte-for-byte).
  2. A constructed-but-realistic "results found" response: real <tr> rows
     taken from an actual Kompas response, re-wrapped through json.dumps
     to simulate the wire-format JSON escaping SAMO actually sends, so
     the test exercises extract_html_from_response() honestly rather than
     skipping straight to parsing already-clean HTML.
"""

import json

from app.operators.samo.parser import parse_samo_prices_response


# ---------------------------------------------------------------------
# Fixture 1: real "no results" response, byte-for-byte as received.
# ---------------------------------------------------------------------
EMPTY_RESPONSE = r"""(function() {
    if (typeof samo === "undefined") {
        samo = {};
    }
    samo.current_request = null;
    samo.ROOT_URL = "\/search_tour?";
    logonTypePriority = "agency";
    if (typeof samo != "undefined" && typeof samo.search_key != "undefined") {
        samo.search_key(null);
    }
    ;samo.jQuery(samo.controls.resultset).ehtml("                                        \u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445. \u0423\u0442\u043e\u0447\u043d\u0438\u0442\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u043f\u043e\u0438\u0441\u043a\u0430.\n                        ");
    samo.initResultset();
}
)();"""


# ---------------------------------------------------------------------
# Fixture 2: real rows (copied from an actual Kompas PRICES response),
# wrapped in a minimal table + pager, then run through json.dumps to
# produce realistic JSON-escaped wire content.
# ---------------------------------------------------------------------
SAMPLE_TABLE_HTML = """<table class="res">
<thead><tr><th>Заезд</th><th>Тур</th></tr></thead>
<tbody>
<tr class="even price_info white_row stats stateFromKey-7 townFromKey-9 stateKey-32 checkIn-20260930 nights-7 hnights-6 tourKey-8534 spoKey-105340 programTypeKey-1 hotelKey-51474 htPlaceKey-4 roomKey-1118 mealKey-4 adult-2 child-0"
    data-townfrom="9" data-state="32"
    data-checkin="20260930" data-nights="7"
    data-hnights="6" data-cat-claim="0xDEADBEEF" data-packet-type="0"
    data-hotel="51474" data-statefrom="7"
    data-hotel-lat="" data-hotel-lng=""
    data-tour="8534" data-ptype="1" data-meal="4"
    data-room="1118" data-htplace="4">
    <td><div class="btn-group"></div></td>
    <td class="sortie transp_icon_1">
        <div class="samo_format_date" data-date="30.09.2026" data-lang="ru">30.09.2026</div>
        <span class="helpalt" data-popup="вылеты">22:35</span>
    </td>
    <td class="tour">VN: Фукуок из Алматы (BLOCK)<br><span class="icon tr tr_8534"></span></td>
    <td class="c">6<span class="helpalt price-additional-nights" data-popup="ночей в дороге">+1</span></td>
    <td class="link-hotel">SK Hotel Phu Quoc 2*\n(Фукуок)</td>
    <td class="nw"><span class="hotel_availability hotel_availability_R"></span></td>
    <td>BB</td>
    <td><span class="">Superior Garden View / DBL</span></td>
    <td class="r nw attributes"><span class="marker">&nbsp;</span></td>
    <td class="c nw statistic"><span class="stats helpalt">&nbsp;</span></td>
    <td class="td_price">
        <span data-cat-price="1378.79" data-cat-price_old="" data-converted_price_old=""
              data-cat-currency="2" data-converted-price-number="685259"
              data-currency="1" data-currency_title="KZT"
              class="price expand price_button">685&#8239;259&nbsp;KZT</span>
    </td>
    <td><span class="percent helpalt icon-info" data-popup="посмотреть скидки"></span></td>
    <td></td>
    <td class="type_price"><span class="all_prices">ALA-PQC_124_VJ66, VSV5314</span></td>
    <td class="nw transport"><div class="transport"><span class="name">Эконом</span></div></td>
</tr>
<tr class="odd price_info red_row stats stateFromKey-7 townFromKey-9 stateKey-32 checkIn-20260930 nights-7 hnights-6 tourKey-8534 spoKey-105340 programTypeKey-1 hotelKey-51540 htPlaceKey-4 roomKey-67345 mealKey-4 adult-2 child-0"
    data-townfrom="9" data-state="32"
    data-checkin="20260930" data-nights="7"
    data-hnights="6" data-cat-claim="0xDEADBEEF2" data-packet-type="0"
    data-hotel="51540" data-statefrom="7"
    data-hotel-lat="" data-hotel-lng=""
    data-tour="8534" data-ptype="1" data-meal="4"
    data-room="67345" data-htplace="4">
    <td><div class="btn-group"></div></td>
    <td class="sortie transp_icon_1">
        <div class="samo_format_date" data-date="30.09.2026" data-lang="ru">30.09.2026</div>
        <span class="helpalt" data-popup="вылеты">22:35</span>
    </td>
    <td class="tour">VN: Фукуок из Алматы (BLOCK)<br><span class="icon tr tr_8534"></span></td>
    <td class="c">6<span class="helpalt price-additional-nights" data-popup="ночей в дороге">+1</span></td>
    <td class="link-hotel">Sun and Sea Hotel 3*\n(Фукуок)</td>
    <td class="nw"><span class="hotel_availability hotel_availability_N"></span></td>
    <td>BB</td>
    <td><span class="">Deluxe Double Garden View / DBL</span></td>
    <td class="r nw attributes"><span class="marker">&nbsp;</span></td>
    <td class="c nw statistic"><span class="stats helpalt">&nbsp;</span></td>
    <td class="td_price">
        <span data-cat-price="1418.79" data-cat-price_old="" data-converted_price_old=""
              data-cat-currency="2" data-converted-price-number="705139"
              data-currency="1" data-currency_title="KZT"
              class="price stop" title="Остановка продаж на проживание с 26.03.2026 по 31.12.2026">705&#8239;139&nbsp;KZT</span>
    </td>
    <td></td>
    <td></td>
    <td class="type_price"><span class="all_prices">ALA-PQC_124_VJ66, VSV5314</span></td>
    <td class="nw transport"><div class="transport"><span class="name">Эконом</span></div></td>
</tr>
<tr class="even price_info white_row stats stateFromKey-7 townFromKey-9 stateKey-32 checkIn-20260930 nights-7 hnights-6 tourKey-8534 spoKey-105340 programTypeKey-1 hotelKey-47458 htPlaceKey-4 roomKey-2161 mealKey-4 adult-2 child-0"
    data-townfrom="9" data-state="32"
    data-checkin="20260930" data-nights="7"
    data-hnights="6" data-cat-claim="0xDEADBEEF3" data-packet-type="0"
    data-hotel="47458" data-statefrom="7"
    data-hotel-lat="" data-hotel-lng=""
    data-tour="8534" data-ptype="1" data-meal="4"
    data-room="2161" data-htplace="4">
    <td><div class="btn-group"></div></td>
    <td class="sortie transp_icon_1">
        <div class="samo_format_date" data-date="30.09.2026" data-lang="ru">30.09.2026</div>
        <span class="helpalt" data-popup="вылеты">22:35</span>
    </td>
    <td class="tour">VN: Фукуок из Алматы (BLOCK)<br><span class="icon tr tr_8534"></span></td>
    <td class="c">6<span class="helpalt price-additional-nights" data-popup="ночей в дороге">+1</span></td>
    <td class="link-hotel"><a href="https://kompastour.com/hotel_redirect.php?redirect_url=/vietnam/fukuok/tahiti_central_hotel/" target="_blank">Tahiti Central Hotel, 3*</a>\n(Duong Dong)</td>
    <td class="nw"><span class="hotel_availability hotel_availability_R"></span></td>
    <td>BB</td>
    <td><span class="">SUPERIOR CITY VIEW / DBL</span></td>
    <td class="r nw attributes"><span class="marker">&nbsp;</span></td>
    <td class="c nw statistic"><span class="stats helpalt">&nbsp;</span></td>
    <td class="td_price">
        <span data-cat-price="1415.06" data-cat-price_old="" data-converted_price_old=""
              data-cat-currency="2" data-converted-price-number="703285"
              data-currency="1" data-currency_title="KZT"
              class="price expand price_button">703&#8239;285&nbsp;KZT</span>
    </td>
    <td><span class="percent helpalt icon-info" data-popup="посмотреть скидки"></span></td>
    <td></td>
    <td class="type_price"><span class="all_prices">ALA-PQC_124_VJ66, VSV5314</span></td>
    <td class="nw transport"><div class="transport"><span class="name">Эконом</span></div></td>
</tr>
</tbody>
</table>
<div class="pager">
    <span class="current_page">1</span>
    <span class="page" data-page="2">2</span>
    <span class="page" data-page="3">3</span>
    <span class="page" data-page="7">7</span>
</div>
"""

SAMPLE_RESPONSE = (
    '(function() {\n'
    '    samo.jQuery(samo.controls.resultset).ehtml(' + json.dumps(SAMPLE_TABLE_HTML) + ');\n'
    '    samo.initResultset();\n'
    '}\n'
    ')();'
)


def run_test(name: str, raw_response: str):
    print(f"\n=== {name} ===")
    result = parse_samo_prices_response(raw_response)
    print(f"empty: {result['empty']}")
    print(f"error: {result['error']}")
    print(f"pagination: {result['pagination']}")
    print(f"row count: {len(result['rows'])}")
    for i, row in enumerate(result["rows"]):
        print(f"\n--- row {i} ---")
        for k, v in row.items():
            print(f"  {k}: {v}")
    return result


if __name__ == "__main__":
    empty_result = run_test("Empty response", EMPTY_RESPONSE)
    assert empty_result["empty"] is True
    assert empty_result["rows"] == []
    print("\n[OK] empty response handled correctly")

    sample_result = run_test("Sample response (3 rows)", SAMPLE_RESPONSE)
    assert sample_result["empty"] is False
    assert len(sample_result["rows"]) == 3
    assert sample_result["pagination"] == {"current_page": 1, "total_pages": 7, "pages": [1, 2, 3, 7]}

    row0, row1, row2 = sample_result["rows"]
    assert row0["hotel_id"] == 51474
    assert row0["hotel_name_raw"] == "SK Hotel Phu Quoc 2*"
    assert row0["location_name"] == "Фукуок"
    assert row0["stars"] == 2
    assert row0["room_name_raw"] == "Superior Garden View"
    assert row0["occupancy_code"] == "DBL"
    assert row0["meal_code"] == "BB"
    assert row0["price_value"] == 685259.0
    assert row0["price_currency_title"] == "KZT"
    assert row0["is_bookable"] is True
    assert row0["checkin_date"] == "20260930"
    assert row0["nights"] == 7
    assert row0["hotel_nights"] == 6
    assert row0["transport_name"] == "Эконом"
    assert row0["flight_numbers"] == "ALA-PQC_124_VJ66, VSV5314"

    assert row1["hotel_id"] == 51540
    assert row1["is_bookable"] is False
    assert "Остановка продаж" in row1["sale_stop_note"]

    assert row2["hotel_id"] == 47458
    assert row2["hotel_name_raw"] == "Tahiti Central Hotel, 3*"
    assert row2["hotel_url"] == "https://kompastour.com/hotel_redirect.php?redirect_url=/vietnam/fukuok/tahiti_central_hotel/"
    assert row2["location_name"] == "Duong Dong"
    assert row2["stars"] == 3
    assert row2["is_bookable"] is True

    print("\n[OK] sample response parsed and validated correctly")
    print("\nAll tests passed.")