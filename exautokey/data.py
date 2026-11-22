"""อ่านไฟล์ข้อมูล CSV / Excel (.xlsx)

เลขแถว (Row.line) นับแบบเดียวกับ Excel: แถวหัวตารางปกติคือแถว 1
ข้อมูลแถวแรกจึงเป็นแถว 2 ใช้อ้างอิงกลับไปที่ไฟล์ต้นฉบับได้ตรงกัน
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass, field

from .formats import is_empty

CSV_ENCODINGS = ("utf-8-sig", "cp874")


class DataError(Exception):
    """อ่านไฟล์ข้อมูลไม่ได้"""


@dataclass
class Row:
    line: int
    values: dict[str, object]

    def get(self, column: str) -> object:
        return self.values.get(column)


@dataclass
class Table:
    columns: list[str]
    rows: list[Row]
    source: str = ""
    info: str = ""
    header_line: int = 1
    sheets: list[str] = field(default_factory=list)

    @property
    def first_line(self) -> int | None:
        return self.rows[0].line if self.rows else None

    @property
    def last_line(self) -> int | None:
        return self.rows[-1].line if self.rows else None

    def select(self, start: int | None = None, end: int | None = None) -> list[Row]:
        return [
            r for r in self.rows
            if (start is None or r.line >= start) and (end is None or r.line <= end)
        ]


def _clean_headers(raw: list[object]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}
    for idx, h in enumerate(raw, start=1):
        name = "" if h is None else str(h).strip().replace("﻿", "")
        if not name:
            name = f"คอลัมน์{idx}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        headers.append(name)
    return headers


def _trim_trailing(values: list[object]) -> list[object]:
    out = list(values)
    while out and is_empty(out[-1]):
        out.pop()
    return out


def _build(records: list[tuple[int, list[object]]], source: str, info: str) -> Table:
    header_idx = next((i for i, (_, vals) in enumerate(records) if _trim_trailing(vals)), None)
    if header_idx is None:
        raise DataError("ไฟล์ไม่มีข้อมูล")
    header_line, header_vals = records[header_idx]
    columns = _clean_headers(_trim_trailing(header_vals))
    rows: list[Row] = []
    for line, vals in records[header_idx + 1 :]:
        if all(is_empty(v) for v in vals):
            continue
        extra = _trim_trailing(vals[len(columns) :])
        if extra:
            raise DataError(
                f"แถว {line} มีข้อมูลเกินจำนวนหัวคอลัมน์ ({len(columns)} คอลัมน์) "
                "ตรวจสอบว่าใช้ตัวคั่นถูกต้อง หรือมีเครื่องหมาย , ในตัวเลขที่ไม่ได้อยู่ในเครื่องหมายคำพูด"
            )
        values = {col: (vals[i] if i < len(vals) else None) for i, col in enumerate(columns)}
        rows.append(Row(line, values))
    return Table(columns=columns, rows=rows, source=source, info=info, header_line=header_line)


def _decode(data: bytes, encoding: str | None) -> tuple[str, str]:
    if encoding:
        return data.decode(encoding), encoding
    for enc in CSV_ENCODINGS:
        try:
            return data.decode(enc), ("UTF-8" if enc == "utf-8-sig" else "Windows-874 (ภาษาไทย ANSI)")
        except UnicodeDecodeError:
            continue
    raise DataError("อ่านภาษาไทยในไฟล์ไม่ได้ ให้บันทึกไฟล์เป็น CSV UTF-8 แล้วลองใหม่")


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def load_csv(path: str, encoding: str | None = None, delimiter: str | None = None) -> Table:
    with open(path, "rb") as fh:
        data = fh.read()
    text, enc_label = _decode(data, encoding)
    delim = delimiter or _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    records = [(n, list(rec)) for n, rec in enumerate(reader, start=1)]
    delim_label = {"\t": "Tab", ",": "จุลภาค (,)", ";": "อัฒภาค (;)", "|": "ขีดตั้ง (|)"}.get(delim, delim)
    return _build(records, path, f"CSV · {enc_label} · คั่นด้วย {delim_label}")


def _require_openpyxl():
    try:
        import openpyxl
    except ImportError:  # pragma: no cover - ขึ้นกับเครื่องผู้ใช้
        raise DataError("ต้องติดตั้ง openpyxl เพื่อเปิดไฟล์ Excel (pip install openpyxl) หรือบันทึกไฟล์เป็น CSV") from None
    return openpyxl


def list_sheets(path: str) -> list[str]:
    openpyxl = _require_openpyxl()
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def load_xlsx(path: str, sheet: str | None = None) -> Table:
    openpyxl = _require_openpyxl()
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:  # ไฟล์เสียหรือเปิดค้างใน Excel
        raise DataError(f"เปิดไฟล์ Excel ไม่ได้: {exc}") from None
    try:
        names = list(wb.sheetnames)
        if sheet and sheet not in names:
            raise DataError(f"ไม่พบชีต \"{sheet}\"")
        ws = wb[sheet] if sheet else wb.worksheets[0]
        records = [
            (n, list(vals))
            for n, vals in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True), start=1)
        ]
        table = _build(records, path, f"Excel · ชีต \"{ws.title}\"")
        table.sheets = names
        return table
    finally:
        wb.close()


def load_table(path: str, sheet: str | None = None) -> Table:
    if not os.path.exists(path):
        raise DataError(f"ไม่พบไฟล์ {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        return load_xlsx(path, sheet)
    if ext == ".xls":
        raise DataError("ไฟล์ .xls รุ่นเก่ายังไม่รองรับ ให้เปิดใน Excel แล้วบันทึกเป็น .xlsx หรือ CSV")
    return load_csv(path)


def write_csv_header(path: str, columns: list[str], example_rows: list[list[str]] | None = None) -> None:
    """สร้างไฟล์ CSV (UTF-8 BOM เปิดใน Excel ภาษาไทยได้) ที่มีหัวคอลัมน์ตามที่กำหนด"""
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for row in example_rows or []:
            w.writerow(row)
