"""
FunSun-specific constants confirmed by observing real captured traffic.

Same caveat as kompas/config.py: this is NOT a city/country code
mapping table - that's the city_mapping / country_mapping DB
infrastructure. These are just the handful of values verified so far,
so connector.py doesn't have magic numbers scattered through it.
"""

BASE_URL = "https://b2b.fstravel.asia"

# Confirmed by observation in captured DevTools traffic (samo_action=PRICES,
# 200 OK, real price rows returned) - NOT a complete mapping.
TOWN_FROM_ALMATY = 367408
STATE_VIETNAM = 293645  # seen on Nha Trang / Cam Ranh searches