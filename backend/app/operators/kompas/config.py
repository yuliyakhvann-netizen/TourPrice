"""
Kompas-specific constants confirmed by observing real captured traffic.

This is deliberately NOT a city/country code mapping table - that's a
separate, larger piece of infrastructure (per-operator, living in the
DB per the original spec's city_code_mapping / country_code_mapping
design, since codes differ between operators) that hasn't been built
yet. These are just the handful of values we've actually verified,
kept here so connector.py doesn't have magic numbers scattered through it.
"""

BASE_URL = "https://online.kz.kompastour.com"

TOWN_FROM_ALMATY = 9
STATE_VIETNAM = 32

# Kompas-specific search defaults — differ from FunSun:
# CURRENCY=1 (KZT), FILTER=1 (confirmed via DevTools — 0 causes HTML response),
# PARTITION_PRICE=160
CURRENCY_KZT = 1
FILTER_DEFAULT = 1
PARTITION_PRICE_DEFAULT = 160