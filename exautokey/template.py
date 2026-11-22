"""เทมเพลต = ลำดับขั้นตอนการคีย์ 1 เอกสารในหน้าจอ Express

แบ่งเป็น 3 ส่วน
    header  ส่วนหัวเอกสาร  ทำ 1 ครั้งต่อเอกสาร (ใช้ค่าจากแถวแรกของเอกสาร)
    lines   รายการ         ทำซ้ำทุกแถวของเอกสาร
    footer  ท้ายเอกสาร      ทำ 1 ครั้งต่อเอกสาร เช่น กดบันทึก
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field

from .formats import normalize_spec

STEP_KINDS = {
    "field": "ช่องข้อมูล",
    "text": "ข้อความคงที่",
    "keys": "กดปุ่ม",
    "wait": "รอ",
    "pause": "หยุดรอผู้ใช้",
}
SECTIONS = {
    "header": "ส่วนหัวเอกสาร",
    "lines": "รายการ (ทำซ้ำทุกแถว)",
    "footer": "ท้ายเอกสาร",
}
INPUT_MODES = {
    "unicode": "พิมพ์ทีละตัวอักษร",
    "paste": "วางผ่าน Clipboard (Ctrl+V)",
}


@dataclass
class Step:
    kind: str = "field"
    column: str = ""
    value: str = ""
    fmt: dict = field(default_factory=lambda: {"type": "text"})
    before: str = ""
    then: str = "{ENTER}"
    required: bool = False
    ms: int = 0
    note: str = ""

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind}
        if self.kind == "field":
            d.update(column=self.column, format=self.fmt)
            if self.before:
                d["before"] = self.before
            d["then"] = self.then
            if self.required:
                d["required"] = True
        elif self.kind == "text":
            d.update(value=self.value, then=self.then)
        elif self.kind in ("keys", "pause"):
            d["value"] = self.value
        elif self.kind == "wait":
            d["ms"] = self.ms
        if self.note:
            d["note"] = self.note
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Step":
        kind = d.get("kind", "field")
        if kind not in STEP_KINDS:
            raise ValueError(f"ไม่รู้จักประเภทขั้นตอน \"{kind}\"")
        return cls(
            kind=kind,
            column=str(d.get("column", "")),
            value=str(d.get("value", "")),
            fmt=normalize_spec(d.get("format")),
            before=str(d.get("before", "")),
            then=str(d.get("then", "{ENTER}" if kind in ("field", "text") else "")),
            required=bool(d.get("required", False)),
            ms=int(d.get("ms", 0) or 0),
            note=str(d.get("note", "")),
        )

    def copy(self) -> "Step":
        return Step.from_dict(json.loads(json.dumps(self.to_dict())))


@dataclass
class Settings:
    key_delay_ms: int = 30
    step_delay_ms: int = 150
    doc_delay_ms: int = 1000
    start_delay_s: int = 3
    input_mode: str = "unicode"

    @classmethod
    def from_dict(cls, d: dict | None) -> "Settings":
        d = d or {}
        s = cls()
        for k in ("key_delay_ms", "step_delay_ms", "doc_delay_ms", "start_delay_s"):
            if k in d:
                setattr(s, k, max(0, int(d[k])))
        mode = d.get("input_mode", s.input_mode)
        s.input_mode = mode if mode in INPUT_MODES else "unicode"
        return s


@dataclass
class Template:
    name: str = "เทมเพลตใหม่"
    description: str = ""
    window_title: str = "Express"
    group_by: str = ""
    header: list[Step] = field(default_factory=list)
    lines: list[Step] = field(default_factory=list)
    footer: list[Step] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
    path: str = ""

    def section(self, name: str) -> list[Step]:
        return getattr(self, name)

    def all_steps(self):
        for sec in SECTIONS:
            for idx, step in enumerate(self.section(sec)):
                yield sec, idx, step

    def columns_used(self) -> list[str]:
        """คอลัมน์ที่เทมเพลตต้องใช้ เรียงตามลำดับที่ปรากฏ"""
        cols: list[str] = []
        if self.group_by:
            cols.append(self.group_by)
        for _, _, step in self.all_steps():
            if step.kind == "field" and step.column and step.column not in cols:
                cols.append(step.column)
        return cols

    def to_dict(self) -> dict:
        return {
            "format": "ex-autokey-template",
            "version": 1,
            "name": self.name,
            "description": self.description,
            "window_title": self.window_title,
            "group_by": self.group_by,
            "settings": asdict(self.settings),
            **{sec: [s.to_dict() for s in self.section(sec)] for sec in SECTIONS},
        }

    @classmethod
    def from_dict(cls, d: dict, path: str = "") -> "Template":
        if d.get("format", "ex-autokey-template") != "ex-autokey-template":
            raise ValueError("ไฟล์นี้ไม่ใช่เทมเพลตของ EX-AutoKey")
        return cls(
            name=str(d.get("name", "เทมเพลต")),
            description=str(d.get("description", "")),
            window_title=str(d.get("window_title", "")),
            group_by=str(d.get("group_by", "") or ""),
            header=[Step.from_dict(x) for x in d.get("header", [])],
            lines=[Step.from_dict(x) for x in d.get("lines", [])],
            footer=[Step.from_dict(x) for x in d.get("footer", [])],
            settings=Settings.from_dict(d.get("settings")),
            path=path,
        )

    @classmethod
    def load(cls, path: str) -> "Template":
        with open(path, encoding="utf-8-sig") as fh:
            return cls.from_dict(json.load(fh), path=path)

    def save(self, path: str | None = None) -> str:
        path = path or self.path
        if not path:
            raise ValueError("ยังไม่ได้ระบุที่บันทึกเทมเพลต")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        self.path = path
        return path

    def copy(self) -> "Template":
        return Template.from_dict(json.loads(json.dumps(self.to_dict())))


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return (name or "template")[:80]


def list_templates(folder: str) -> tuple[list[Template], list[str]]:
    """คืน (เทมเพลตที่อ่านได้, ข้อความผิดพลาดของไฟล์ที่อ่านไม่ได้)"""
    out: list[Template] = []
    errors: list[str] = []
    if not os.path.isdir(folder):
        return out, errors
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith(".json"):
            try:
                out.append(Template.load(os.path.join(folder, fn)))
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"{fn}: {exc}")
    return out, errors
