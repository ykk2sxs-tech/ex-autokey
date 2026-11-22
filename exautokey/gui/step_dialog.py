"""หน้าต่างเพิ่ม/แก้ไขขั้นตอนในเทมเพลต"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..formats import DATE_PATTERNS, FormatError, apply_format, is_empty, to_text
from ..keyspec import COMMON_KEYS, KeySpecError, parse_keys
from ..template import STEP_KINDS, Step
from .theme import C
from .widgets import center_on

if TYPE_CHECKING:
    from .app import App

DECIMAL_CHOICES = ["ตามต้นฉบับ", "0", "1", "2", "3", "4"]
KEYS_HELP = (
    "{ENTER} {TAB} {ESC} {F1}..{F12} {UP} {DOWN} {LEFT} {RIGHT} {HOME} {END} {DEL} {BS}\n"
    "{TAB 3} = กด 3 ครั้ง   {WAIT 500} = รอ 0.5 วินาที\n"
    "^ = Ctrl   + = Shift   % = Alt   เช่น ^s  %{F4}  +{TAB}\n"
    "ตัวอักษรอื่นจะถูกพิมพ์ตามที่เขียน  ถ้าต้องการพิมพ์ + ^ % { } ให้เขียน {+} {^} {%} {{} {}}"
)


class StepDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "App", step: Step, title: str):
        super().__init__(parent)
        self.withdraw()
        self.app = app
        self.step = step
        self.result: Step | None = None
        self.title(title)
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        body = ttk.Frame(self, style="Plain.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        self.body = body
        self.row = 0

        ttk.Label(body, text=STEP_KINDS[step.kind], style="H2.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.row = 1

        self.note = tk.StringVar(value=step.note)
        builder = getattr(self, f"_build_{step.kind}")
        builder()
        self._entry("หมายเหตุ (แสดงในรายการ)", self.note, width=44)

        self.err = ttk.Label(body, text="", style="Err.TLabel", wraplength=520, justify="left")
        self.err.grid(row=self.row, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.row += 1

        btns = ttk.Frame(body, style="Plain.TFrame")
        btns.grid(row=self.row, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="ยกเลิก", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="ตกลง", style="Primary.TButton", command=self._ok).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        center_on(self, parent.winfo_toplevel())
        self.deiconify()
        self.grab_set()
        self.focus_set()
        self.wait_window()

    # ------------------------------------------------------------ helpers
    def _label(self, text: str) -> None:
        ttk.Label(self.body, text=text, style="Card.TLabel").grid(row=self.row, column=0, sticky="w", padx=(0, 12), pady=4)

    def _entry(self, label: str, var: tk.StringVar, width: int = 30) -> ttk.Entry:
        self._label(label)
        e = ttk.Entry(self.body, textvariable=var, width=width)
        e.grid(row=self.row, column=1, columnspan=2, sticky="we", pady=4)
        self.row += 1
        return e

    def _keys_combo(self, label: str, var: tk.StringVar) -> None:
        self._label(label)
        cb = ttk.Combobox(self.body, textvariable=var, values=[""] + COMMON_KEYS, width=28)
        cb.grid(row=self.row, column=1, sticky="w", pady=4)
        ttk.Label(self.body, text="เว้นว่าง = ไม่กด", style="CardMuted.TLabel").grid(row=self.row, column=2, sticky="w", padx=8)
        self.row += 1

    def _columns(self) -> list[str]:
        cols: list[str] = []
        if self.app.table is not None:
            cols += self.app.table.columns
        for c in self.app.template.columns_used():
            if c not in cols:
                cols.append(c)
        return cols

    # ------------------------------------------------------------ builders
    def _build_field(self) -> None:
        s = self.step
        b = self.body
        self.column = tk.StringVar(value=s.column)
        self._label("คอลัมน์ในไฟล์ข้อมูล")
        cb = ttk.Combobox(b, textvariable=self.column, values=self._columns(), width=30)
        cb.grid(row=self.row, column=1, columnspan=2, sticky="we", pady=4)
        self.row += 1

        spec = s.fmt
        self.fmt_type = tk.StringVar(value=spec.get("type", "text"))
        self._label("รูปแบบค่า")
        rb = ttk.Frame(b, style="Plain.TFrame")
        rb.grid(row=self.row, column=1, columnspan=2, sticky="w", pady=4)
        for val, txt in (("text", "ข้อความ"), ("date", "วันที่"), ("number", "ตัวเลข")):
            ttk.Radiobutton(rb, text=txt, value=val, variable=self.fmt_type, command=self._show_fmt).pack(side="left", padx=(0, 14))
        self.row += 1

        # ตัวเลือกย่อยของแต่ละรูปแบบ
        self.opt_row = self.row
        self.row += 1
        self.text_opts = ttk.Frame(b, style="Plain.TFrame")
        self.maxlen = tk.StringVar(value=str(spec.get("max_length", 0) or 0))
        ttk.Label(self.text_opts, text="ความยาวสูงสุด", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(self.text_opts, from_=0, to=254, textvariable=self.maxlen, width=6).pack(side="left", padx=6)
        ttk.Label(self.text_opts, text="ตัวอักษร (0 = ไม่จำกัด) ใช้กันข้อความยาวเกินช่องใน Express", style="CardMuted.TLabel").pack(side="left")

        self.date_opts = ttk.Frame(b, style="Plain.TFrame")
        self.pattern = tk.StringVar(value=spec.get("pattern", "dd/mm/yy"))
        self.era = tk.StringVar(value=spec.get("era", "BE"))
        ttk.Label(self.date_opts, text="พิมพ์เป็น", style="Card.TLabel").pack(side="left")
        ttk.Combobox(self.date_opts, textvariable=self.pattern, values=DATE_PATTERNS, width=12).pack(side="left", padx=6)
        ttk.Radiobutton(self.date_opts, text="ปี พ.ศ.", value="BE", variable=self.era).pack(side="left", padx=(8, 8))
        ttk.Radiobutton(self.date_opts, text="ปี ค.ศ.", value="CE", variable=self.era).pack(side="left")

        self.num_opts = ttk.Frame(b, style="Plain.TFrame")
        dec = spec.get("decimals", 2)
        self.decimals = tk.StringVar(value="ตามต้นฉบับ" if dec in (None, "") else str(dec))
        self.thousands = tk.BooleanVar(value=bool(spec.get("thousands", False)))
        self.total = tk.BooleanVar(value=bool(spec.get("total", False)))
        n1 = ttk.Frame(self.num_opts, style="Plain.TFrame")
        n1.pack(anchor="w")
        ttk.Label(n1, text="ทศนิยม", style="Card.TLabel").pack(side="left")
        ttk.Combobox(n1, textvariable=self.decimals, values=DECIMAL_CHOICES, width=10, state="readonly").pack(side="left", padx=6)
        ttk.Label(n1, text="ตำแหน่ง (ปัดเศษแบบ 0.5 ขึ้น)", style="CardMuted.TLabel").pack(side="left")
        ttk.Checkbutton(self.num_opts, text="ใส่คอมมาคั่นหลักพัน", variable=self.thousands).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(self.num_opts, text="แสดงยอดรวมคอลัมน์นี้ในหน้าตรวจสอบ (ใช้กระทบยอดกับต้นฉบับ)",
                        variable=self.total).pack(anchor="w")

        self.required = tk.BooleanVar(value=s.required)
        ttk.Checkbutton(b, text="ต้องมีค่า (ถ้าว่างจะแจ้งข้อผิดพลาดก่อนรัน)", variable=self.required).grid(
            row=self.row, column=1, columnspan=2, sticky="w", pady=4)
        self.row += 1

        self.before = tk.StringVar(value=s.before)
        self.then = tk.StringVar(value=s.then)
        self._keys_combo("กดก่อนพิมพ์", self.before)
        self._keys_combo("กดหลังพิมพ์", self.then)

        self.preview = ttk.Label(b, text="", style="CardMuted.TLabel", wraplength=520, justify="left")
        self.preview.grid(row=self.row, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.row += 1

        for var in (self.column, self.fmt_type, self.maxlen, self.pattern, self.era, self.decimals, self.thousands):
            var.trace_add("write", lambda *_: self._update_preview())
        self._show_fmt()

    def _build_text(self) -> None:
        self.value = tk.StringVar(value=self.step.value)
        self._entry("ข้อความที่จะพิมพ์ทุกเอกสาร", self.value, width=40)
        self.then = tk.StringVar(value=self.step.then)
        self._keys_combo("กดหลังพิมพ์", self.then)

    def _build_keys(self) -> None:
        self.value = tk.StringVar(value=self.step.value)
        entry = self._entry("ปุ่มที่จะกด", self.value, width=44)
        quick = ttk.Frame(self.body, style="Plain.TFrame")
        quick.grid(row=self.row, column=1, columnspan=2, sticky="w")
        for i, k in enumerate(COMMON_KEYS):
            ttk.Button(quick, text=k, style="Small.TButton",
                       command=lambda k=k: (entry.insert("insert", k), entry.focus_set())).grid(
                row=i // 7, column=i % 7, padx=2, pady=2, sticky="we")
        self.row += 1
        ttk.Label(self.body, text=KEYS_HELP, style="CardMuted.TLabel", justify="left").grid(
            row=self.row, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.row += 1

    def _build_wait(self) -> None:
        self.ms = tk.StringVar(value=str(self.step.ms or 500))
        self._label("รอ (มิลลิวินาที)")
        ttk.Spinbox(self.body, from_=50, to=60000, increment=50, textvariable=self.ms, width=10).grid(
            row=self.row, column=1, sticky="w", pady=4)
        ttk.Label(self.body, text="1000 = 1 วินาที ใช้เมื่อ Express ต้องโหลดหน้าจอหรือค้นหาข้อมูล",
                  style="CardMuted.TLabel").grid(row=self.row, column=2, sticky="w", padx=8)
        self.row += 1

    def _build_pause(self) -> None:
        self.value = tk.StringVar(value=self.step.value or "ตรวจหน้าจอ Express แล้วกด 'ทำต่อ'")
        self._entry("ข้อความแจ้งผู้ใช้", self.value, width=50)
        ttk.Label(self.body, style="CardMuted.TLabel", wraplength=520, justify="left",
                  text="โปรแกรมจะหยุดรอตรงนี้ทุกเอกสาร ผู้ใช้ทำงานใน Express เอง (เช่น ตรวจยอดแล้วกดบันทึก) "
                       "แล้วกด 'ทำต่อ' ในหน้าจอ EX-AutoKey เพื่อคีย์ต่อ").grid(
            row=self.row, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.row += 1

    # ------------------------------------------------------------ field format
    def _show_fmt(self) -> None:
        for f in (self.text_opts, self.date_opts, self.num_opts):
            f.grid_forget()
        frame = {"text": self.text_opts, "date": self.date_opts, "number": self.num_opts}[self.fmt_type.get()]
        frame.grid(row=self.opt_row, column=1, columnspan=2, sticky="w", pady=4)
        self._update_preview()

    def _spec(self) -> dict:
        t = self.fmt_type.get()
        if t == "date":
            return {"type": "date", "pattern": self.pattern.get().strip() or "dd/mm/yyyy", "era": self.era.get()}
        if t == "number":
            dec = self.decimals.get()
            spec = {"type": "number", "decimals": None if dec == "ตามต้นฉบับ" else int(dec),
                    "thousands": bool(self.thousands.get())}
            if self.total.get():
                spec["total"] = True
            return spec
        try:
            ml = int(self.maxlen.get() or 0)
        except ValueError:
            ml = 0
        return {"type": "text", "max_length": ml} if ml > 0 else {"type": "text"}

    def _update_preview(self) -> None:
        table = self.app.table
        col = self.column.get().strip()
        if table is None or col not in table.columns:
            self.preview.configure(text="(เปิดไฟล์ข้อมูลก่อน จะเห็นตัวอย่างค่าที่จะพิมพ์)", style="CardMuted.TLabel")
            return
        row = next((r for r in table.rows if not is_empty(r.get(col))), None)
        if row is None:
            self.preview.configure(text=f"คอลัมน์ \"{col}\" ไม่มีค่าเลย", style="CardMuted.TLabel")
            return
        raw = row.get(col)
        try:
            out = apply_format(raw, self._spec())
        except FormatError as exc:
            self.preview.configure(text=f"ตัวอย่างแถว {row.line}: \"{to_text(raw)}\" → แปลงไม่ได้: {exc}", style="Err.TLabel")
            return
        self.preview.configure(text=f"ตัวอย่างแถว {row.line}: \"{to_text(raw)}\"  →  จะพิมพ์ \"{out}\"", style="Ok.TLabel")

    # ------------------------------------------------------------ OK
    def _check_keys(self, label: str, spec: str) -> str | None:
        try:
            parse_keys(spec)
        except KeySpecError as exc:
            return f"{label}: {exc}"
        return None

    def _ok(self) -> None:
        s = Step(kind=self.step.kind, note=self.note.get().strip())
        errors: list[str] = []
        if s.kind == "field":
            s.column = self.column.get().strip()
            s.fmt = self._spec()
            s.required = bool(self.required.get())
            s.before = self.before.get().strip()
            s.then = self.then.get().strip()
            if not s.column:
                errors.append("ยังไม่ได้เลือกคอลัมน์")
            errors += [e for e in (self._check_keys("กดก่อนพิมพ์", s.before), self._check_keys("กดหลังพิมพ์", s.then)) if e]
        elif s.kind == "text":
            s.value = self.value.get()
            s.then = self.then.get().strip()
            if not s.value:
                errors.append("ยังไม่ได้ใส่ข้อความ")
            errors += [e for e in (self._check_keys("กดหลังพิมพ์", s.then),) if e]
        elif s.kind == "keys":
            s.value = self.value.get().strip()
            if not s.value:
                errors.append("ยังไม่ได้ระบุปุ่ม")
            errors += [e for e in (self._check_keys("ปุ่ม", s.value),) if e]
        elif s.kind == "wait":
            try:
                s.ms = int(self.ms.get())
                if s.ms <= 0:
                    raise ValueError
            except ValueError:
                errors.append("เวลารอต้องเป็นตัวเลขมากกว่า 0")
        elif s.kind == "pause":
            s.value = self.value.get().strip()
        if errors:
            self.err.configure(text="\n".join(errors))
            return
        self.result = s
        self.destroy()
