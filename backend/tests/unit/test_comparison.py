from decimal import Decimal

import pytest


def calc_market_stats(prices: list[Decimal]) -> dict:
    """Isolated helper — mirrors CompareService logic for unit testing."""
    if not prices:
        return {}
    return {
        "min": min(prices),
        "max": max(prices),
        "avg": sum(prices) / len(prices),
    }


def deviation_pct(operator_price: Decimal, market_avg: Decimal) -> Decimal:
    return ((operator_price - market_avg) / market_avg * 100).quantize(Decimal("0.01"))


def test_market_stats_basic():
    prices = [Decimal("100000"), Decimal("120000"), Decimal("110000")]
    stats = calc_market_stats(prices)
    assert stats["min"] == Decimal("100000")
    assert stats["max"] == Decimal("120000")
    assert stats["avg"] == Decimal("110000")


def test_market_stats_single_price():
    prices = [Decimal("99000")]
    stats = calc_market_stats(prices)
    assert stats["min"] == stats["max"] == stats["avg"] == Decimal("99000")


def test_market_stats_empty():
    assert calc_market_stats([]) == {}


def test_deviation_above_market():
    pct = deviation_pct(Decimal("115000"), Decimal("100000"))
    assert pct == Decimal("15.00")


def test_deviation_below_market():
    pct = deviation_pct(Decimal("85000"), Decimal("100000"))
    assert pct == Decimal("-15.00")


def test_deviation_at_market():
    pct = deviation_pct(Decimal("100000"), Decimal("100000"))
    assert pct == Decimal("0.00")
