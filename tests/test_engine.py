import threading
import time
from decimal import Decimal

import pytest

from exautokey.backends import RecordingBackend
from exautokey.data import Row, Table
from exautokey.engine import PauseHere, Runner, build_plan, render_preview, write_log
from exautokey.template import Settings, Step, Template

DATE = {"type": "date", "pattern": "dd/mm/yy", "era": "BE"}
MONEY = {"type": "number", "decimals": 2, "total": True}


def table(rows, columns=("เลขที่", "วันที่", "สินค้า", "จำนวน", "ราคา")):
    return Table(columns=list(columns), rows=[Row(i + 2, dict(zip(columns, r))) for i, r in enumerate(rows)])


def tmpl(**kw):
    t = Template(
        name="ทดสอบ",
        window_title="Express",
        group_by="เลขที่",
        header=[Step("field", "เลขที่", required=True), Step("field", "วันที่", fmt=DATE, required=True)],
        lines=[Step("field", "สินค้า"), Step("field", "จำนวน", fmt={"type": "number", "decimals": None}),
               Step("field", "ราคา", fmt=MONEY)],
        footer=[Step("keys", value="{F9}")],
        settings=Settings(key_delay_ms=0, step_delay_ms=0, doc_delay_ms=0, start_delay_s=0),
    )
    for k, v in kw.items():
        setattr(t, k, v)
    return t


ROWS = [
    ["A1", "22/11/2569", "P1", "2", "1,500"],
    ["A1", "22/11/2569", "P2", "1", "99.995"],
    ["A2", "23/11/2569", "P1", "3", "10"],
]


def test_grouping_and_actions():
    plan = build_plan(tmpl(), table(ROWS))
    assert plan.ok, plan.issues
    assert [d.key for d in plan.docs] == ["A1", "A2"]
    assert plan.docs[0].lines_text == "แถว 2–3"
    assert plan.totals["ราคา"] == Decimal("1500.00") + Decimal("100.00") + Decimal("10.00")

    be = RecordingBackend()
    r = Runner(plan, be)
    assert r.run() == "finished"
    assert be.typed() == (
        "A1<ENTER>22/11/69<ENTER>"
        "P1<ENTER>2<ENTER>1500.00<ENTER>"
        "P2<ENTER>1<ENTER>100.00<ENTER>"
        "<F9>"
        "A2<ENTER>23/11/69<ENTER>P1<ENTER>3<ENTER>10.00<ENTER><F9>"
    )
    assert [x.status for x in r.results] == ["คีย์ครบ", "คีย์ครบ"]


def test_no_grouping_one_row_per_doc():
    plan = build_plan(tmpl(group_by=""), table(ROWS))
    assert len(plan.docs) == 3


def test_validation_errors():
    rows = [
        ["A1", "31/02/2569", "P1", "x", "10"],     # วันที่ผิด, จำนวนไม่ใช่ตัวเลข
        ["A1", "22/11/2569", "P2", "1", "10"],     # วันที่ส่วนหัวไม่ตรงกับแถวแรก
        ["", "22/11/2569", "P3", "1", "10"],        # ไม่มีเลขที่
        ["A2", "22/11/2569", "P1\tX", "1", "10"],  # มี Tab ในข้อความ
        ["A1", "22/11/2569", "P1", "1", "10"],     # A1 ไม่ต่อเนื่อง
    ]
    plan = build_plan(tmpl(), table(rows))
    assert not plan.ok
    msgs = " | ".join(i.message for i in plan.errors)
    assert "ไม่ใช่วันที่ที่มีอยู่จริง" in msgs
    assert "ไม่ใช่ตัวเลข" in msgs
    assert "ไม่ตรงกับแถว" in msgs
    assert "ไม่มีค่าในคอลัมน์" in msgs
    assert "Tab" in msgs
    assert "ไม่อยู่ติดกัน" in msgs
    lines = {i.line for i in plan.errors}
    assert {2, 3, 4, 5, 6} <= lines


def test_missing_column_and_bad_keys():
    t = tmpl()
    t.lines.append(Step("field", "ไม่มีคอลัมน์นี้"))
    t.footer.append(Step("keys", value="{ENTR}"))
    plan = build_plan(t, table(ROWS))
    msgs = " | ".join(i.message for i in plan.errors)
    assert "ไม่พบคอลัมน์ \"ไม่มีคอลัมน์นี้\"" in msgs
    assert "ไม่รู้จักปุ่ม" in msgs
    assert plan.docs == []


def test_required_empty():
    rows = [["A1", "", "P1", "1", "1"]]
    plan = build_plan(tmpl(), table(rows))
    assert any("ต้องมีค่า" in i.message for i in plan.errors)


def test_range_cutting_document():
    plan = build_plan(tmpl(), table(ROWS), start=3, end=4)
    assert any("ตัดเอกสาร A1 ไม่ครบ" in i.message for i in plan.errors)
    plan = build_plan(tmpl(), table(ROWS), start=4, end=4)
    assert plan.ok
    assert [d.key for d in plan.docs] == ["A2"]
    plan = build_plan(tmpl(), table(ROWS), start=10, end=20)
    assert any("ไม่มีข้อมูลในช่วงแถว" in i.message for i in plan.errors)


def test_preview_text():
    text = render_preview(build_plan(tmpl(), table(ROWS)))
    assert "■ เอกสาร 1: A1" in text
    assert 'พิมพ์ "22/11/69"' in text
    assert "[F9]" in text


def test_start_index_and_paste_mode():
    t = tmpl()
    t.settings.input_mode = "paste"
    plan = build_plan(t, table(ROWS))
    be = RecordingBackend()
    assert Runner(plan, be, start_index=1).run() == "finished"
    assert ("paste", "A2") in be.sent
    assert not any(ev[0] == "char" for ev in be.sent)
    assert ("paste", "A1") not in be.sent


def test_window_not_found():
    plan = build_plan(tmpl(), table(ROWS))
    be = RecordingBackend(windows=["Notepad"])
    events = []
    r = Runner(plan, be, events=lambda kind, **kw: events.append((kind, kw)))
    assert r.run() == "error"
    assert "ไม่พบหน้าต่าง" in r.message
    assert events[-1][0] == "finished"


def test_emergency_abort_marks_partial_doc():
    plan = build_plan(tmpl(), table(ROWS))

    class AbortAfter(RecordingBackend):
        def press(self, key, mods=()):
            super().press(key, mods)
            if len([e for e in self.sent if e[0] == "key"]) == 3:
                self.abort = True

    be = AbortAfter()
    r = Runner(plan, be)
    assert r.run() == "stopped"
    assert r.results[0].status.startswith("หยุดกลางเอกสาร")


def _run_in_thread(runner):
    th = threading.Thread(target=runner.run, daemon=True)
    th.start()
    return th


def _wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_focus_loss_pauses_then_resumes():
    plan = build_plan(tmpl(), table(ROWS))

    class LoseFocus(RecordingBackend):
        lost = False

        def type_char(self, ch):
            super().type_char(ch)
            if ch == "P" and not self.lost:
                self.lost = True
                self.active = False  # ผู้ใช้คลิกหน้าต่างอื่น 1 ครั้ง

        def activate(self):
            super().activate()
            self.active = True

    be = LoseFocus()
    events = []
    r = Runner(plan, be, events=lambda kind, **kw: events.append(kind))
    r.resume_delay_s = 0
    r.settle_s = 0
    th = _run_in_thread(r)
    assert _wait_for(lambda: r.paused)
    sent_while_paused = len(be.sent)
    time.sleep(0.2)
    assert len(be.sent) == sent_while_paused  # ไม่ส่งปุ่มตอนหยุดพัก
    r.resume()
    th.join(5)
    assert r.status == "finished"
    assert "paused" in events and "resumed" in events
    # ข้อความไม่หายและไม่ซ้ำหลังทำต่อ
    assert be.typed().count("P1<ENTER>") == 2
    assert ("activate",) in be.sent[sent_while_paused:]


def test_confirm_each_doc_and_stop():
    plan = build_plan(tmpl(), table(ROWS))
    be = RecordingBackend()
    r = Runner(plan, be, confirm_each_doc=True)
    r.resume_delay_s = 0
    r.settle_s = 0
    th = _run_in_thread(r)
    assert _wait_for(lambda: r.paused)
    assert [x.status for x in r.results] == ["คีย์ครบ"]
    r.stop()
    th.join(5)
    assert r.status == "stopped"
    assert len(r.results) == 1


def test_pause_step():
    t = tmpl()
    t.footer = [Step("pause", value="ตรวจแล้วกดบันทึก")]
    plan = build_plan(t, table(ROWS))
    be = RecordingBackend()
    reasons = []
    r = Runner(plan, be, events=lambda kind, **kw: reasons.append(kw.get("reason")) if kind == "paused" else None)
    r.resume_delay_s = 0
    r.settle_s = 0
    th = _run_in_thread(r)
    for _ in range(2):
        assert _wait_for(lambda: r.paused)
        r.resume()
        assert _wait_for(lambda: not r.paused)
    th.join(5)
    assert r.status == "finished"
    assert reasons == ["ตรวจแล้วกดบันทึก", "ตรวจแล้วกดบันทึก"]


def test_pause_step_with_confirm_each_doc_pauses_once_per_doc():
    t = tmpl()
    t.footer = [Step("pause", value="ตรวจแล้วกดบันทึก")]
    plan = build_plan(t, table(ROWS))
    reasons = []
    r = Runner(plan, RecordingBackend(), confirm_each_doc=True,
               events=lambda kind, **kw: reasons.append(kw.get("reason")) if kind == "paused" else None)
    r.resume_delay_s = 0
    r.settle_s = 0
    th = _run_in_thread(r)
    for _ in range(2):
        assert _wait_for(lambda: r.paused)
        r.resume()
        assert _wait_for(lambda: not r.paused)
    th.join(5)
    assert r.status == "finished"
    assert reasons == ["ตรวจแล้วกดบันทึก", "ตรวจแล้วกดบันทึก"]


def test_write_log(tmp_path):
    plan = build_plan(tmpl(), table(ROWS))
    r = Runner(plan, RecordingBackend())
    r.run()
    p = tmp_path / "log.csv"
    write_log(str(p), plan, r.results, r.status, "data.csv")
    text = p.read_text(encoding="utf-8-sig")
    assert "คีย์ครบ" in text and "A2" in text and "1,610.00" in text


def test_plan_with_errors_cannot_run():
    plan = build_plan(tmpl(), table([["A1", "bad", "P", "1", "1"]]))
    with pytest.raises(ValueError):
        Runner(plan, RecordingBackend()).run()


def test_pause_placeholders_filled_per_row():
    t = tmpl()
    t.lines = [Step("pause", value="เลือกบิล {สินค้า} ยอด {ราคา} {ไม่มีคอลัมน์}")]
    t.footer = []
    plan = build_plan(t, table(ROWS))
    assert "ไม่มีคอลัมน์" in " ".join(i.message for i in plan.errors)
    t.lines = [Step("pause", value="เลือกบิล {สินค้า} ยอด {ราคา}")]
    plan = build_plan(t, table(ROWS))
    assert plan.ok, plan.issues
    msgs = [a.message for d in plan.docs for a in d.actions if isinstance(a, PauseHere)]
    assert msgs == ["เลือกบิล P1 ยอด 1,500", "เลือกบิล P2 ยอด 99.995", "เลือกบิล P1 ยอด 10"]
    assert "สินค้า" in t.columns_used() and "ราคา" in t.columns_used()
