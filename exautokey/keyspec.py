"""แปลงข้อความกำหนดปุ่ม (คล้าย SendKeys) เป็นลำดับคำสั่งกดปุ่ม

ไวยากรณ์ที่รองรับ
    {ENTER} {TAB} {ESC} {F1}..{F12} {UP} {DOWN} {LEFT} {RIGHT}
    {HOME} {END} {PGUP} {PGDN} {INS} {DEL} {BS} {SPACE}
    {TAB 3}        กด TAB 3 ครั้ง
    {WAIT 500}     รอ 500 มิลลิวินาที
    ^ = Ctrl, + = Shift, % = Alt  เช่น ^s  %{F4}  +{TAB}
    {{} {}} {^} {+} {%}  พิมพ์อักขระนั้นตรง ๆ
    ตัวอักษรอื่น ๆ จะถูกพิมพ์ตามที่เขียน
"""

from __future__ import annotations

from dataclasses import dataclass, field


class KeySpecError(ValueError):
    """ข้อความกำหนดปุ่มไม่ถูกต้อง"""


@dataclass(frozen=True)
class KeyPress:
    key: str
    mods: tuple[str, ...] = ()
    repeat: int = 1

    def label(self) -> str:
        prefix = "".join(m + "+" for m in self.mods)
        rep = f" ×{self.repeat}" if self.repeat > 1 else ""
        return f"[{prefix}{self.key}{rep}]"


@dataclass(frozen=True)
class TypeText:
    text: str

    def label(self) -> str:
        return f'พิมพ์ "{self.text}"'


@dataclass(frozen=True)
class Wait:
    ms: int

    def label(self) -> str:
        return f"(รอ {self.ms} ms)"


Token = KeyPress | TypeText | Wait

# รหัส Virtual-Key ของ Windows
VK: dict[str, int] = {
    "ENTER": 0x0D,
    "TAB": 0x09,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "BACKSPACE": 0x08,
    "DELETE": 0x2E,
    "INSERT": 0x2D,
    "HOME": 0x24,
    "END": 0x23,
    "PGUP": 0x21,
    "PGDN": 0x22,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
    "CTRL": 0x11,
    "SHIFT": 0x10,
    "ALT": 0x12,
}
VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
VK.update({chr(c): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})

ALIASES = {
    "RETURN": "ENTER",
    "ESCAPE": "ESC",
    "BS": "BACKSPACE",
    "BKSP": "BACKSPACE",
    "DEL": "DELETE",
    "INS": "INSERT",
    "PAGEUP": "PGUP",
    "PAGEDOWN": "PGDN",
    "PGDOWN": "PGDN",
}

# ปุ่มที่ต้องส่งแบบ extended key
EXTENDED = {"DELETE", "INSERT", "HOME", "END", "PGUP", "PGDN", "UP", "DOWN", "LEFT", "RIGHT"}

MOD_CHARS = {"^": "CTRL", "+": "SHIFT", "%": "ALT"}
MOD_ORDER = ("CTRL", "SHIFT", "ALT")

# ปุ่มที่เสนอในหน้าจอแก้ไข
COMMON_KEYS = [
    "{ENTER}", "{TAB}", "+{TAB}", "{ESC}", "{DOWN}", "{UP}",
    "{F2}", "{F3}", "{F5}", "{F8}", "{F9}", "{F10}", "^s", "{WAIT 500}",
]


@dataclass
class _State:
    tokens: list[Token] = field(default_factory=list)
    text: list[str] = field(default_factory=list)
    mods: list[str] = field(default_factory=list)

    def flush(self) -> None:
        if self.text:
            self.tokens.append(TypeText("".join(self.text)))
            self.text.clear()

    def add_mod(self, mod: str, spec: str) -> None:
        if mod in self.mods:
            raise KeySpecError(f"ใช้ปุ่ม {mod} ซ้ำติดกันใน \"{spec}\"")
        self.flush()
        self.mods.append(mod)

    def take_mods(self) -> tuple[str, ...]:
        mods = tuple(m for m in MOD_ORDER if m in self.mods)
        self.mods.clear()
        return mods


def parse_keys(spec: str | None) -> list[Token]:
    """แปลงข้อความกำหนดปุ่มเป็นลิสต์ของ KeyPress / TypeText / Wait"""
    if not spec:
        return []
    st = _State()
    i = 0
    n = len(spec)
    while i < n:
        c = spec[i]
        if c in MOD_CHARS:
            st.add_mod(MOD_CHARS[c], spec)
            i += 1
            continue
        if c == "{":
            if spec.startswith("{}}", i):
                inner, i = "}", i + 3
            else:
                j = spec.find("}", i + 1)
                if j == -1:
                    raise KeySpecError(f"ไม่พบ '}}' ปิดท้ายใน \"{spec}\"")
                inner, i = spec[i + 1 : j], j + 1
            _brace(st, inner, spec)
            continue
        # อักขระธรรมดา
        if st.mods:
            key = c.upper()
            if key not in VK or len(key) != 1:
                raise KeySpecError(f"ใช้ Ctrl/Shift/Alt กับ \"{c}\" ไม่ได้ ให้ใช้กับตัวอักษร A-Z, 0-9 หรือ {{ปุ่ม}}")
            st.tokens.append(KeyPress(key, st.take_mods()))
        else:
            st.text.append(c)
        i += 1
    if st.mods:
        raise KeySpecError(f"มี ^ + % ค้างท้ายข้อความ \"{spec}\" โดยไม่มีปุ่มตามหลัง")
    st.flush()
    return st.tokens


def _brace(st: _State, inner: str, spec: str) -> None:
    if len(inner) == 1 and not inner.isalnum():
        # อักขระพิเศษแบบ literal เช่น {+} {^}
        if st.mods:
            raise KeySpecError(f"ใช้ Ctrl/Shift/Alt กับ \"{{{inner}}}\" ไม่ได้")
        st.text.append(inner)
        return
    parts = inner.split()
    if not parts or len(parts) > 2:
        raise KeySpecError(f"รูปแบบ \"{{{inner}}}\" ไม่ถูกต้อง")
    name = ALIASES.get(parts[0].upper(), parts[0].upper())
    count = 1
    if len(parts) == 2:
        try:
            count = int(parts[1])
        except ValueError:
            raise KeySpecError(f"จำนวนครั้งใน \"{{{inner}}}\" ต้องเป็นตัวเลข") from None
        if count < 1:
            raise KeySpecError(f"จำนวนครั้งใน \"{{{inner}}}\" ต้องมากกว่า 0")
    if name == "WAIT":
        if len(parts) != 2:
            raise KeySpecError("ต้องระบุเวลาเป็นมิลลิวินาที เช่น {WAIT 500}")
        if st.mods:
            raise KeySpecError("ใช้ Ctrl/Shift/Alt กับ {WAIT} ไม่ได้")
        st.flush()
        st.tokens.append(Wait(count))
        return
    if name not in VK or name in ("CTRL", "SHIFT", "ALT"):
        raise KeySpecError(f"ไม่รู้จักปุ่ม \"{{{inner}}}\"")
    if count > 50:
        raise KeySpecError(f"กดซ้ำได้ไม่เกิน 50 ครั้งต่อคำสั่ง (\"{{{inner}}}\")")
    st.flush()
    st.tokens.append(KeyPress(name, st.take_mods(), count))


def validate_keys(spec: str | None) -> str | None:
    """คืนข้อความผิดพลาด หรือ None ถ้าถูกต้อง"""
    try:
        parse_keys(spec)
    except KeySpecError as exc:
        return str(exc)
    return None


def describe(tokens: list[Token]) -> str:
    return " ".join(t.label() for t in tokens)
