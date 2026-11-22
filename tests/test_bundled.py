"""เทมเพลตและไฟล์ตัวอย่างที่มากับโปรแกรมต้องใช้คู่กันได้โดยไม่มีข้อผิดพลาด"""

import os

import pytest

from exautokey.data import load_table
from exautokey.engine import build_plan
from exautokey.template import Template, list_templates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
SAMPLES = os.path.join(ROOT, "samples")
NAMES = sorted(f[:-5] for f in os.listdir(TEMPLATES) if f.endswith(".json"))


def test_all_templates_load():
    templates, errors = list_templates(TEMPLATES)
    assert errors == []
    assert len(templates) == len(NAMES) == 10


@pytest.mark.parametrize("name", NAMES)
def test_template_matches_sample(name):
    t = Template.load(os.path.join(TEMPLATES, name + ".json"))
    table = load_table(os.path.join(SAMPLES, name + ".csv"))
    assert table.columns == t.columns_used()
    plan = build_plan(t, table)
    assert plan.ok, [i.message for i in plan.issues]
    assert plan.docs


def test_xlsx_sample_matches_csv_sample():
    t = Template.load(os.path.join(TEMPLATES, "02-ขายเงินเชื่อ.json"))
    a = build_plan(t, load_table(os.path.join(SAMPLES, "02-ขายเงินเชื่อ.csv")))
    b = build_plan(t, load_table(os.path.join(SAMPLES, "02-ขายเงินเชื่อ.xlsx")))
    assert a.ok and b.ok
    assert a.totals == b.totals
    assert [d.actions for d in a.docs] == [d.actions for d in b.docs]


def test_roundtrip_save(tmp_path):
    t = Template.load(os.path.join(TEMPLATES, "07-ซื้อเงินเชื่อ-VAT.json"))
    p = str(tmp_path / "x.json")
    t.save(p)
    t2 = Template.load(p)
    assert t2.to_dict() == t.to_dict()
