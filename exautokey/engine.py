"""แปลงข้อมูล + เทมเพลต เป็นแผนการคีย์ ตรวจสอบความถูกต้อง และรันจริง"""

from __future__ import annotations

import csv
import datetime as dt
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from .backends import Backend, BackendError
from .data import Row, Table
from .formats import FormatError, apply_format, is_empty, to_text
from .keyspec import KeyPress, KeySpecError, TypeText, Wait, parse_keys
from .template import SECTIONS, Step, Template

SECTION_SHORT = {"header": "หัว", "lines": "รายการ", "footer": "ท้าย"}
FORBIDDEN_CHARS = {"\r": "ขึ้นบรรทัดใหม่", "\n": "ขึ้นบรรทัดใหม่", "\t": "Tab"}


# ------------------------------------------------------------------ actions

@dataclass(frozen=True)
class Mark:
    """จุดเริ่มต้นของแต่ละขั้นตอน ใช้แสดงความคืบหน้า"""
    section: str
    index: int
    row_line: int
    text: str

    def label(self) -> str:
        return f"— {self.text}"


@dataclass(frozen=True)
class PauseHere:
    message: str

    def label(self) -> str:
        return f"⏸ หยุดรอ: {self.message}"


Action = Mark | PauseHere | KeyPress | TypeText | Wait


# ------------------------------------------------------------------ plan

@dataclass
class Issue:
    level: str  # "error" | "warning"
    message: str
    line: int | None = None
    column: str = ""
    doc: str = ""


@dataclass
class DocPlan:
    index: int
    key: str
    rows: list[Row]
    actions: list[Action] = field(default_factory=list)

    @property
    def lines_text(self) -> str:
        first, last = self.rows[0].line, self.rows[-1].line
        return f"แถว {first}" if first == last else f"แถว {first}–{last}"


@dataclass
class Plan:
    template: Template
    docs: list[DocPlan]
    issues: list[Issue]
    totals: dict[str, Decimal]
    row_count: int

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return bool(self.docs) and not self.errors


def _step_title(step: Step) -> str:
    if step.note:
        return step.note
    if step.kind == "field":
        return step.column or "(ยังไม่เลือกคอลัมน์)"
    if step.kind == "text":
        return f'ข้อความ "{step.value}"'
    if step.kind == "keys":
        return f"ปุ่ม {step.value}"
    if step.kind == "wait":
        return f"รอ {step.ms} ms"
    return "หยุดรอผู้ใช้"


def check_template(t: Template) -> list[Issue]:
    issues: list[Issue] = []
    if not t.window_title.strip():
        issues.append(Issue("error", "ยังไม่ได้ระบุชื่อหน้าต่างโปรแกรม Express ในเทมเพลต"))
    if not any(t.section(s) for s in SECTIONS):
        issues.append(Issue("error", "เทมเพลตยังไม่มีขั้นตอน"))
    for sec, idx, step in t.all_steps():
        where = f"{SECTION_SHORT[sec]} ขั้นที่ {idx + 1}"
        if step.kind == "field" and not step.column:
            issues.append(Issue("error", f"{where}: ยังไม่ได้เลือกคอลัมน์"))
        if step.kind == "wait" and step.ms <= 0:
            issues.append(Issue("error", f"{where}: เวลารอต้องมากกว่า 0"))
        specs = []
        if step.kind in ("field", "text"):
            specs = [("ก่อนพิมพ์", step.before), ("หลังพิมพ์", step.then)]
        elif step.kind == "keys":
            specs = [("ปุ่ม", step.value)]
            if not step.value:
                issues.append(Issue("error", f"{where}: ยังไม่ได้ระบุปุ่ม"))
        for label, spec in specs:
            try:
                parse_keys(spec)
            except KeySpecError as exc:
                issues.append(Issue("error", f"{where} ({label}): {exc}"))
    return issues


def check_columns(t: Template, table: Table) -> list[Issue]:
    issues: list[Issue] = []
    have = set(table.columns)
    if t.group_by and t.group_by not in have:
        issues.append(Issue("error", f"ไม่พบคอลัมน์ \"{t.group_by}\" ที่ใช้จัดกลุ่มเอกสาร", column=t.group_by))
    missing = [c for c in t.columns_used() if c not in have and c != t.group_by]
    for c in missing:
        issues.append(Issue("error", f"ไม่พบคอลัมน์ \"{c}\" ในไฟล์ข้อมูล", column=c))
    return issues


def group_documents(rows: list[Row], group_by: str) -> tuple[list[tuple[str, list[Row]]], list[Issue]]:
    issues: list[Issue] = []
    if not group_by:
        return [(f"แถว {r.line}", [r]) for r in rows], issues
    groups: list[tuple[str, list[Row]]] = []
    index: dict[str, int] = {}
    for r in rows:
        key = to_text(r.get(group_by))
        if not key:
            issues.append(Issue("error", f"ไม่มีค่าในคอลัมน์ \"{group_by}\"", r.line, group_by))
            continue
        if groups and groups[-1][0] == key:
            groups[-1][1].append(r)
        elif key in index:
            first = groups[index[key]][1][0].line
            issues.append(Issue(
                "error",
                f"เอกสาร {key} มีแถวไม่อยู่ติดกัน (แถว {first} และ {r.line}) ให้เรียงข้อมูลให้แถวของเอกสารเดียวกันอยู่ติดกัน",
                r.line, group_by, key,
            ))
            groups[index[key]][1].append(r)
        else:
            index[key] = len(groups)
            groups.append((key, [r]))
    return groups, issues


def _keys(spec: str) -> list[Action]:
    try:
        return list(parse_keys(spec))
    except KeySpecError:
        return []  # รายงานไว้แล้วใน check_template


def _compile_step(sec: str, idx: int, step: Step, row: Row, doc_key: str,
                  issues: list[Issue], numbers: dict[tuple[str, int], Decimal]) -> list[Action]:
    acts: list[Action] = [Mark(sec, idx, row.line, _step_title(step))]
    if step.kind == "field":
        col = step.column
        raw = row.get(col)
        text = ""
        if is_empty(raw):
            if step.required:
                issues.append(Issue("error", f"ช่อง \"{col}\" ต้องมีค่า", row.line, col, doc_key))
        else:
            try:
                text = apply_format(raw, step.fmt)
            except FormatError as exc:
                issues.append(Issue("error", f"\"{col}\": {exc}", row.line, col, doc_key))
            else:
                bad = {name for ch, name in FORBIDDEN_CHARS.items() if ch in text}
                if bad:
                    issues.append(Issue("error", f"\"{col}\" มีอักขระ{'/'.join(sorted(bad))}อยู่ในข้อความ", row.line, col, doc_key))
                if step.fmt.get("type") == "number" and step.fmt.get("total") and text:
                    numbers[(col, row.line)] = Decimal(text.replace(",", ""))
        acts += _keys(step.before)
        if text:
            acts.append(TypeText(text))
        acts += _keys(step.then)
    elif step.kind == "text":
        if step.value:
            acts.append(TypeText(step.value))
        acts += _keys(step.then)
    elif step.kind == "keys":
        acts += _keys(step.value)
    elif step.kind == "wait":
        acts.append(Wait(step.ms))
    elif step.kind == "pause":
        acts.append(PauseHere(step.value or "ตรวจหน้าจอ Express แล้วกด 'ทำต่อ'"))
    return acts


def _header_consistency(t: Template, key: str, rows: list[Row]) -> list[Issue]:
    issues: list[Issue] = []
    if len(rows) < 2:
        return issues
    cols = []
    for sec in ("header", "footer"):
        for step in t.section(sec):
            if step.kind == "field" and step.column and step.column not in cols:
                cols.append(step.column)
    for col in cols:
        first = to_text(rows[0].get(col))
        for r in rows[1:]:
            if to_text(r.get(col)) != first:
                issues.append(Issue(
                    "error",
                    f"เอกสาร {key}: \"{col}\" ไม่ตรงกับแถว {rows[0].line} (\"{first}\" กับ \"{to_text(r.get(col))}\") "
                    "ข้อมูลส่วนหัวของเอกสารเดียวกันต้องเหมือนกันทุกแถว",
                    r.line, col, key,
                ))
                break
    return issues


def build_plan(t: Template, table: Table, start: int | None = None, end: int | None = None) -> Plan:
    issues = check_template(t) + check_columns(t, table)
    selected = table.select(start, end)
    if not selected:
        issues.append(Issue("error", "ไม่มีข้อมูลในช่วงแถวที่เลือก"))
    if any(i.level == "error" and i.column and i.line is None for i in issues):
        # คอลัมน์ไม่ครบ สร้างแผนต่อไม่ได้
        return Plan(t, [], issues, {}, len(selected))

    groups, g_issues = group_documents(selected, t.group_by)
    issues += g_issues

    if t.group_by and (start is not None or end is not None):
        selected_lines = {r.line for r in selected}
        keys = {k for k, _ in groups}
        outside: dict[str, list[int]] = {}
        for r in table.rows:
            k = to_text(r.get(t.group_by))
            if k in keys and r.line not in selected_lines:
                outside.setdefault(k, []).append(r.line)
        for k, lines in outside.items():
            shown = ", ".join(str(x) for x in lines[:5]) + (" ..." if len(lines) > 5 else "")
            issues.append(Issue("error", f"ช่วงแถวที่เลือกตัดเอกสาร {k} ไม่ครบ (ยังมีแถว {shown} อยู่นอกช่วง)", doc=k))

    numbers: dict[tuple[str, int], Decimal] = {}
    docs: list[DocPlan] = []
    for n, (key, rows) in enumerate(groups):
        issues += _header_consistency(t, key, rows)
        doc = DocPlan(n, key, rows)
        for sec in SECTIONS:
            sec_rows = rows if sec == "lines" else rows[:1]
            for row in sec_rows:
                for idx, step in enumerate(t.section(sec)):
                    doc.actions += _compile_step(sec, idx, step, row, key, issues, numbers)
        docs.append(doc)

    totals: dict[str, Decimal] = {}
    for (col, _), val in numbers.items():
        totals[col] = totals.get(col, Decimal(0)) + val
    return Plan(t, docs, issues, totals, len(selected))


def render_preview(plan: Plan, max_docs: int = 30) -> str:
    out: list[str] = []
    for doc in plan.docs[:max_docs]:
        out.append(f"■ เอกสาร {doc.index + 1}: {doc.key}  ({doc.lines_text})")
        current: Mark | None = None
        parts: list[str] = []

        def flush() -> None:
            if current is None:
                return
            where = SECTION_SHORT[current.section]
            if current.section == "lines":
                where += f" แถว {current.row_line}"
            out.append(f"    {where}\t{current.text}\t→ {' '.join(parts) if parts else '(ไม่มีการกด)'}")

        for a in doc.actions:
            if isinstance(a, Mark):
                flush()
                current, parts = a, []
            else:
                parts.append(a.label())
        flush()
        out.append("")
    if len(plan.docs) > max_docs:
        out.append(f"... และอีก {len(plan.docs) - max_docs} เอกสาร")
    return "\n".join(out)


# ------------------------------------------------------------------ runner

class StopRun(Exception):
    pass


@dataclass
class DocResult:
    index: int
    key: str
    lines: str
    status: str
    started: str
    finished: str = ""


EventFn = Callable[..., None]


class Runner:
    """รันแผนการคีย์ (ควรเรียก run() ใน thread แยกจากหน้าจอ)"""

    def __init__(self, plan: Plan, backend: Backend, events: EventFn | None = None,
                 confirm_each_doc: bool = False, start_index: int = 0,
                 sleep: Callable[[float], None] = time.sleep):
        self.plan = plan
        self.backend = backend
        self.settings = plan.template.settings
        self.events: EventFn = events or (lambda kind, **kw: None)
        self.confirm_each_doc = confirm_each_doc
        self.start_index = start_index
        self._sleep_fn = sleep
        self._stop = threading.Event()
        self._running = threading.Event()
        self._running.set()
        self.results: list[DocResult] = []
        self.status = "idle"
        self.message = ""
        self.resume_delay_s = 2  # นับถอยหลังก่อนคีย์ต่อหลังกด 'ทำต่อ'
        self.settle_s = 0.3      # รอหน้าต่างขึ้นมาด้านหน้า
        backend.notify = lambda text: self.events("log", text=text)

    # ---- ควบคุมจากหน้าจอ
    def stop(self) -> None:
        self._stop.set()
        self._running.set()

    def pause(self, reason: str = "ผู้ใช้กดพัก") -> None:
        if self._running.is_set():
            self._running.clear()
            self.events("paused", reason=reason)

    def resume(self) -> None:
        self._running.set()

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    # ---- ภายใน
    def _check_stop(self) -> None:
        if self.backend.abort_requested():
            if not self._stop.is_set():
                self.events("log", text="ตรวจพบคำสั่งหยุดฉุกเฉิน")
            self._stop.set()
        if self._stop.is_set():
            raise StopRun

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while True:
            self._check_stop()
            left = end - time.monotonic()
            if left <= 0:
                return
            self._sleep_fn(min(0.05, left))

    def _countdown(self, seconds: int) -> None:
        for s in range(seconds, 0, -1):
            self.events("countdown", seconds=s)
            self._sleep(1.0)

    def _wait_resume(self) -> None:
        while True:
            while not self._running.wait(0.1):
                self._check_stop()
            self._check_stop()
            self.events("resumed")
            self._countdown(self.resume_delay_s)
            self.backend.activate()
            self._sleep(self.settle_s)
            if self.backend.target_active():
                return
            self.pause("เปิดหน้าต่าง Express ขึ้นมาไม่ได้ ให้คลิกที่หน้าต่าง Express แล้วกด 'ทำต่อ'")

    def _checkpoint(self) -> None:
        self._check_stop()
        if self._running.is_set() and not self.backend.target_active():
            self.pause("หน้าต่าง Express ไม่ได้อยู่ด้านหน้า จึงหยุดไว้ก่อนเพื่อไม่ให้พิมพ์ผิดที่")
        if not self._running.is_set():
            self._wait_resume()

    def _do(self, a: Action) -> None:
        key_delay = self.settings.key_delay_ms / 1000
        if isinstance(a, Mark):
            self.events("step", mark=a)
            self._checkpoint()
            self._sleep(self.settings.step_delay_ms / 1000)
        elif isinstance(a, Wait):
            self._sleep(a.ms / 1000)
        elif isinstance(a, PauseHere):
            self.pause(a.message)
            self._wait_resume()
        elif isinstance(a, TypeText):
            self._checkpoint()
            if self.settings.input_mode == "paste":
                self.backend.paste_text(a.text)
                # รอให้ Express อ่าน Clipboard เสร็จก่อนจะเปลี่ยนค่าในช่องถัดไป
                self._sleep(max(key_delay, 0.15))
            else:
                self.backend.before_text(a.text)
                for ch in a.text:
                    self._checkpoint()
                    self.backend.type_char(ch)
                    self._sleep(key_delay)
        elif isinstance(a, KeyPress):
            for _ in range(a.repeat):
                self._checkpoint()
                self.backend.press(a.key, a.mods)
                self._sleep(key_delay)

    def _run_doc(self, doc: DocPlan, number: int, total: int) -> None:
        res = DocResult(doc.index, doc.key, doc.lines_text, "กำลังคีย์", _now())
        self.results.append(res)
        self.events("doc_start", doc=doc, number=number, total=total)
        try:
            for a in doc.actions:
                self._do(a)
        except StopRun:
            res.status = "หยุดกลางเอกสาร (คีย์ไม่ครบ ต้องตรวจใน Express)"
            res.finished = _now()
            raise
        except Exception as exc:
            res.status = f"ผิดพลาดกลางเอกสาร: {exc}"
            res.finished = _now()
            raise
        res.status = "คีย์ครบ"
        res.finished = _now()
        self.events("doc_done", doc=doc, number=number, total=total)

    def run(self) -> str:
        if not self.plan.ok:
            raise ValueError("แผนการคีย์ยังมีข้อผิดพลาด")
        self.status = "running"
        try:
            title = self.backend.prepare(self.plan.template.window_title)
            self.events("log", text=f"พบหน้าต่าง: {title}")
            self._countdown(self.settings.start_delay_s)
            self.backend.activate()
            self._sleep(self.settle_s)
            if not self.backend.target_active():
                self.pause("เปิดหน้าต่าง Express ขึ้นมาไม่ได้ ให้คลิกที่หน้าต่าง Express แล้วกด 'ทำต่อ'")
                self._wait_resume()
            docs = self.plan.docs[self.start_index :]
            for n, doc in enumerate(docs, start=1):
                self._run_doc(doc, n, len(docs))
                if n < len(docs):
                    # ถ้าเอกสารจบด้วยขั้นตอน "หยุดรอผู้ใช้" อยู่แล้ว ไม่ต้องหยุดซ้ำอีกรอบ
                    ends_with_pause = bool(doc.actions) and isinstance(doc.actions[-1], PauseHere)
                    if self.confirm_each_doc and not ends_with_pause:
                        self.pause(f"คีย์เอกสาร {doc.key} ครบแล้ว ตรวจใน Express ก่อน แล้วกด 'ทำต่อ' เพื่อคีย์เอกสารถัดไป")
                        self._wait_resume()
                    self._sleep(self.settings.doc_delay_ms / 1000)
            self.status = "finished"
        except StopRun:
            self.status = "stopped"
        except BackendError as exc:
            self.status = "error"
            self.message = str(exc)
        except Exception as exc:  # แจ้งหน้าจอทุกกรณี ไม่ให้ thread ตายเงียบ
            self.status = "error"
            self.message = f"{type(exc).__name__}: {exc}"
        finally:
            self.events("finished", status=self.status, message=self.message, results=list(self.results))
        return self.status


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(path: str, plan: Plan, results: list[DocResult], status: str, source: str = "") -> None:
    """บันทึกผลการรันเป็น CSV เก็บไว้เป็นหลักฐาน (audit trail)"""
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["เทมเพลต", plan.template.name])
        w.writerow(["ไฟล์ข้อมูล", source])
        w.writerow(["สถานะการรัน", status])
        w.writerow(["บันทึกเมื่อ", _now()])
        for col, total in plan.totals.items():
            w.writerow([f"ยอดรวม {col} (ทั้งแผน)", f"{total:,f}"])
        w.writerow([])
        w.writerow(["ลำดับ", "เอกสาร", "แถวในไฟล์", "สถานะ", "เริ่ม", "เสร็จ"])
        for r in results:
            w.writerow([r.index + 1, r.key, r.lines, r.status, r.started, r.finished])
