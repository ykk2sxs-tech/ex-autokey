"""เปิดหน้าจอจริง โหลดไฟล์ตัวอย่าง และตรวจสอบข้อมูล (ข้ามถ้าเครื่องไม่มีจอ/tkinter)"""

import os
import sys

import pytest

tk = pytest.importorskip("tkinter")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def app():
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        pytest.skip("ไม่มีจอแสดงผล")
    from exautokey.gui.app import App

    try:
        a = App()
    except tk.TclError as exc:
        pytest.skip(f"เปิดหน้าจอไม่ได้: {exc}")
    a.withdraw()
    yield a
    a.destroy()


def test_load_sample_and_check(app):
    app.pages["data"].load(os.path.join(ROOT, "samples", "01-ขายเงินสด.csv"))
    files = [os.path.basename(t.path) for t in app.templates]
    app.select_template(files.index("01-ขายเงินสด.json"))
    for page in ("template", "run", "data"):
        app.show_page(page)
    plan = app.pages["run"].check()
    assert plan is not None and plan.ok
    assert len(plan.docs) == 3
    assert app.nav["run"].sub.cget("text").startswith("พร้อมคีย์ 3")


def test_template_edit_invalidates_plan(app):
    app.pages["data"].load(os.path.join(ROOT, "samples", "01-ขายเงินสด.csv"))
    app.pages["run"].check()
    assert app.plan is not None
    app.pages["template"].window_var.set("Express X")
    assert app.plan is None
    assert app.template_dirty
