"""หน้าต่างหลักของ EX-AutoKey"""

from __future__ import annotations

import os
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import APP_NAME, __version__
from ..data import Table
from ..engine import Plan, Runner
from ..paths import templates_dir
from ..template import Step, Template, list_templates, safe_filename
from .data_page import DataPage
from .run_page import RunPage
from .template_page import TemplatePage, ask_name
from .theme import C, setup

NAV = [
    ("data", "1", "ไฟล์ข้อมูล"),
    ("template", "2", "เทมเพลต"),
    ("run", "3", "ตรวจสอบและรัน"),
]


class NavItem(tk.Frame):
    def __init__(self, master: tk.Misc, app: "App", key: str, number: str, title: str):
        super().__init__(master, bg=C["side"], cursor="hand2", padx=16, pady=10)
        self.app = app
        self.key = key
        self.active = False
        self.num = tk.Label(self, text=number, width=2, font=app.fonts["num"], bg=C["side_hover"], fg=C["side_text"])
        self.num.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 12), ipady=3)
        self.title_lbl = tk.Label(self, text=title, font=app.fonts["nav"], bg=C["side"], fg=C["side_text"], anchor="w")
        self.title_lbl.grid(row=0, column=1, sticky="w")
        self.sub = tk.Label(self, text="", font=app.fonts["small"], bg=C["side"], fg=C["side_muted"], anchor="w",
                            justify="left", wraplength=190)
        self.sub.grid(row=1, column=1, sticky="w")
        for w in (self, self.num, self.title_lbl, self.sub):
            w.bind("<Button-1>", lambda e: app.show_page(key))
            w.bind("<Enter>", lambda e: self._paint(hover=True))
            w.bind("<Leave>", lambda e: self._paint(hover=False))

    def _paint(self, hover: bool = False) -> None:
        bg = C["side_active"] if self.active else (C["side_hover"] if hover else C["side"])
        for w in (self, self.title_lbl, self.sub):
            w.configure(bg=bg)
        self.num.configure(bg=C["accent"] if self.active else C["side_hover"],
                           fg="#231600" if self.active else C["side_text"])

    def set_active(self, active: bool) -> None:
        self.active = active
        self._paint()

    def set_sub(self, text: str) -> None:
        self.sub.configure(text=text)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} · คีย์ข้อมูลเข้าโปรแกรมบัญชีอัตโนมัติ")
        self.geometry("1240x800")
        self.minsize(1060, 680)
        self.fonts = setup(self)

        self.table: Table | None = None
        self.data_path = ""
        self.data_sheet: str | None = None
        self.templates: list[Template] = []
        self.template = Template()
        self.template_index: int | None = None
        self.template_dirty = False
        self.plan: Plan | None = None
        self.runner: Runner | None = None
        self.events: queue.Queue = queue.Queue()
        self.current_page = ""

        self._build()
        self.reload_templates()
        self.show_page("data")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(80, self._poll_events)

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        side = tk.Frame(self, bg=C["side"], width=250)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = tk.Frame(side, bg=C["side"], padx=20, pady=22)
        logo.pack(fill="x")
        tk.Label(logo, text="EX", font=self.fonts["logo"], bg=C["accent"], fg="#231600", padx=6).pack(side="left")
        tk.Label(logo, text=" AutoKey", font=self.fonts["logo"], bg=C["side"], fg="white").pack(side="left")
        tk.Label(side, text="คีย์ข้อมูลจาก Excel / CSV\nเข้าโปรแกรมบัญชี Express", font=self.fonts["small"],
                 bg=C["side"], fg=C["side_muted"], justify="left", anchor="w", padx=20).pack(fill="x", pady=(0, 18))

        self.nav: dict[str, NavItem] = {}
        for key, num, title in NAV:
            item = NavItem(side, self, key, num, title)
            item.pack(fill="x")
            self.nav[key] = item

        safety = tk.Frame(side, bg=C["side_hover"], padx=14, pady=12)
        safety.pack(side="bottom", fill="x", padx=14, pady=14)
        tk.Label(safety, text="หยุดฉุกเฉินระหว่างคีย์", font=self.fonts["bold"], bg=C["side_hover"], fg=C["accent"],
                 anchor="w").pack(fill="x")
        tk.Label(safety, text="• ลากเมาส์ไปมุมซ้ายบนสุดของจอ\n• หรือกด Ctrl + Shift + Q\n• คลิกหน้าต่างอื่น = หยุดพักทันที",
                 font=self.fonts["small"], bg=C["side_hover"], fg=C["side_text"], justify="left", anchor="w",
                 wraplength=200).pack(fill="x", pady=(4, 0))
        tk.Label(side, text=f"เวอร์ชัน {__version__}", font=self.fonts["small"], bg=C["side"], fg=C["side_muted"]).pack(
            side="bottom", anchor="w", padx=20)

        main = ttk.Frame(self, padding=(24, 18, 24, 18))
        main.pack(side="left", fill="both", expand=True)
        head = ttk.Frame(main)
        head.pack(fill="x", pady=(0, 14))
        self.h_title = ttk.Label(head, text="", style="H1.TLabel")
        self.h_title.pack(anchor="w")
        self.h_sub = ttk.Label(head, text="", style="Muted.TLabel")
        self.h_sub.pack(anchor="w")

        body = ttk.Frame(main)
        body.pack(fill="both", expand=True)
        self.pages = {
            "data": DataPage(body, self),
            "template": TemplatePage(body, self),
            "run": RunPage(body, self),
        }

    def show_page(self, key: str) -> None:
        for k, page in self.pages.items():
            if k == key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for k, item in self.nav.items():
            item.set_active(k == key)
        page = self.pages[key]
        self.h_title.configure(text=page.title)
        self.h_sub.configure(text=page.subtitle)
        self.current_page = key
        page.on_show()

    def update_nav(self) -> None:
        if self.table is None:
            self.nav["data"].set_sub("ยังไม่ได้เปิดไฟล์")
        else:
            self.nav["data"].set_sub(f"{os.path.basename(self.data_path)}\n{len(self.table.rows):,} แถว")
        self.nav["template"].set_sub(self.template.name + ("  • ยังไม่บันทึก" if self.template_dirty else ""))
        run_page: RunPage = self.pages["run"]  # type: ignore[assignment]
        if run_page.running:
            text = "กำลังคีย์…"
        elif self.plan is None:
            text = "ยังไม่ได้ตรวจสอบ"
        elif self.plan.ok:
            text = f"พร้อมคีย์ {len(self.plan.docs):,} เอกสาร"
        else:
            text = f"มีข้อผิดพลาด {len(self.plan.errors):,} รายการ"
        self.nav["run"].set_sub(text)

    # ------------------------------------------------------------------ data
    def set_table(self, table: Table, path: str, sheet: str | None) -> None:
        self.table = table
        self.data_path = path
        self.data_sheet = sheet
        self.pages["run"].data_changed()
        self.pages["template"].refresh_columns()
        self.invalidate_plan()

    def show_data_line(self, line: int) -> None:
        self.show_page("data")
        tree = self.pages["data"].table_view.tree
        for iid in tree.get_children():
            if str(tree.set(iid, "__line")) == str(line):
                tree.selection_set(iid)
                tree.see(iid)
                break

    # ------------------------------------------------------------------ plan
    def invalidate_plan(self) -> None:
        if not hasattr(self, "pages"):
            return
        self.plan = None
        self.pages["run"].plan_invalidated()
        self.update_nav()

    def set_plan(self, plan: Plan) -> None:
        self.plan = plan
        self.update_nav()

    # ------------------------------------------------------------------ templates
    def reload_templates(self, select_path: str | None = None) -> None:
        self.templates, errors = list_templates(templates_dir())
        if errors:
            messagebox.showwarning("อ่านเทมเพลตไม่ได้บางไฟล์", "\n".join(errors), parent=self)
        idx = 0 if self.templates else None
        if select_path:
            for i, t in enumerate(self.templates):
                if os.path.abspath(t.path) == os.path.abspath(select_path):
                    idx = i
        if idx is None:
            self._load_template(Template(header=[Step(kind="field")]), None)
        else:
            self._load_template(self.templates[idx].copy(), idx)

    def _load_template(self, t: Template, index: int | None) -> None:
        if index is not None:
            t.path = self.templates[index].path
        self.template = t
        self.template_index = index
        self.template_dirty = False
        self.pages["template"].load_template(t)
        self.invalidate_plan()

    def _confirm_discard(self) -> bool:
        if not self.template_dirty:
            return True
        ans = messagebox.askyesnocancel("เทมเพลตยังไม่บันทึก", f"บันทึกการแก้ไขเทมเพลต \"{self.template.name}\" ก่อนไหม?", parent=self)
        if ans is None:
            return False
        if ans:
            return self.save_template()
        return True

    def select_template(self, index: int) -> None:
        if index == self.template_index or index < 0:
            return
        if not self._confirm_discard():
            self.pages["template"].refresh_picker()
            return
        self._load_template(self.templates[index].copy(), index)

    def template_changed(self) -> None:
        self.template_dirty = True
        self.invalidate_plan()

    def save_template(self) -> bool:
        t = self.template
        if not t.name.strip():
            messagebox.showwarning("บันทึกเทมเพลต", "ใส่ชื่อเทมเพลตก่อน", parent=self)
            return False
        if t.path:
            # เทมเพลตเดิม: บันทึกทับไฟล์เดิม (ชื่อเทมเพลตเก็บอยู่ในไฟล์ ไม่ต้องเปลี่ยนชื่อไฟล์)
            target = t.path
        else:
            target = os.path.join(templates_dir(), safe_filename(t.name) + ".json")
            if os.path.exists(target) and not messagebox.askyesno(
                    "บันทึกเทมเพลต", f"มีไฟล์เทมเพลตชื่อ \"{os.path.basename(target)}\" อยู่แล้ว บันทึกทับไหม?", parent=self):
                return False
        try:
            t.save(target)
        except OSError as exc:
            messagebox.showerror("บันทึกเทมเพลตไม่ได้", str(exc), parent=self)
            return False
        self.reload_templates(select_path=target)
        return True

    def new_template(self) -> None:
        if not self._confirm_discard():
            return
        name = ask_name(self, "เทมเพลตใหม่", "เทมเพลตใหม่")
        if not name:
            return
        t = Template(name=name, header=[Step(kind="field")])
        self._load_template(t, None)
        self.template_dirty = True
        self.update_nav()
        self.pages["template"].refresh_picker()

    def duplicate_template(self) -> None:
        if not self._confirm_discard():
            return
        name = ask_name(self, "ทำสำเนาเทมเพลต", self.template.name + " (สำเนา)")
        if not name:
            return
        t = self.template.copy()
        t.name = name
        t.path = ""
        self._load_template(t, None)
        self.template_dirty = True
        self.update_nav()
        self.pages["template"].refresh_picker()

    def delete_template(self) -> None:
        t = self.template
        if not t.path:
            if messagebox.askyesno("ลบเทมเพลต", "เทมเพลตนี้ยังไม่ได้บันทึก ทิ้งการแก้ไขไหม?", parent=self):
                self.reload_templates()
            return
        if not messagebox.askyesno("ลบเทมเพลต", f"ลบเทมเพลต \"{t.name}\" ถาวรไหม?", parent=self):
            return
        try:
            os.remove(t.path)
        except OSError as exc:
            messagebox.showerror("ลบเทมเพลตไม่ได้", str(exc), parent=self)
            return
        self.reload_templates()

    def import_template(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, title="นำเข้าเทมเพลต", filetypes=[("เทมเพลต", "*.json")])
        if not path:
            return
        try:
            t = Template.load(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("นำเข้าเทมเพลตไม่ได้", str(exc), parent=self)
            return
        t.path = ""
        self._load_template(t, None)
        self.template_dirty = True
        self.update_nav()
        self.pages["template"].refresh_picker()

    # ------------------------------------------------------------------ runner events
    def post_event(self, kind: str, **data) -> None:
        """เรียกจาก thread ของ Runner: ส่งเข้าคิวแล้วให้ thread หน้าจอเป็นคนอัปเดต"""
        self.events.put((kind, data))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, data = self.events.get_nowait()
                self.pages["run"].handle_event(kind, data)
        except queue.Empty:
            pass
        self.after(80, self._poll_events)

    def bring_to_front(self) -> None:
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()
        if self.current_page != "run":
            self.show_page("run")

    def on_close(self) -> None:
        run_page: RunPage = self.pages["run"]  # type: ignore[assignment]
        if run_page.running:
            if not messagebox.askyesno("กำลังคีย์อยู่", "หยุดการคีย์และปิดโปรแกรมไหม?", parent=self):
                return
            if self.runner:
                self.runner.stop()
        if not self._confirm_discard():
            return
        self.destroy()


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main() -> None:
    _enable_dpi_awareness()
    app = App()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.pages["data"].load(sys.argv[1])
    app.mainloop()


if __name__ == "__main__":
    main()
