from datetime import date

import pytest

from app.availability import check_availability
from app.kb import split_sources


def ids(res):
    return [r["id"] for r in res["rooms"]]


def test_three_guests_excludes_standard():
    res = check_availability(date(2026, 10, 1), date(2026, 10, 3), 3)
    assert ids(res) == ["deluxe", "family"]
    assert res["rooms"][0]["total"] == 360  # 2 nights x 180


def test_sold_out_dates_excluded():
    res = check_availability(date(2026, 12, 25), date(2026, 12, 27), 2)
    assert ids(res) == ["standard"]


def test_too_many_guests_returns_no_rooms():
    assert check_availability(date(2026, 10, 1), date(2026, 10, 2), 9)["rooms"] == []


@pytest.mark.parametrize("cin,cout,n", [
    (date(2026, 10, 3), date(2026, 10, 1), 2),
    (date(2026, 10, 1), date(2026, 10, 1), 2),
    (date(2026, 10, 1), date(2026, 10, 2), 0),
])
def test_invalid_input_raises(cin, cout, n):
    with pytest.raises(ValueError):
        check_availability(cin, cout, n)


def test_split_sources():
    assert split_sources("Hi.\nSOURCES: pool, wifi") == ("Hi.", ["pool", "wifi"])
    assert split_sources("No idea.\nSOURCES: none") == ("No idea.", [])
    assert split_sources("no line") == ("no line", [])
