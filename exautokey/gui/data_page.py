"""หน้า 1: เปิดไฟล์ข้อมูล"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import TYPE_CHECKING

from ..data import DataError, load_table
from ..formats import to_text
from ..paths import samples_dir
from .widgets import ScrollTree, card

if TYPE_CHECKING:
    from .app import App

MAX_SHOW = 3000
FILETYPES = [
    ("ไฟล์ข้อมูล", "*.csv *.txt *.xlsx *.xlsm"),
    ("CSV", "*.csv *.txt"),
    ("Excel", "*.xlsx *.xlsm"),
    ("ทุกไฟล์", "*.*"),
]


class DataPage(ttk.Frame):
    title = "ไฟล์ข้อมูล"
    subtitle = "เปิดไฟล์ CSV หรือ Excel ที่เตรียมไว้ โดยให้ 1 แถวเป็น 1 รายการ และแถวแรกเป็นหัวคอลัมน์"

    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master)
        self.app = app

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="เปิดไฟล์ CSV / Excel…", style="Accent.TButton", command=self.open_file).pack(side="left")
        ttk.Button(bar, text="เปิดไฟล์ตัวอย่าง…", command=self.open_sample).pack(side="left", padx=(8, 0))
        self.reload_btn = ttk.Button(bar, text="↻ โหลดไฟล์เดิมใหม่", command=self.reload, state="disabled")
        self.reload_btn.pack(side="left", padx=(8, 0))
        self.sheet_frame = ttk.Frame(bar)
        ttk.Label(self.sheet_frame, text="ชีต").pack(side="left", padx=(16, 6))
        self.sheet_var = tk.StringVar()
        self.sheet_box = ttk.Combobox(self.sheet_frame, textvariable=self.sheet_var, state="readonly", width=20)
        self.sheet_box.pack(side="left")
        self.sheet_box.bind("<<ComboboxSelected>>", lambda e: self.load(self.app.data_path, self.sheet_var.get()))

        self.info = ttk.Label(self, text="ยังไม่ได้เปิดไฟล์", style="Muted.TLabel")
        self.info.pack(fill="x", pady=(12, 6))

        box = card(self, padding=1)
        box.pack(fill="both", expand=True)
        self.table_view = ScrollTree(box, selectmode="extended")
        self.placeholder = tk.Label(
            box, bg="white", fg="#8a94a6", font=app.fonts["base"], justify="center",
            text="ยังไม่มีข้อมูล\n\nเตรียมข้อมูลใน Excel แล้วเปิดไฟล์ .xlsx ได้เลย หรือบันทึกเป็น CSV\n"
                 "1 แถว = 1 รายการ ถ้าเอกสารมีหลายรายการ ให้ใส่เลขที่เอกสารซ้ำทุกแถว\n\n"
                 "ลองกด \"เปิดไฟล์ตัวอย่าง…\" เพื่อดูรูปแบบไฟล์ของแต่ละเทมเพลต",
        )
        self.placeholder.pack(fill="both", expand=True)

        ttk.Label(
            self, style="Muted.TLabel",
            text="คอลัมน์ \"แถว\" คือเลขแถวเดียวกับใน Excel (แถว 1 = หัวตาราง) ใช้เลือกช่วงแถวในหน้าตรวจสอบและรัน",
        ).pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        pass

    def open_file(self) -> None:
        initial = os.path.dirname(self.app.data_path) if self.app.data_path else os.path.expanduser("~")
        path = filedialog.askopenfilename(parent=self, title="เปิดไฟล์ข้อมูล", filetypes=FILETYPES, initialdir=initial)
        if path:
            self.load(path)

    def open_sample(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="เปิดไฟล์ตัวอย่าง", filetypes=FILETYPES,
                                          initialdir=samples_dir())
        if path:
            self.load(path)

    def reload(self) -> None:
        if self.app.data_path:
            self.load(self.app.data_path, self.app.data_sheet)

    def load(self, path: str, sheet: str | None = None) -> None:
        try:
            table = load_table(path, sheet or None)
        except DataError as exc:
            messagebox.showerror("เปิดไฟล์ไม่ได้", str(exc), parent=self)
            return
        except OSError as exc:
            messagebox.showerror("เปิดไฟล์ไม่ได้", f"{exc}\n\nถ้าไฟล์เปิดค้างอยู่ใน Excel ให้ปิดก่อนแล้วลองใหม่", parent=self)
            return
        self.app.set_table(table, path, sheet)
        self.show_table()

    def show_table(self) -> None:
        table = self.app.table
        if table is None:
            return
        if table.sheets:
            self.sheet_box.configure(values=table.sheets)
            self.sheet_var.set(self.app.data_sheet or table.sheets[0])
            self.sheet_frame.pack(side="left")
        else:
            self.sheet_frame.pack_forget()
        self.reload_btn.configure(state="normal")
        rng = f"แถว {table.first_line}–{table.last_line}" if table.rows else "ไม่มีแถวข้อมูล"
        self.info.configure(
            text=f"{os.path.basename(table.source)}  ·  {table.info}  ·  {len(table.rows):,} แถว ({rng})  ·  {len(table.columns)} คอลัมน์"
        )

        f = tkfont.Font(font=self.app.fonts["base"])
        bold = tkfont.Font(font=self.app.fonts["bold"])
        cols = [("__line", "แถว", 56, "e")]
        sample = table.rows[:50]
        for i, c in enumerate(table.columns):
            w = bold.measure(c) + 28
            for r in sample:
                w = max(w, f.measure(to_text(r.get(c))) + 20)
            cols.append((f"c{i}", c, min(max(w, 70), 320), "w"))
        self.placeholder.pack_forget()
        self.table_view.pack(fill="both", expand=True)
        self.table_view.set_columns(cols)
        tree = self.table_view.tree
        for n, r in enumerate(table.rows[:MAX_SHOW]):
            tree.insert("", "end", values=[r.line] + [to_text(r.get(c)) for c in table.columns],
                        tags=("odd",) if n % 2 else ())
        if len(table.rows) > MAX_SHOW:
            self.info.configure(text=self.info.cget("text") + f"  ·  แสดง {MAX_SHOW:,} แถวแรก")
