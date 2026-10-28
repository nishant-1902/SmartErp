from decimal import Decimal

import pytest
from bson.decimal128 import Decimal128

from common.money import (
    apply_discount,
    apply_tax,
    from_decimal128,
    line_total,
    quantize_money,
    to_decimal,
    to_decimal128,
)


def test_decimal_arithmetic_avoids_float_precision_errors():
    result = to_decimal("0.1") + to_decimal("0.2")

    assert result == Decimal("0.3")
    assert line_total("0.1", 3) == Decimal("0.30")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1.005", Decimal("1.01")), ("1.004", Decimal("1.00")), ("-1.005", Decimal("-1.01"))],
)
def test_quantize_money_uses_half_up_rounding(value, expected):
    assert quantize_money(value) == expected


@pytest.mark.parametrize("value", [0.1, True, Decimal("NaN"), Decimal("Infinity"), "bad"])
def test_to_decimal_rejects_float_boolean_non_finite_and_invalid_values(value):
    with pytest.raises((TypeError, ValueError)):
        to_decimal(value)


def test_decimal128_conversion_round_trip():
    stored = to_decimal128("123.45")

    assert isinstance(stored, Decimal128)
    assert from_decimal128(stored) == Decimal("123.45")


def test_line_total_rejects_negative_values():
    with pytest.raises(ValueError):
        line_total("-1.00", 2)


def test_discount_then_tax_applies_tax_to_discounted_price():
    discounted = apply_discount("100.00", "10")

    assert discounted == Decimal("90.00")
    assert apply_tax(discounted, "10") == Decimal("99.00")


@pytest.mark.parametrize("discount", ["-1", "100.01"])
def test_discount_rejects_rates_outside_zero_to_one_hundred(discount):
    with pytest.raises(ValueError):
        apply_discount("100", discount)


def test_tax_rejects_negative_rate():
    with pytest.raises(ValueError):
        apply_tax("100", "-1")
