"""Exact decimal arithmetic helpers for monetary values."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import TypeAlias

from bson.decimal128 import Decimal128

DecimalInput: TypeAlias = Decimal | Decimal128 | int | str
_CENT = Decimal("0.01")
_ONE_HUNDRED = Decimal("100")


def to_decimal(value: DecimalInput) -> Decimal:
    """Convert an exact numeric input to a finite Decimal; floats are rejected."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("Money values must not use float or bool.")
    if isinstance(value, Decimal128):
        result = value.to_decimal()
    elif isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Money value is not a valid decimal.") from exc
    else:
        raise TypeError("Money value must be Decimal, Decimal128, int, or str.")

    if not result.is_finite():
        raise ValueError("Money value must be finite.")
    return result


def quantize_money(value: DecimalInput) -> Decimal:
    """Round a monetary amount to two decimal places using ROUND_HALF_UP."""
    try:
        return to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Money value cannot be represented to two decimal places.") from exc


def to_decimal128(value: DecimalInput) -> Decimal128:
    """Convert an exact numeric value to BSON Decimal128 without using floats."""
    try:
        return Decimal128(to_decimal(value))
    except InvalidOperation as exc:
        raise ValueError("Money value cannot be represented as Decimal128.") from exc


def from_decimal128(value: Decimal128) -> Decimal:
    """Convert a BSON Decimal128 value to Python Decimal."""
    if not isinstance(value, Decimal128):
        raise TypeError("Expected a BSON Decimal128 value.")
    return to_decimal(value)


def line_total(unit_price: DecimalInput, quantity: DecimalInput) -> Decimal:
    """Calculate and round the total for a non-negative unit price and quantity."""
    price = to_decimal(unit_price)
    count = to_decimal(quantity)
    if price < 0 or count < 0:
        raise ValueError("Unit price and quantity must not be negative.")
    try:
        return quantize_money(price * count)
    except InvalidOperation as exc:
        raise ValueError("Line total cannot be represented as money.") from exc


def apply_discount(amount: DecimalInput, discount_percent: DecimalInput) -> Decimal:
    """Apply a percentage discount from 0 to 100 and round the result."""
    total = to_decimal(amount)
    discount = to_decimal(discount_percent)
    if total < 0:
        raise ValueError("Amount must not be negative.")
    if discount < 0 or discount > _ONE_HUNDRED:
        raise ValueError("Discount percent must be between 0 and 100.")
    return quantize_money(total * (_ONE_HUNDRED - discount) / _ONE_HUNDRED)


def apply_tax(amount: DecimalInput, tax_percent: DecimalInput) -> Decimal:
    """Add a non-negative percentage tax to an amount and round the result."""
    total = to_decimal(amount)
    tax = to_decimal(tax_percent)
    if total < 0 or tax < 0:
        raise ValueError("Amount and tax percent must not be negative.")
    return quantize_money(total * (_ONE_HUNDRED + tax) / _ONE_HUNDRED)
