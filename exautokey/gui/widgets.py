"""วิดเจ็ตที่ใช้ซ้ำหลายหน้า"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .theme import C


def card(parent: tk.Misc, padding=14) -> ttk.Frame:
    return ttk.Frame(parent, style="Card.TFrame", padding=padding)


class ScrollTree(ttk.Frame):
    """Treeview พร้อมแถบเลื่อนแนวตั้งและแนวนอน"""

    def __init__(self, master: tk.Misc, columns: list[tuple[str, str, int, str]] | None = None,
                 selectmode: str = "browse", height: int = 10):
        super().__init__(master, style="Plain.TFrame")
        self.tree = ttk.Treeview(self, show="headings", selectmode=selectmode, height=height)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.tag_configure("error", background=C["err_bg"])
        self.tree.tag_configure("warning", background=C["warn_bg"])
        self.tree.tag_configure("pause", background=C["warn_bg"])
        self.tree.tag_configure("odd", background="#fafbfd")
        if columns:
            self.set_columns(columns)

    def set_columns(self, columns: list[tuple[str, str, int, str]]) -> None:
        """columns = [(id, หัวคอลัมน์, ความกว้าง, anchor)]"""
        self.clear()
        ids = [c[0] for c in columns]
        self.tree.configure(columns=ids)
        for cid, heading, width, anchor in columns:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, minwidth=40, anchor=anchor, stretch=False)
        if columns:
            self.tree.column(ids[-1], stretch=True)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def selected_index(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.index(sel[0])


class StatTile(tk.Frame):
    def __init__(self, master: tk.Misc, label: str, fonts: dict, color: str | None = None):
        super().__init__(master, bg=C["tile"], highlightbackground=C["line"], highlightthickness=1, padx=14, pady=8)
        self.color = color or C["text"]
        self.value = tk.Label(self, text="–", font=fonts["big"], bg=C["tile"], fg=C["muted"])
        self.value.pack(anchor="w")
        tk.Label(self, text=label, font=fonts["small"], bg=C["tile"], fg=C["muted"]).pack(anchor="w")

    def set(self, value: int | str | None, highlight: bool = True) -> None:
        if value is None:
            self.value.configure(text="–", fg=C["muted"])
        else:
            self.value.configure(text=str(value), fg=self.color if highlight else C["text"])


class LogBox(ttk.Frame):
    def __init__(self, master: tk.Misc, fonts: dict, height: int = 8):
        super().__init__(master, style="Plain.TFrame")
        self.text = tk.Text(self, height=height, wrap="word", font=fonts["base"], relief="flat",
                            bg="white", fg=C["text"], padx=10, pady=8, state="disabled",
                            highlightthickness=0, spacing1=2, spacing3=2)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text.tag_configure("muted", foreground=C["muted"])
        self.text.tag_configure("ok", foreground=C["ok"])
        self.text.tag_configure("err", foreground=C["err"])
        self.text.tag_configure("warn", foreground=C["warn"])
        self.text.tag_configure("head", font=fonts["bold"])

    def set(self, content: str, tag: str | None = None) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self._insert_lines(content, tag)
        self.text.configure(state="disabled")
        self.text.see("1.0")

    def _insert_lines(self, content: str, tag: str | None) -> None:
        for line in content.splitlines(keepends=True):
            t = tag or ("head" if line.startswith("■") else None)
            self.text.insert("end", line, t or ())

    def append(self, line: str, tag: str | None = None) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n", tag or ())
        self.text.configure(state="disabled")
        self.text.see("end")


def center_on(win: tk.Toplevel, parent: tk.Misc) -> None:
    win.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    win.geometry(f"+{max(px + (pw - w) // 2, 0)}+{max(py + (ph - h) // 3, 0)}")
