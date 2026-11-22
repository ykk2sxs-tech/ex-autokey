"""หน้า 2: เทมเพลตการคีย์"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from ..backends import BackendError, get_backend
from ..data import write_csv_header
from ..formats import describe_spec
from ..template import INPUT_MODES, SECTIONS, STEP_KINDS, Step, Template
from .step_dialog import StepDialog
from .widgets import ScrollTree, card, center_on

if TYPE_CHECKING:
    from .app import App

NO_GROUP = "(ไม่จัดกลุ่ม: 1 แถว = 1 เอกสาร)"
ADD_BUTTONS = [
    ("field", "+ ช่องข้อมูล"),
    ("text", "+ ข้อความคงที่"),
    ("keys", "+ กดปุ่ม"),
    ("wait", "+ รอ"),
    ("pause", "+ หยุดรอผู้ใช้"),
]


def step_values(i: int, s: Step) -> tuple:
    kind = STEP_KINDS[s.kind]
    what = fmt = before = then = ""
    if s.kind == "field":
        what = s.column + ("  *" if s.required else "")
        fmt = describe_spec(s.fmt)
        before, then = s.before, s.then
    elif s.kind == "text":
        what, then = f"\"{s.value}\"", s.then
    elif s.kind == "keys":
        what = s.value
    elif s.kind == "wait":
        what = f"{s.ms:,} ms"
    elif s.kind == "pause":
        what = s.value
    return (i + 1, kind, what, fmt, before, then, s.note)


class StepList(ttk.Frame):
    COLUMNS = [
        ("no", "#", 36, "center"),
        ("kind", "ประเภท", 88, "w"),
        ("what", "คอลัมน์ / ค่า", 140, "w"),
        ("fmt", "รูปแบบ", 205, "w"),
        ("before", "กดก่อน", 60, "w"),
        ("then", "กดหลัง", 76, "w"),
        ("note", "หมายเหตุ", 200, "w"),
    ]

    def __init__(self, master: tk.Misc, page: "TemplatePage", section: str):
        super().__init__(master, style="Plain.TFrame", padding=(10, 8))
        self.page = page
        self.app = page.app
        self.section = section
        bar = ttk.Frame(self, style="Plain.TFrame")
        bar.pack(fill="x", pady=(0, 6))
        for kind, label in ADD_BUTTONS:
            ttk.Button(bar, text=label, style="Small.TButton", command=lambda k=kind: self.add(k)).pack(side="left", padx=(0, 4))
        for label, cmd in (("ลบ", self.delete), ("▼", lambda: self.move(1)), ("▲", lambda: self.move(-1)),
                           ("ทำซ้ำ", self.duplicate), ("แก้ไข", self.edit)):
            ttk.Button(bar, text=label, style="Small.TButton", command=cmd).pack(side="right", padx=(4, 0))
        self.list = ScrollTree(self, self.COLUMNS, height=6)
        self.list.pack(fill="both", expand=True)
        self.list.tree.bind("<Double-1>", lambda e: self.edit())
        self.list.tree.bind("<Delete>", lambda e: self.delete())

    @property
    def steps(self) -> list[Step]:
        return self.app.template.section(self.section)

    def refresh(self, select: int | None = None) -> None:
        tree = self.list.tree
        self.list.clear()
        for i, s in enumerate(self.steps):
            tags = ("pause",) if s.kind == "pause" else (("odd",) if i % 2 else ())
            tree.insert("", "end", iid=str(i), values=step_values(i, s), tags=tags)
        if select is not None and 0 <= select < len(self.steps):
            tree.selection_set(str(select))
            tree.see(str(select))

    def _changed(self, select: int | None) -> None:
        self.refresh(select)
        self.app.template_changed()
        self.page.update_tab_titles()

    def add(self, kind: str) -> None:
        defaults = {
            "field": Step(kind="field", then="{ENTER}"),
            "text": Step(kind="text", then="{ENTER}"),
            "keys": Step(kind="keys", value="", then=""),
            "wait": Step(kind="wait", ms=500, then=""),
            "pause": Step(kind="pause", then=""),
        }
        dlg = StepDialog(self, self.app, defaults[kind], f"เพิ่มขั้นตอน: {STEP_KINDS[kind]}")
        if dlg.result is None:
            return
        idx = self.list.selected_index()
        pos = len(self.steps) if idx is None else idx + 1
        self.steps.insert(pos, dlg.result)
        self._changed(pos)

    def edit(self) -> None:
        idx = self.list.selected_index()
        if idx is None:
            return
        dlg = StepDialog(self, self.app, self.steps[idx].copy(), f"แก้ไขขั้นตอนที่ {idx + 1}")
        if dlg.result is not None:
            self.steps[idx] = dlg.result
            self._changed(idx)

    def duplicate(self) -> None:
        idx = self.list.selected_index()
        if idx is None:
            return
        self.steps.insert(idx + 1, self.steps[idx].copy())
        self._changed(idx + 1)

    def move(self, delta: int) -> None:
        idx = self.list.selected_index()
        if idx is None:
            return
        new = idx + delta
        if not 0 <= new < len(self.steps):
            return
        self.steps[idx], self.steps[new] = self.steps[new], self.steps[idx]
        self._changed(new)

    def delete(self) -> None:
        idx = self.list.selected_index()
        if idx is None:
            return
        del self.steps[idx]
        self._changed(min(idx, len(self.steps) - 1) if self.steps else None)


class TemplatePage(ttk.Frame):
    title = "เทมเพลตการคีย์"
    subtitle = "กำหนดว่าแต่ละคอลัมน์จะพิมพ์ลงช่องไหนของ Express และต้องกดปุ่มอะไรระหว่างช่อง"

    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master)
        self.app = app
        self._loading = False

        # แถบเลือกเทมเพลต
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="เทมเพลต").pack(side="left", padx=(0, 8))
        self.pick_var = tk.StringVar()
        self.pick = ttk.Combobox(bar, textvariable=self.pick_var, state="readonly", width=36)
        self.pick.pack(side="left")
        self.pick.bind("<<ComboboxSelected>>", lambda e: self.app.select_template(self.pick.current()))
        self.save_btn = ttk.Button(bar, text="บันทึก", style="Primary.TButton", command=self.app.save_template)
        self.save_btn.pack(side="left", padx=(8, 0))
        for text, cmd in (("ใหม่", self.app.new_template), ("ทำสำเนา", self.app.duplicate_template),
                          ("ลบ", self.app.delete_template), ("นำเข้า…", self.app.import_template)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="สร้างไฟล์ CSV เปล่าตามเทมเพลต…", command=self.export_csv).pack(side="right")

        # ข้อมูลทั่วไปของเทมเพลต
        form = card(self)
        form.pack(fill="x", pady=(12, 10))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.name_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        self.window_var = tk.StringVar()
        self.group_var = tk.StringVar()

        def lab(r, c, text):
            ttk.Label(form, text=text, style="Card.TLabel").grid(row=r, column=c, sticky="w", padx=(0 if c == 0 else 18, 10), pady=4)

        lab(0, 0, "ชื่อเทมเพลต")
        ttk.Entry(form, textvariable=self.name_var).grid(row=0, column=1, sticky="we", pady=4)
        lab(0, 2, "หน้าต่างโปรแกรม (ชื่อมีคำว่า)")
        wf = ttk.Frame(form, style="Plain.TFrame")
        wf.grid(row=0, column=3, sticky="we")
        wf.columnconfigure(0, weight=1)
        ttk.Entry(wf, textvariable=self.window_var).grid(row=0, column=0, sticky="we")
        ttk.Button(wf, text="เลือก…", style="Small.TButton", command=self.pick_window).grid(row=0, column=1, padx=(6, 0))
        lab(1, 0, "คำอธิบาย")
        ttk.Entry(form, textvariable=self.desc_var).grid(row=1, column=1, columnspan=3, sticky="we", pady=4)
        lab(2, 0, "จัดกลุ่มเอกสารตาม")
        self.group_box = ttk.Combobox(form, textvariable=self.group_var, width=30)
        self.group_box.grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(form, style="CardMuted.TLabel",
                  text="แถวที่อยู่ติดกันและมีค่าคอลัมน์นี้เหมือนกัน = 1 เอกสาร (ส่วนหัวทำครั้งเดียว รายการทำทุกแถว)").grid(
            row=2, column=2, columnspan=2, sticky="w", padx=(18, 0))

        for var, attr in ((self.name_var, "name"), (self.desc_var, "description"),
                          (self.window_var, "window_title"), (self.group_var, "group_by")):
            var.trace_add("write", lambda *_, v=var, a=attr: self._form_changed(a, v))

        # ส่วนล่าง: ขั้นตอน + ตั้งค่า
        lower = ttk.Frame(self)
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=1)
        lower.rowconfigure(0, weight=1)

        nb_card = card(lower, padding=0)
        nb_card.grid(row=0, column=0, sticky="nsew")
        self.nb = ttk.Notebook(nb_card)
        self.nb.pack(fill="both", expand=True, padx=1, pady=1)
        self.lists: dict[str, StepList] = {}
        for sec in SECTIONS:
            sl = StepList(self.nb, self, sec)
            self.nb.add(sl, text=SECTIONS[sec])
            self.lists[sec] = sl

        st = card(lower)
        st.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        ttk.Label(st, text="ความเร็วและวิธีพิมพ์", style="H2.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.setting_vars: dict[str, tk.StringVar] = {}
        for r, (key, label, hi) in enumerate((("key_delay_ms", "หน่วงต่อตัวอักษร (ms)", 1000),
                                              ("step_delay_ms", "หน่วงต่อขั้นตอน (ms)", 5000),
                                              ("doc_delay_ms", "หน่วงต่อเอกสาร (ms)", 30000),
                                              ("start_delay_s", "นับถอยหลัง (วินาที)", 30)), start=1):
            ttk.Label(st, text=label, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            ttk.Spinbox(st, from_=0, to=hi, increment=10 if hi > 30 else 1, textvariable=var, width=7).grid(
                row=r, column=1, sticky="e", padx=(10, 0), pady=2)
            var.trace_add("write", lambda *_, k=key, v=var: self._setting_changed(k, v))
            self.setting_vars[key] = var
        ttk.Label(st, text="วิธีส่งข้อความ", style="Card.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self.mode_var = tk.StringVar()
        for r, (val, text) in enumerate(INPUT_MODES.items(), start=6):
            ttk.Radiobutton(st, text=text, value=val, variable=self.mode_var,
                            command=lambda: self._setting_changed("input_mode", self.mode_var)).grid(
                row=r, column=0, columnspan=2, sticky="w")
        ttk.Label(st, style="CardMuted.TLabel", wraplength=250, justify="left",
                  text="ภาษาไทยขึ้นเป็น ? → ใช้แบบวาง Clipboard\nตัวอักษรหาย/ข้ามช่อง → เพิ่มเวลาหน่วง").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self.refresh_columns()

    def refresh_columns(self) -> None:
        cols = list(self.app.table.columns) if self.app.table else []
        for c in self.app.template.columns_used():
            if c not in cols:
                cols.append(c)
        self.group_box.configure(values=[NO_GROUP] + cols)

    def refresh_picker(self) -> None:
        names = [t.name for t in self.app.templates]
        self.pick.configure(values=names)
        idx = self.app.template_index
        if idx is not None and 0 <= idx < len(names):
            self.pick.current(idx)
        else:
            self.pick_var.set(self.app.template.name + " (ยังไม่บันทึก)")

    def load_template(self, t: Template) -> None:
        self._loading = True
        try:
            self.name_var.set(t.name)
            self.desc_var.set(t.description)
            self.window_var.set(t.window_title)
            self.group_var.set(t.group_by or NO_GROUP)
            for key, var in self.setting_vars.items():
                var.set(str(getattr(t.settings, key)))
            self.mode_var.set(t.settings.input_mode)
        finally:
            self._loading = False
        for sl in self.lists.values():
            sl.refresh()
        self.refresh_columns()
        self.refresh_picker()
        self.update_tab_titles()

    def update_tab_titles(self) -> None:
        for i, sec in enumerate(SECTIONS):
            n = len(self.app.template.section(sec))
            self.nb.tab(i, text=f"{SECTIONS[sec]}  ({n})")

    def _form_changed(self, attr: str, var: tk.StringVar) -> None:
        if self._loading:
            return
        value = var.get()
        if attr == "group_by" and value == NO_GROUP:
            value = ""
        setattr(self.app.template, attr, value.strip() if attr != "description" else value)
        self.app.template_changed()

    def _setting_changed(self, key: str, var: tk.StringVar) -> None:
        if self._loading:
            return
        s = self.app.template.settings
        if key == "input_mode":
            s.input_mode = var.get()
        else:
            try:
                setattr(s, key, max(0, int(var.get())))
            except ValueError:
                return
        self.app.template_changed()

    # ------------------------------------------------------------------
    def pick_window(self) -> None:
        try:
            titles = get_backend().list_windows()
        except BackendError as exc:
            messagebox.showinfo("เลือกหน้าต่าง", str(exc), parent=self)
            return
        if not titles:
            messagebox.showinfo("เลือกหน้าต่าง", "ไม่พบหน้าต่างโปรแกรมที่เปิดอยู่", parent=self)
            return
        dlg = tk.Toplevel(self)
        dlg.title("เลือกหน้าต่างโปรแกรม Express")
        dlg.transient(self.winfo_toplevel())
        frame = ttk.Frame(dlg, style="Plain.TFrame", padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, style="Card.TLabel", wraplength=460, justify="left",
                  text="เลือกหน้าต่างของ Express แล้วแก้ข้อความให้เหลือเฉพาะคำที่ไม่เปลี่ยน "
                       "(เช่น ตัดชื่อเมนูหรือวันที่ออก) เพื่อให้ใช้ได้ทุกครั้ง").pack(anchor="w", pady=(0, 8))
        lb = tk.Listbox(frame, height=12, width=64, font=self.app.fonts["base"], activestyle="none")
        lb.pack(fill="both", expand=True)
        for t in titles:
            lb.insert("end", t)

        def choose() -> None:
            sel = lb.curselection()
            if sel:
                self.window_var.set(titles[sel[0]])
            dlg.destroy()

        lb.bind("<Double-1>", lambda e: choose())
        ttk.Button(frame, text="ใช้หน้าต่างนี้", style="Primary.TButton", command=choose).pack(anchor="e", pady=(10, 0))
        center_on(dlg, self.winfo_toplevel())
        dlg.grab_set()

    def export_csv(self) -> None:
        cols = self.app.template.columns_used()
        if not cols:
            messagebox.showinfo("สร้างไฟล์ CSV", "เทมเพลตนี้ยังไม่มีช่องข้อมูล", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="บันทึกไฟล์ CSV เปล่า", defaultextension=".csv",
            initialfile=f"{self.app.template.name}.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        write_csv_header(path, cols)
        messagebox.showinfo("สร้างไฟล์ CSV",
                            f"สร้างไฟล์แล้ว: {os.path.basename(path)}\n\nคอลัมน์: {', '.join(cols)}\n\n"
                            "เปิดใน Excel กรอกข้อมูล แล้วบันทึกเป็น CSV UTF-8 หรือ .xlsx", parent=self)


def ask_name(parent: tk.Misc, title: str, initial: str) -> str | None:
    name = simpledialog.askstring(title, "ชื่อเทมเพลต", initialvalue=initial, parent=parent)
    return name.strip() if name and name.strip() else None
