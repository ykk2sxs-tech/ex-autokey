import datetime as dt

import pytest

from exautokey.data import DataError, load_csv, load_table, write_csv_header


def write(tmp_path, name, content: bytes):
    p = tmp_path / name
    p.write_bytes(content)
    return str(p)


def test_csv_utf8_bom_and_line_numbers(tmp_path):
    path = write(tmp_path, "a.csv", "﻿เลขที่,จำนวน\nA1,10\n\nA2,\"1,500.00\"\n".encode("utf-8"))
    t = load_csv(path)
    assert t.columns == ["เลขที่", "จำนวน"]
    assert [r.line for r in t.rows] == [2, 4]  # แถวว่างถูกข้าม แต่เลขแถวยังตรงกับ Excel
    assert t.rows[1].get("จำนวน") == "1,500.00"
    assert "UTF-8" in t.info


def test_csv_thai_ansi(tmp_path):
    path = write(tmp_path, "b.csv", "ชื่อ,ยอด\nทดสอบ,5\n".encode("cp874"))
    t = load_csv(path)
    assert t.columns == ["ชื่อ", "ยอด"]
    assert t.rows[0].get("ชื่อ") == "ทดสอบ"
    assert "874" in t.info


def test_csv_semicolon_and_duplicate_headers(tmp_path):
    path = write(tmp_path, "c.csv", "a;a;b\n1;2;3\n".encode("utf-8"))
    t = load_csv(path)
    assert t.columns == ["a", "a_2", "b"]
    assert t.rows[0].values == {"a": "1", "a_2": "2", "b": "3"}


def test_csv_extra_values_is_error(tmp_path):
    path = write(tmp_path, "d.csv", "a,b\n1,2,3\n".encode("utf-8"))
    with pytest.raises(DataError):
        load_csv(path)


def test_select_range(tmp_path):
    path = write(tmp_path, "e.csv", "a\n1\n2\n3\n4\n".encode("utf-8"))
    t = load_csv(path)
    assert [r.get("a") for r in t.select(3, 4)] == ["2", "3"]
    assert len(t.select()) == 4


def test_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ข้อมูล"
    ws.append([])  # แถวว่างด้านบน
    ws.append(["เลขที่", "วันที่", "ยอด"])
    ws.append(["X1", dt.date(2026, 11, 22), 1234.5])
    wb.create_sheet("อื่น")
    p = str(tmp_path / "f.xlsx")
    wb.save(p)
    t = load_table(p)
    assert t.columns == ["เลขที่", "วันที่", "ยอด"]
    assert t.rows[0].line == 3
    assert t.rows[0].get("ยอด") == 1234.5
    assert t.rows[0].get("วันที่").date() == dt.date(2026, 11, 22)
    assert t.sheets == ["ข้อมูล", "อื่น"]
    with pytest.raises(DataError):
        load_table(p, "ไม่มี")


def test_write_csv_header_roundtrip(tmp_path):
    p = str(tmp_path / "g.csv")
    write_csv_header(p, ["เลขที่", "วันที่"], [["A", "1/1/2569"]])
    t = load_csv(p)
    assert t.columns == ["เลขที่", "วันที่"]
    assert t.rows[0].get("เลขที่") == "A"
