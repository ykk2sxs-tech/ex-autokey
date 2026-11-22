"""แปลงค่าจากไฟล์ข้อมูลให้อยู่ในรูปแบบที่จะพิมพ์ลง Express

รูปแบบ (format spec) เป็น dict เช่น
    {"type": "text", "max_length": 20}
    {"type": "date", "pattern": "dd/mm/yy", "era": "BE"}
    {"type": "number", "decimals": 2, "thousands": false}
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


class FormatError(ValueError):
    """แปลงค่าไม่ได้"""


DATE_PATTERNS = ["dd/mm/yy", "dd/mm/yyyy", "ddmmyy", "ddmmyyyy", "d/m/yyyy", "yyyy-mm-dd"]
FORMAT_TYPES = {"text": "ข้อความ", "date": "วันที่", "number": "ตัวเลข"}

THAI_MONTHS = {
    "มกราคม": 1, "ม.ค.": 1, "มค": 1,
    "กุมภาพันธ์": 2, "ก.พ.": 2, "กพ": 2,
    "มีนาคม": 3, "มี.ค.": 3, "มีค": 3,
    "เมษายน": 4, "เม.ย.": 4, "เมย": 4,
    "พฤษภาคม": 5, "พ.ค.": 5, "พค": 5,
    "มิถุนายน": 6, "มิ.ย.": 6, "มิย": 6,
    "กรกฎาคม": 7, "ก.ค.": 7, "กค": 7,
    "สิงหาคม": 8, "ส.ค.": 8, "สค": 8,
    "กันยายน": 9, "ก.ย.": 9, "กย": 9,
    "ตุลาคม": 10, "ต.ค.": 10, "ตค": 10,
    "พฤศจิกายน": 11, "พ.ย.": 11, "พย": 11,
    "ธันวาคม": 12, "ธ.ค.": 12, "ธค": 12,
}

EXCEL_EPOCH = dt.date(1899, 12, 30)


def is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def to_text(value: object) -> str:
    """แปลงค่าใด ๆ เป็นข้อความแบบไม่เปลี่ยนความหมาย"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, float):
        return _plain(Decimal(repr(value)))
    if isinstance(value, Decimal):
        return _plain(value)
    return str(value).strip()


def _plain(d: Decimal) -> str:
    s = f"{d:f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s


# ---------------------------------------------------------------- ตัวเลข

def parse_number(value: object) -> Decimal:
    if isinstance(value, bool):
        raise FormatError("ค่าเป็น TRUE/FALSE ไม่ใช่ตัวเลข")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, Decimal):
        return value
    s = to_text(value)
    raw = s
    for ch in (",", " ", " ", "฿", "บาท"):
        s = s.replace(ch, "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    elif s.endswith("-") and len(s) > 1:
        neg, s = True, s[:-1]
    if not s:
        raise FormatError("ค่าว่าง")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise FormatError(f"\"{raw}\" ไม่ใช่ตัวเลข") from None
    if not d.is_finite():
        raise FormatError(f"\"{raw}\" ไม่ใช่ตัวเลข")
    return -d if neg else d


def round_number(d: Decimal, decimals: int | None) -> Decimal:
    if decimals is None:
        return d
    d = d.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)
    return d


def format_number(value: object, decimals: int | None = 2, thousands: bool = False) -> str:
    d = round_number(parse_number(value), decimals)
    if decimals is None:
        s = _plain(d)
        if thousands:
            whole, _, frac = s.partition(".")
            s = f"{int(whole):,}" + (f".{frac}" if frac else "")
            if whole == "-0":
                s = "-" + s
        return s
    return f"{d:,f}" if thousands else f"{d:f}"


# ---------------------------------------------------------------- วันที่

_ISO = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_DMY = re.compile(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})")
_THAI = re.compile(r"(\d{1,2})\s*([ก-๙.]+)\s*(\d{4}|\d{2})")


def _year_to_ce(y: int, digits: int) -> int:
    if digits == 4:
        return y - 543 if y >= 2400 else y
    # ปี 2 หลัก: 40-99 ถือเป็น พ.ศ. 25xx, 00-39 ถือเป็น ค.ศ. 20xx
    return 2500 + y - 543 if y >= 40 else 2000 + y


def parse_date(value: object) -> dt.date:
    if isinstance(value, dt.datetime):
        d = value.date()
    elif isinstance(value, dt.date):
        d = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        # เลขวันที่แบบ Excel (serial number)
        if not 1 <= value < 2958466:
            raise FormatError(f"\"{value}\" ไม่ใช่วันที่")
        d = EXCEL_EPOCH + dt.timedelta(days=int(value))
    else:
        s = to_text(value)
        if not s:
            raise FormatError("ค่าว่าง")
        date_part = re.split(r"[ T]", s, maxsplit=1)[0] if _ISO.match(s) else s
        y = m = dd = None
        if mt := _ISO.fullmatch(date_part):
            y, m, dd = int(mt[1]), int(mt[2]), int(mt[3])
            y = _year_to_ce(y, 4)
        elif mt := _DMY.fullmatch(re.split(r"\s+", s, maxsplit=1)[0]):
            dd, m = int(mt[1]), int(mt[2])
            y = _year_to_ce(int(mt[3]), len(mt[3]))
        elif mt := _THAI.fullmatch(s):
            month_key = mt[2].strip()
            if month_key not in THAI_MONTHS:
                raise FormatError(f"ไม่รู้จักชื่อเดือน \"{month_key}\"")
            dd, m = int(mt[1]), THAI_MONTHS[month_key]
            y = _year_to_ce(int(mt[3]), len(mt[3]))
        else:
            raise FormatError(f"\"{s}\" ไม่ใช่วันที่ (ใช้ วว/ดด/ปปปป หรือ ปปปป-ดด-วว)")
        try:
            d = dt.date(y, m, dd)
        except ValueError:
            raise FormatError(f"\"{s}\" ไม่ใช่วันที่ที่มีอยู่จริง") from None
    if not 1950 <= d.year <= 2150:
        raise FormatError(f"ปี ค.ศ. {d.year} ผิดปกติ ตรวจสอบว่าใส่ปี พ.ศ./ค.ศ. ถูกต้อง")
    return d


_DATE_TOKEN = re.compile(r"yyyy|yy|dd|mm|d|m")


def format_date(value: object, pattern: str = "dd/mm/yyyy", era: str = "CE") -> str:
    d = parse_date(value)
    year = d.year + (543 if era.upper() == "BE" else 0)

    def repl(mt: re.Match) -> str:
        tok = mt.group(0)
        return {
            "yyyy": f"{year:04d}",
            "yy": f"{year % 100:02d}",
            "dd": f"{d.day:02d}",
            "d": str(d.day),
            "mm": f"{d.month:02d}",
            "m": str(d.month),
        }[tok]

    return _DATE_TOKEN.sub(repl, pattern)


# ---------------------------------------------------------------- รวม

def normalize_spec(spec: dict | None) -> dict:
    spec = dict(spec or {})
    spec.setdefault("type", "text")
    if spec["type"] not in FORMAT_TYPES:
        raise FormatError(f"ไม่รู้จักรูปแบบ \"{spec['type']}\"")
    return spec


def apply_format(value: object, spec: dict | None) -> str:
    spec = normalize_spec(spec)
    kind = spec["type"]
    if kind == "date":
        return format_date(value, spec.get("pattern", "dd/mm/yyyy"), spec.get("era", "CE"))
    if kind == "number":
        decimals = spec.get("decimals", 2)
        return format_number(value, None if decimals in (None, "") else int(decimals), bool(spec.get("thousands", False)))
    text = to_text(value)
    max_len = spec.get("max_length")
    if max_len and len(text) > int(max_len):
        raise FormatError(f"ยาว {len(text)} ตัวอักษร เกินที่กำหนด {max_len}")
    return text


def describe_spec(spec: dict | None) -> str:
    try:
        spec = normalize_spec(spec)
    except FormatError as exc:
        return str(exc)
    kind = spec["type"]
    if kind == "date":
        era = "พ.ศ." if spec.get("era", "CE").upper() == "BE" else "ค.ศ."
        return f"วันที่ {spec.get('pattern', 'dd/mm/yyyy')} {era}"
    if kind == "number":
        dec = spec.get("decimals", 2)
        dec_txt = "ตามต้นฉบับ" if dec in (None, "") else f"{dec} ตำแหน่ง"
        return (f"ตัวเลข {dec_txt}" + (" มีคอมมา" if spec.get("thousands") else "")
                + (" · รวมยอด" if spec.get("total") else ""))
    if spec.get("max_length"):
        return f"ข้อความ ≤{spec['max_length']} ตัว"
    return "ข้อความ"
