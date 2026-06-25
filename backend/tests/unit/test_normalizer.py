import pytest

# Isolated normalizer logic for unit testing without DB
ROOM_DICT = {
    "standard room": "Standard Room",
    "std room": "Standard Room",
    "standard dbl": "Standard Room",
    "standard": "Standard Room",
    "deluxe room": "Deluxe Room",
    "suite": "Suite",
}

MEAL_DICT = {
    "uai": "Ultra All Inclusive",
    "uall": "Ultra All Inclusive",
    "ultra all inclusive": "Ultra All Inclusive",
    "ai": "All Inclusive",
    "all inclusive": "All Inclusive",
    "hb": "Half Board",
}


def normalize_value(raw: str, mapping: dict[str, str], threshold: float = 80.0) -> str | None:
    from rapidfuzz import process
    key = raw.lower().strip()
    if key in mapping:
        return mapping[key]
    match = process.extractOne(key, mapping.keys(), score_cutoff=threshold)
    if match:
        return mapping[match[0]]
    return None


def test_exact_room_match():
    assert normalize_value("Standard Room", ROOM_DICT) == "Standard Room"


def test_fuzzy_room_match():
    assert normalize_value("STD ROOM", ROOM_DICT) == "Standard Room"


def test_fuzzy_meal_match():
    assert normalize_value("UAI", MEAL_DICT) == "Ultra All Inclusive"


def test_all_inclusive_variants():
    for raw in ["AI", "All Inclusive", "all inclusive"]:
        assert normalize_value(raw, MEAL_DICT) == "All Inclusive"


def test_uai_variants():
    for raw in ["UAI", "UALL", "Ultra All Inclusive"]:
        assert normalize_value(raw, MEAL_DICT) == "Ultra All Inclusive"


def test_unknown_value_returns_none():
    result = normalize_value("XYZUNKNOWN123", ROOM_DICT, threshold=90.0)
    assert result is None


def test_standard_dbl_maps_to_standard_room():
    assert normalize_value("STANDARD DBL", ROOM_DICT) == "Standard Room"
