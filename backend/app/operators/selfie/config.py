"""
Selfie Travel operator configuration.
SAMO-based, same platform as Kompas/FunSun.
Confirmed via DevTools: TOWNFROMINC=1344 (Алматы), samo_action=PRICES returns ehtml payload.
"""
from __future__ import annotations

BASE_URL = "https://b2b.selfietravel.kz"

OPERATOR_CODE = "selfie"

TOWN_FROM_ALMATY = 1344  # confirmed via INIT response

# Selfie-specific search defaults (confirmed via DevTools)
# CURRENCY=4 (KZT) — отличается от Kompas где KZT=1
CURRENCY_KZT = 4
FILTER_DEFAULT = 1
PARTITION_PRICE_DEFAULT = 160