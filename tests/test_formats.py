import datetime as dt
from decimal import Decimal

import pytest

from exautokey.formats import FormatError, apply_format, format_date, format_number, parse_date, parse_number


@pytest.mark.parametrize("raw,expected", [
    ("22/11/2569", dt.date(2026, 11, 22)),   # พ.ศ. 4 หลัก
    ("22/11/2026", dt.date(2026, 11, 22)),   # ค.ศ. 4 หลัก
    ("22/11/69", dt.date(2026, 11, 22)),     # พ.ศ. 2 หลัก
    ("22/11/26", dt.date(2026, 11, 22)),     # ค.ศ. 2 หลัก
    ("1-2-2569", dt.date(2026, 2, 1)),
    ("2026-11-22", dt.date(2026, 11, 22)),
    ("2569-11-22", dt.date(2026, 11, 22)),
    ("2026-11-22 00:00:00", dt.date(2026, 11, 22)),
    ("22/11/2569 10:30", dt.date(2026, 11, 22)),
    ("22 พ.ย. 69", dt.date(2026, 11, 22)),
    ("1 มกราคม 2570", dt.date(2027, 1, 1)),
    (dt.datetime(2026, 11, 22, 8, 0), dt.date(2026, 11, 22)),
    (dt.date(2026, 11, 22), dt.date(2026, 11, 22)),
    (46348, dt.date(2026, 11, 22)),          # Excel serial
])
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["31/02/2569", "abc", "", "22/13/2569", "22/11/1900", "22/11/2800"])
def test_parse_date_errors(raw):
    with pytest.raises(FormatError):
        parse_date(raw)


def test_format_date_patterns():
    d = "22/11/2569"
    assert format_date(d, "dd/mm/yy", "BE") == "22/11/69"
    assert format_date(d, "dd/mm/yyyy", "BE") == "22/11/2569"
    assert format_date(d, "ddmmyy", "BE") == "221169"
    assert format_date(d, "ddmmyyyy", "CE") == "22112026"
    assert format_date("01/02/2569", "d/m/yyyy", "CE") == "1/2/2026"
    assert format_date(d, "yyyy-mm-dd", "CE") == "2026-11-22"


@pytest.mark.parametrize("raw,expected", [
    ("1,234.56", Decimal("1234.56")),
    ("(1,000.00)", Decimal("-1000.00")),
    ("500-", Decimal("-500")),
    ("฿ 99", Decimal("99")),
    (1500, Decimal("1500")),
    (0.1, Decimal("0.1")),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_format_number_rounding_half_up():
    assert format_number("2.345", 2) == "2.35"
    assert format_number("2.344", 2) == "2.34"
    assert format_number("-2.345", 2) == "-2.35"
    assert format_number("1234567.891", 2, thousands=True) == "1,234,567.89"
    assert format_number("10", 0) == "10"
    assert format_number("-0.001", 2) == "0.00"
    assert format_number(1500.0, None) == "1500"
    assert format_number("1500.50", None) == "1500.5"
    assert format_number("1234.5", None, thousands=True) == "1,234.5"


@pytest.mark.parametrize("raw", ["abc", "", "1.2.3", True])
def test_number_errors(raw):
    with pytest.raises(FormatError):
        parse_number(raw)


def test_apply_format_text_max_length():
    assert apply_format("  C-0001 ", {"type": "text"}) == "C-0001"
    assert apply_format("ABC", {"type": "text", "max_length": 3}) == "ABC"
    with pytest.raises(FormatError):
        apply_format("ABCD", {"type": "text", "max_length": 3})
