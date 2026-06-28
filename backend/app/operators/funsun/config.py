"""
FunSun-specific constants confirmed by observing real captured traffic.
BASE_URL: https://b2b.fstravel.asia
TOWN_FROM_ALMATY=367408, CURRENCY=11 (KZT), PARTITION_PRICE=224, FILTER=1
ВАЖНО: FunSun принимает максимум 10 дней в одном запросе (CHECKIN_BEG..CHECKIN_END).
"""

BASE_URL = "https://b2b.fstravel.asia"

OPERATOR_CODE = "funsun"

TOWN_FROM_ALMATY = 367408

STATE_VIETNAM = 293645  # Вьетнам (Нячанг / Камрань)

# Все страны из HTML <select name="STATEINC"> (samo_id → normalized_value)
COUNTRIES = {
    293645: "Вьетнам",
    18498:  "Египет",
    230826: "Китай",
    20613:  "ОАЭ",
    18803:  "Турция",
}

CURRENCY_KZT = 11       # 11 = KZT у FunSun (отличается от других операторов!)
FILTER_DEFAULT = 1      # confirmed via DevTools
PARTITION_PRICE_DEFAULT = 224  # confirmed via DevTools

MAX_DATE_WINDOW_DAYS = 10  # FunSun возвращает ошибку если интервал > 10 дней