from datetime import date

import pytest

from app.schemas.tour import TourKey


def make_key(**overrides) -> TourKey:
    defaults = dict(
        country="Turkey",
        departure_city="Almaty",
        departure_date=date(2026, 6, 15),
        nights=7,
        hotel="Rixos Premium Belek",
        room_type="Standard Room",
        meal_type="Ultra All Inclusive",
        airline="Air Astana",
        adults=2,
        children=0,
    )
    defaults.update(overrides)
    return TourKey(**defaults)


def test_same_tours_produce_same_hash():
    k1 = make_key()
    k2 = make_key()
    assert k1.hash() == k2.hash()


def test_different_hotel_produces_different_hash():
    k1 = make_key(hotel="Rixos Premium Belek")
    k2 = make_key(hotel="Maxx Royal Belek")
    assert k1.hash() != k2.hash()


def test_hash_is_case_insensitive():
    k1 = make_key(hotel="Rixos Premium Belek", room_type="Standard Room")
    k2 = make_key(hotel="RIXOS PREMIUM BELEK", room_type="STANDARD ROOM")
    assert k1.hash() == k2.hash()


def test_different_nights_produce_different_hash():
    assert make_key(nights=7).hash() != make_key(nights=14).hash()


def test_children_count_matters():
    assert make_key(children=0).hash() != make_key(children=1).hash()


def test_tour_key_is_hashable_for_dict():
    k = make_key()
    d = {k: 100}
    assert d[k] == 100


def test_tour_key_hash_is_16_chars():
    assert len(make_key().hash()) == 16
