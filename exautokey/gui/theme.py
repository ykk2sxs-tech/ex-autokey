"""สี ฟอนต์ และสไตล์ของหน้าจอ"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

C = {
    "bg": "#f3f5f9",
    "card": "#ffffff",
    "line": "#dde3ec",
    "text": "#1d2533",
    "muted": "#677489",
    "side": "#13203a",
    "side_hover": "#1c2c4d",
    "side_active": "#25395f",
    "side_text": "#e3e9f5",
    "side_muted": "#8fa0bf",
    "accent": "#f5a524",
    "accent_dark": "#d98a0b",
    "primary": "#1e6fd9",
    "primary_dark": "#1859b0",
    "ok": "#1f8a4c",
    "err": "#c0392b",
    "warn": "#a86a12",
    "ok_bg": "#e6f5ec",
    "err_bg": "#fdecea",
    "warn_bg": "#fdf4e3",
    "sel": "#d6e6fb",
    "tile": "#f7f9fc",
}

FONT_CANDIDATES = (
    "Leelawadee UI",
    "Leelawadee",
    "Tahoma",
    "Noto Sans Thai UI",
    "Noto Sans Thai",
    "Loma",
    "Garuda",
)


def pick_family(root: tk.Misc) -> str:
    families = set(tkfont.families(root))
    for fam in FONT_CANDIDATES:
        if fam in families:
            return fam
    return tkfont.nametofont("TkDefaultFont").actual("family")


def setup(root: tk.Tk) -> dict[str, tuple]:
    fam = pick_family(root)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont", "TkFixedFont"):
        try:
            tkfont.nametofont(name).configure(family=fam, size=10)
        except tk.TclError:
            pass
    fonts = {
        "base": (fam, 10),
        "bold": (fam, 10, "bold"),
        "small": (fam, 9),
        "h1": (fam, 17, "bold"),
        "h2": (fam, 12, "bold"),
        "big": (fam, 22, "bold"),
        "logo": (fam, 19, "bold"),
        "nav": (fam, 11, "bold"),
        "num": (fam, 12, "bold"),
    }
    linespace = tkfont.Font(root=root, family=fam, size=10).metrics("linespace")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=C["bg"], foreground=C["text"], font=fonts["base"],
                    bordercolor=C["line"], lightcolor=C["line"], darkcolor=C["line"], focuscolor=C["primary"])
    style.configure("TFrame", background=C["bg"])
    style.configure("Card.TFrame", background=C["card"], relief="solid", borderwidth=1)
    style.configure("Plain.TFrame", background=C["card"])
    style.configure("TLabel", background=C["bg"])
    style.configure("Card.TLabel", background=C["card"])
    style.configure("Muted.TLabel", foreground=C["muted"])
    style.configure("CardMuted.TLabel", background=C["card"], foreground=C["muted"], font=fonts["small"])
    style.configure("H1.TLabel", font=fonts["h1"])
    style.configure("H2.TLabel", font=fonts["h2"], background=C["card"])
    style.configure("Err.TLabel", background=C["card"], foreground=C["err"])
    style.configure("Ok.TLabel", background=C["card"], foreground=C["ok"])

    style.configure("TButton", padding=(10, 5), background="#e8ecf2", width=0)
    style.map("TButton", background=[("disabled", "#f1f3f6"), ("active", "#dce3ec")],
              foreground=[("disabled", "#a3acb9")])
    style.configure("Accent.TButton", background=C["accent"], foreground="#231600", font=fonts["bold"],
                    bordercolor=C["accent_dark"], lightcolor=C["accent"], darkcolor=C["accent_dark"])
    style.map("Accent.TButton", background=[("disabled", "#f6deb0"), ("active", C["accent_dark"])])
    style.configure("Primary.TButton", background=C["primary"], foreground="white", font=fonts["bold"],
                    bordercolor=C["primary_dark"], lightcolor=C["primary"], darkcolor=C["primary_dark"])
    style.map("Primary.TButton", background=[("disabled", "#a7c2ea"), ("active", C["primary_dark"])],
              foreground=[("disabled", "#eef3fb")])
    style.configure("Danger.TButton", background="#fbe4e1", foreground=C["err"], font=fonts["bold"])
    style.map("Danger.TButton", background=[("disabled", "#f6efee"), ("active", "#f6cdc7")],
              foreground=[("disabled", "#d9a7a1")])
    style.configure("Small.TButton", padding=(6, 3), font=fonts["small"])

    style.configure("Treeview", rowheight=int(linespace * 1.75), background="white",
                    fieldbackground="white", bordercolor=C["line"])
    style.configure("Treeview.Heading", background="#eef1f6", font=fonts["bold"], relief="flat", padding=(6, 5))
    style.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", C["text"])])
    style.map("Treeview.Heading", background=[("active", "#e3e8f0")])

    style.configure("TNotebook", background=C["card"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", padding=(16, 7), background="#e8ecf2")
    style.map("TNotebook.Tab", background=[("selected", C["card"])], expand=[("selected", (0, 2, 0, 0))])

    for w in ("TCheckbutton", "TRadiobutton"):
        style.configure(w, background=C["card"])
        style.map(w, background=[("active", C["card"])])
    style.configure("TEntry", padding=4)
    style.configure("TCombobox", padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", "white")], selectbackground=[("readonly", "white")],
              selectforeground=[("readonly", C["text"])])
    style.configure("TSpinbox", padding=4)
    style.configure("Horizontal.TProgressbar", troughcolor="#e6eaf0", background=C["primary"],
                    thickness=12, bordercolor="#e6eaf0", lightcolor=C["primary"], darkcolor=C["primary"])
    style.configure("TSeparator", background=C["line"])

    root.configure(background=C["bg"])
    root.option_add("*TCombobox*Listbox.font", fonts["base"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["sel"])
    root.option_add("*TCombobox*Listbox.selectForeground", C["text"])
    return fonts
