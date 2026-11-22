"""หน้า 3: ตรวจสอบข้อมูลและรันคีย์"""

from __future__ import annotations

import datetime as dt
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from ..backends import BackendError, get_backend
from ..engine import Plan, Runner, build_plan, render_preview, write_log
from ..paths import logs_dir
from .theme import C
from .widgets import LogBox, ScrollTree, StatTile, card

if TYPE_CHECKING:
    from .app import App


class RunPage(ttk.Frame):
    title = "ตรวจสอบและรัน"
    subtitle = "ตรวจข้อมูลทุกแถวก่อนคีย์ ดูลำดับการกดปุ่ม แล้วสั่งคีย์เข้า Express"

    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master)
        self.app = app
        self.thread: threading.Thread | None = None
        self.run_start_index = 0

        # ---- ช่วงข้อมูล
        top = card(self)
        top.pack(fill="x")
        ttk.Label(top, text="ช่วงข้อมูลที่จะคีย์", style="H2.TLabel").grid(row=0, column=0, columnspan=6, sticky="w")
        self.range_mode = tk.StringVar(value="all")
        self.range_from = tk.StringVar()
        self.range_to = tk.StringVar()
        ttk.Radiobutton(top, text="ทุกแถว", value="all", variable=self.range_mode, command=self._range_mode_changed).grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Radiobutton(top, text="เฉพาะแถวที่", value="range", variable=self.range_mode, command=self._range_mode_changed).grid(
            row=1, column=1, sticky="w", padx=(18, 6), pady=(8, 0))
        self.from_box = ttk.Spinbox(top, from_=1, to=1_000_000, textvariable=self.range_from, width=8)
        self.from_box.grid(row=1, column=2, pady=(8, 0))
        ttk.Label(top, text="ถึง", style="Card.TLabel").grid(row=1, column=3, padx=6, pady=(8, 0))
        self.to_box = ttk.Spinbox(top, from_=1, to=1_000_000, textvariable=self.range_to, width=8)
        self.to_box.grid(row=1, column=4, pady=(8, 0))
        self.range_info = ttk.Label(top, text="", style="CardMuted.TLabel")
        self.range_info.grid(row=1, column=5, sticky="w", padx=(12, 0), pady=(8, 0))
        top.columnconfigure(5, weight=1)
        self.check_btn = ttk.Button(top, text="ตรวจสอบข้อมูล", style="Accent.TButton", command=self.check)
        self.check_btn.grid(row=0, column=6, rowspan=2, sticky="e")
        for v in (self.range_from, self.range_to):
            v.trace_add("write", lambda *_: self.app.invalidate_plan())

        # ---- ตัวเลขสรุป
        tiles = ttk.Frame(self)
        tiles.pack(fill="x", pady=10)
        self.t_docs = StatTile(tiles, "เอกสาร", app.fonts, C["primary"])
        self.t_rows = StatTile(tiles, "แถวข้อมูล", app.fonts, C["text"])
        self.t_err = StatTile(tiles, "ข้อผิดพลาด", app.fonts, C["err"])
        self.t_warn = StatTile(tiles, "คำเตือน", app.fonts, C["warn"])
        for i, t in enumerate((self.t_docs, self.t_rows, self.t_err, self.t_warn)):
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            tiles.columnconfigure(i, weight=1, uniform="tile")
        self.totals = tk.Label(tiles, text="", bg=C["bg"], fg=C["text"], font=app.fonts["base"], justify="left", anchor="w")
        self.totals.grid(row=0, column=4, sticky="nsw", padx=(16, 0))
        tiles.columnconfigure(4, weight=3)

        # ---- ส่วนรัน (วางล่างสุดก่อน เพื่อให้แท็บกลางขยายเต็ม)
        runbox = card(self)
        runbox.pack(side="bottom", fill="x", pady=(10, 0))
        row1 = ttk.Frame(runbox, style="Plain.TFrame")
        row1.pack(fill="x")
        btns = ttk.Frame(row1, style="Plain.TFrame")
        btns.pack(side="right")
        self.start_btn = ttk.Button(btns, text="▶  เริ่มคีย์", style="Primary.TButton", command=self.start)
        self.pause_btn = ttk.Button(btns, text="พัก", command=self.pause, state="disabled")
        self.resume_btn = ttk.Button(btns, text="ทำต่อ", style="Accent.TButton", command=self.resume, state="disabled")
        self.stop_btn = ttk.Button(btns, text="■  หยุด", style="Danger.TButton", command=self.stop, state="disabled")
        for b in (self.start_btn, self.pause_btn, self.resume_btn, self.stop_btn):
            b.pack(side="left", padx=(6, 0))
        self.confirm_each = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="หยุดให้ตรวจทุกเอกสาร (แนะนำตอนทดลอง)",
                        variable=self.confirm_each).pack(side="left")
        ttk.Label(row1, text="เริ่มที่เอกสารที่", style="Card.TLabel").pack(side="left", padx=(18, 6))
        self.start_doc = tk.StringVar(value="1")
        self.start_box = ttk.Spinbox(row1, from_=1, to=1, textvariable=self.start_doc, width=6)
        self.start_box.pack(side="left")

        self.progress = ttk.Progressbar(runbox, mode="determinate", maximum=1)
        self.progress.pack(fill="x", pady=(10, 6))
        self.status = tk.Label(runbox, text="กด \"ตรวจสอบข้อมูล\" ก่อนเริ่มคีย์", bg=C["card"], fg=C["muted"],
                               font=app.fonts["bold"], anchor="w", justify="left", wraplength=880)
        self.status.pack(fill="x")
        self.substatus = tk.Label(runbox, text="", bg=C["card"], fg=C["muted"], font=app.fonts["small"], anchor="w")
        self.substatus.pack(fill="x")

        # ---- แท็บ ปัญหา / ลำดับการคีย์ / บันทึก
        mid = card(self, padding=0)
        mid.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(mid)
        self.nb.pack(fill="both", expand=True, padx=1, pady=1)
        self.issues = ScrollTree(self.nb, [
            ("level", "ระดับ", 90, "w"),
            ("line", "แถว", 60, "e"),
            ("column", "คอลัมน์", 130, "w"),
            ("doc", "เอกสาร", 120, "w"),
            ("msg", "รายละเอียด", 600, "w"),
        ], height=8)
        self.preview = LogBox(self.nb, app.fonts)
        self.preview.text.configure(tabs=("110p", "270p"), wrap="none")
        self.log = LogBox(self.nb, app.fonts)
        self.nb.add(self.issues, text="ปัญหาที่พบ")
        self.nb.add(self.preview, text="ลำดับการคีย์ (ตัวอย่าง)")
        self.nb.add(self.log, text="บันทึกการรัน")
        self.issues.tree.bind("<Double-1>", self._jump_to_issue)

    # ------------------------------------------------------------------ state
    def on_show(self) -> None:
        table = self.app.table
        if table and table.rows:
            self.range_info.configure(text=f"ข้อมูลในไฟล์อยู่ที่แถว {table.first_line}–{table.last_line} (เลขแถวแบบ Excel)")
            if not self.range_from.get():
                self.range_from.set(str(table.first_line))
            if not self.range_to.get():
                self.range_to.set(str(table.last_line))
        else:
            self.range_info.configure(text="ยังไม่ได้เปิดไฟล์ข้อมูล")
        self._update_range_state()

    def _update_range_state(self) -> None:
        state = "normal" if self.range_mode.get() == "range" else "disabled"
        self.from_box.configure(state=state)
        self.to_box.configure(state=state)

    def _range_mode_changed(self) -> None:
        self._update_range_state()
        self.app.invalidate_plan()

    def data_changed(self) -> None:
        table = self.app.table
        if table and table.rows:
            self.range_from.set(str(table.first_line))
            self.range_to.set(str(table.last_line))
        self.on_show()

    def plan_invalidated(self) -> None:
        if self.running:
            return
        for t in (self.t_docs, self.t_rows, self.t_err, self.t_warn):
            t.set(None)
        self.totals.configure(text="")
        self._set_status("ข้อมูลหรือเทมเพลตเปลี่ยน กด \"ตรวจสอบข้อมูล\" ใหม่ (หรือกดเริ่มคีย์ ระบบจะตรวจให้ก่อน)", C["muted"])

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _set_status(self, text: str, color: str = C["text"]) -> None:
        self.status.configure(text=text, fg=color)

    # ------------------------------------------------------------------ check
    def _range(self) -> tuple[int | None, int | None] | None:
        if self.range_mode.get() != "range":
            return None, None
        try:
            start, end = int(self.range_from.get()), int(self.range_to.get())
        except ValueError:
            messagebox.showwarning("ช่วงแถว", "ใส่เลขแถวเป็นตัวเลข", parent=self)
            return None
        if start > end:
            messagebox.showwarning("ช่วงแถว", "แถวเริ่มต้นต้องไม่มากกว่าแถวสุดท้าย", parent=self)
            return None
        return start, end

    def check(self) -> Plan | None:
        if self.running:
            return None
        if self.app.table is None:
            messagebox.showinfo("ยังไม่มีข้อมูล", "เปิดไฟล์ข้อมูลก่อน", parent=self)
            self.app.show_page("data")
            return None
        rng = self._range()
        if rng is None:
            return None
        plan = build_plan(self.app.template, self.app.table, *rng)
        self.app.set_plan(plan)
        self.show_plan(plan)
        return plan

    def show_plan(self, plan: Plan) -> None:
        self.t_docs.set(len(plan.docs))
        self.t_rows.set(plan.row_count)
        self.t_err.set(len(plan.errors), highlight=bool(plan.errors))
        self.t_warn.set(len(plan.warnings), highlight=bool(plan.warnings))
        if plan.totals:
            lines = ["ยอดรวมเพื่อกระทบยอดกับต้นฉบับ"] + [f"{col}:  {val:,f}" for col, val in plan.totals.items()]
            self.totals.configure(text="\n".join(lines))
        else:
            self.totals.configure(text="")

        tree = self.issues.tree
        self.issues.clear()
        ordered = sorted(plan.issues, key=lambda i: (i.level != "error", i.line or 0))
        for n, i in enumerate(ordered):
            tree.insert("", "end", iid=str(n), values=(
                "ข้อผิดพลาด" if i.level == "error" else "คำเตือน", i.line or "", i.column, i.doc, i.message,
            ), tags=(i.level,))
        self.preview.set(render_preview(plan) or "(ไม่มีเอกสาร)")
        self.start_box.configure(to=max(len(plan.docs), 1))
        try:
            if int(self.start_doc.get()) > len(plan.docs):
                self.start_doc.set("1")
        except ValueError:
            self.start_doc.set("1")

        if plan.ok:
            self._set_status(f"พร้อมคีย์ {len(plan.docs):,} เอกสาร ({plan.row_count:,} แถว) ตรวจลำดับการคีย์ในแท็บกลางก่อนเริ่ม", C["ok"])
            self.nb.select(self.preview)
        else:
            self._set_status(f"ต้องแก้ข้อผิดพลาด {len(plan.errors):,} รายการก่อนเริ่มคีย์ (ดับเบิลคลิกรายการเพื่อดูแถวในข้อมูล)", C["err"])
            self.nb.select(self.issues)

    def _jump_to_issue(self, _event=None) -> None:
        sel = self.issues.tree.selection()
        if not sel:
            return
        line = self.issues.tree.item(sel[0], "values")[1]
        if line:
            self.app.show_data_line(int(line))

    # ------------------------------------------------------------------ run
    def start(self) -> None:
        if self.running:
            return
        plan = self.check()
        if plan is None or not plan.ok:
            return
        try:
            start_index = max(int(self.start_doc.get()) - 1, 0)
        except ValueError:
            start_index = 0
        if start_index >= len(plan.docs):
            messagebox.showwarning("เริ่มที่เอกสาร", "เลขเอกสารที่จะเริ่มเกินจำนวนเอกสาร", parent=self)
            return
        try:
            backend = get_backend()
        except BackendError as exc:
            messagebox.showerror("เริ่มคีย์ไม่ได้", str(exc), parent=self)
            return
        docs = plan.docs[start_index:]
        t = plan.template
        msg = (
            f"จะคีย์ {len(docs):,} เอกสาร (เอกสารที่ {start_index + 1}–{len(plan.docs)}) "
            f"เข้าหน้าต่างที่ชื่อมีคำว่า \"{t.window_title}\"\n\n"
            "ก่อนกดตกลง\n"
            "• เปิดหน้าจอบันทึกที่ตรงกับเทมเพลตใน Express ไว้ และวางเคอร์เซอร์ที่ช่องแรก\n"
            f"• หลังกดตกลง จะนับถอยหลัง {t.settings.start_delay_s} วินาที แล้วสลับไปที่ Express เอง\n"
            "• ห้ามใช้เมาส์หรือคีย์บอร์ดระหว่างคีย์ ถ้าคลิกออกจาก Express โปรแกรมจะหยุดพักให้\n"
            f"• หยุดฉุกเฉิน: {backend.abort_hint}"
        )
        if not messagebox.askokcancel("ยืนยันเริ่มคีย์", msg, parent=self):
            return
        self.run_start_index = start_index
        runner = Runner(plan, backend, events=self.app.post_event,
                        confirm_each_doc=self.confirm_each.get(), start_index=start_index)
        self.app.runner = runner
        self.log.set("")
        self.log.append(f"เริ่ม {dt.datetime.now():%d/%m/%Y %H:%M:%S}  เทมเพลต \"{t.name}\"  {len(docs):,} เอกสาร", "head")
        self.progress.configure(maximum=max(len(docs), 1), value=0)
        self.nb.select(self.log)
        self._set_buttons(running=True, paused=False)
        self.thread = threading.Thread(target=runner.run, name="exautokey-runner", daemon=True)
        self.thread.start()
        self.app.update_nav()

    def pause(self) -> None:
        if self.app.runner:
            self.app.runner.pause()

    def resume(self) -> None:
        if self.app.runner:
            self._set_buttons(running=True, paused=False)
            self.app.runner.resume()

    def stop(self) -> None:
        if self.app.runner:
            self.app.runner.stop()
            self._set_status("กำลังหยุด…", C["err"])

    def _set_buttons(self, running: bool, paused: bool) -> None:
        self.start_btn.configure(state="disabled" if running else "normal")
        self.check_btn.configure(state="disabled" if running else "normal")
        self.pause_btn.configure(state="normal" if running and not paused else "disabled")
        self.resume_btn.configure(state="normal" if running and paused else "disabled")
        self.stop_btn.configure(state="normal" if running else "disabled")

    # ------------------------------------------------------------------ events
    def handle_event(self, kind: str, data: dict) -> None:
        if kind == "log":
            self.log.append(data["text"], "muted")
        elif kind == "countdown":
            self._set_status(f"เริ่มใน {data['seconds']} วินาที… อย่าแตะเมาส์และคีย์บอร์ด", C["primary"])
        elif kind == "doc_start":
            doc = data["doc"]
            self._set_status(f"กำลังคีย์เอกสาร {data['number']}/{data['total']}:  {doc.key}  ({doc.lines_text})", C["primary"])
        elif kind == "step":
            m = data["mark"]
            self.substatus.configure(text=f"ขั้นตอน: {m.text}  (แถว {m.row_line})")
        elif kind == "doc_done":
            doc = data["doc"]
            self.progress.configure(value=data["number"])
            self.log.append(f"✓ {doc.key}  ({doc.lines_text})", "ok")
        elif kind == "paused":
            self._set_buttons(running=True, paused=True)
            self._set_status(f"หยุดพัก: {data['reason']}", C["warn"])
            self.log.append(f"หยุดพัก: {data['reason']}", "warn")
            self.app.bring_to_front()
        elif kind == "resumed":
            self._set_buttons(running=True, paused=False)
            self._set_status("กำลังกลับไปที่หน้าต่าง Express…", C["primary"])
        elif kind == "finished":
            self._finished(data)

    def _finished(self, data: dict) -> None:
        runner = self.app.runner
        status = data["status"]
        results = data["results"]
        self._set_buttons(running=False, paused=False)
        self.substatus.configure(text="")
        done = sum(1 for r in results if r.status == "คีย์ครบ")
        partial = [r for r in results if r.status != "คีย์ครบ"]

        log_path = ""
        if runner is not None:
            try:
                log_path = os.path.join(logs_dir(), f"run_{dt.datetime.now():%Y%m%d_%H%M%S}.csv")
                write_log(log_path, runner.plan, results, status, self.app.data_path)
            except OSError as exc:
                log_path = ""
                self.log.append(f"บันทึกไฟล์ log ไม่ได้: {exc}", "err")

        next_doc = self.run_start_index + done + 1
        if status == "finished":
            self._set_status(f"เสร็จแล้ว คีย์ครบ {done:,} เอกสาร", C["ok"])
            self.log.append(f"เสร็จ คีย์ครบ {done:,} เอกสาร", "ok")
        else:
            label = {"stopped": "หยุดแล้ว", "error": "เกิดข้อผิดพลาด"}.get(status, status)
            detail = f"  ({data.get('message')})" if data.get("message") else ""
            self._set_status(f"{label}{detail}  คีย์ครบ {done:,} เอกสาร", C["err"])
            self.log.append(f"{label}{detail}", "err")
            if runner is not None and next_doc <= len(runner.plan.docs):
                self.start_doc.set(str(next_doc))
        if log_path:
            self.log.append(f"บันทึกผลไว้ที่ {log_path}", "muted")
        self.app.update_nav()

        text = f"คีย์ครบ {done:,} เอกสาร"
        if partial:
            p = partial[-1]
            text += (f"\n\nเอกสาร {p.key} ({p.lines}) คีย์ไม่ครบ ต้องตรวจและแก้หรือยกเลิกใน Express เอง"
                     f"\nถ้าจะคีย์ต่อ ช่อง \"เริ่มที่เอกสารที่\" ตั้งไว้ที่ {next_doc} ให้แล้ว")
        if log_path:
            text += f"\n\nไฟล์บันทึกผล: {log_path}"
        if status == "finished":
            messagebox.showinfo("คีย์เสร็จแล้ว", text, parent=self)
        else:
            messagebox.showwarning("คีย์ไม่ครบ", (data.get("message") + "\n\n" if data.get("message") else "") + text, parent=self)
