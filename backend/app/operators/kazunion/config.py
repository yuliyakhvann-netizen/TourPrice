"""
Kazunion operator configuration.
САМО-based, no login required.
Confirmed via DevTools: TOWNFROMINC=57 (Алматы), CURRENCY=2 (KZT).
"""
from __future__ import annotations

BASE_URL = "https://online.kazunion.com"

OPERATOR_CODE = "kazunion"

TOWN_FROM_ALMATY = 57  # confirmed via HTML option value
CURRENCY_KZT = 4       # 4 = KZT у Kazunion (2=USD, 3=EUR, 4=KZT)
FILTER_DEFAULT = 0
PARTITION_PRICE_DEFAULT = 232  # confirmed via DevTools

# Все страны из HTML <select name="STATEINC"> (samo_id → название)
COUNTRIES = {
    48: "Азербайджан",
    22: "Вьетнам",
    43: "Грузия",
    14: "Индонезия",
    5:  "Испания",
    95: "Катар",
    93: "Кения",
    84: "Кипр",
    19: "Китай",
    56: "Маврикий",
    13: "Малайзия",
    33: "Мальдивы",
    11: "ОАЭ",
    52: "Сейшелы",
    42: "Сингапур",
    73: "Словения",
    12: "Таиланд",
    6:  "Турция",
    69: "Черногория",
    31: "Чехия",
}