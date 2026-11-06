from decimal import Decimal

import pytest

from app.utils.money import paise_to_json_number, rupees_to_paise, split_equally


def test_rupees_to_paise_is_exact():
    assert rupees_to_paise(Decimal("1200")) == 120000
    assert rupees_to_paise(Decimal("0.01")) == 1
    assert rupees_to_paise(Decimal("19.99")) == 1999
    assert rupees_to_paise(Decimal("0.10")) + rupees_to_paise(Decimal("0.20")) == 30


def test_rupees_to_paise_rejects_sub_paisa_amounts():
    with pytest.raises(ValueError):
        rupees_to_paise(Decimal("1.005"))


def test_paise_to_json_number():
    assert paise_to_json_number(40000) == 400
    assert isinstance(paise_to_json_number(40000), int)
    assert paise_to_json_number(3333) == 33.33
    assert paise_to_json_number(-30000) == -300
    assert paise_to_json_number(-5) == -0.05


def test_equal_split_even():
    assert split_equally(120000, [1, 2, 3]) == {1: 40000, 2: 40000, 3: 40000}


def test_equal_split_distributes_remainder_to_lowest_ids():
    assert split_equally(10000, [3, 1, 2]) == {1: 3334, 2: 3333, 3: 3333}
    assert split_equally(10001, [1, 2, 3]) == {1: 3334, 2: 3334, 3: 3333}


def test_equal_split_smaller_than_participant_count():
    shares = split_equally(1, [1, 2, 3])
    assert shares == {1: 1, 2: 0, 3: 0}


@pytest.mark.parametrize("total", [1, 2, 99, 100, 101, 12345, 999_999_937])
@pytest.mark.parametrize("people", [1, 2, 3, 7, 11])
def test_equal_split_always_sums_exactly(total, people):
    shares = split_equally(total, range(1, people + 1))
    assert sum(shares.values()) == total
    assert max(shares.values()) - min(shares.values()) <= 1


def test_equal_split_requires_participants():
    with pytest.raises(ValueError):
        split_equally(100, [])
