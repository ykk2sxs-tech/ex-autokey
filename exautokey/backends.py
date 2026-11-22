"""ตัวส่งปุ่มไปยังหน้าต่างเป้าหมาย

WindowsBackend (winbackend.py) ส่งปุ่มจริงด้วย Win32 SendInput
RecordingBackend ใช้ในการทดสอบ จะบันทึกสิ่งที่ส่งไว้ ไม่ได้กดปุ่มจริง
"""

from __future__ import annotations

import sys


class BackendError(Exception):
    """ส่งปุ่มไม่ได้ / หาหน้าต่างเป้าหมายไม่พบ"""


class Backend:
    name = "base"
    abort_hint = ""

    def notify(self, text: str) -> None:
        """ส่งข้อความแจ้งเตือนไปที่หน้าจอ (Runner จะแทนที่ฟังก์ชันนี้)"""

    def list_windows(self) -> list[str]:
        return []

    def prepare(self, window_title: str) -> str:
        """หาหน้าต่างเป้าหมาย คืนชื่อหน้าต่างที่พบ"""
        raise NotImplementedError

    def activate(self) -> None:
        raise NotImplementedError

    def target_active(self) -> bool:
        raise NotImplementedError

    def abort_requested(self) -> bool:
        return False

    def type_char(self, ch: str) -> None:
        raise NotImplementedError

    def paste_text(self, text: str) -> None:
        raise NotImplementedError

    def press(self, key: str, mods: tuple[str, ...] = ()) -> None:
        raise NotImplementedError

    def before_text(self, text: str) -> None:
        """เรียกก่อนพิมพ์ข้อความแต่ละช่อง (ใช้สลับแป้นพิมพ์ภาษาไทย)"""


class RecordingBackend(Backend):
    name = "recording"

    def __init__(self, active: bool = True, windows: list[str] | None = None):
        self.active = active
        self.abort = False
        self.sent: list[tuple] = []
        self.windows = windows if windows is not None else ["Express"]
        self.target = ""

    def list_windows(self) -> list[str]:
        return list(self.windows)

    def prepare(self, window_title: str) -> str:
        for w in self.windows:
            if window_title.lower() in w.lower():
                self.target = w
                return w
        raise BackendError(f"ไม่พบหน้าต่างที่มีชื่อ \"{window_title}\"")

    def activate(self) -> None:
        self.sent.append(("activate",))

    def target_active(self) -> bool:
        return self.active

    def abort_requested(self) -> bool:
        return self.abort

    def type_char(self, ch: str) -> None:
        self.sent.append(("char", ch))

    def paste_text(self, text: str) -> None:
        self.sent.append(("paste", text))

    def press(self, key: str, mods: tuple[str, ...] = ()) -> None:
        self.sent.append(("key", key, tuple(mods)))

    def typed(self) -> str:
        """จำลองผลลัพธ์เป็นข้อความ เพื่อให้อ่าน/ตรวจในการทดสอบได้ง่าย"""
        out = []
        for ev in self.sent:
            if ev[0] == "char":
                out.append(ev[1])
            elif ev[0] == "paste":
                out.append(ev[1])
            elif ev[0] == "key":
                mods = "".join(m + "+" for m in ev[2])
                out.append(f"<{mods}{ev[1]}>")
        return "".join(out)


def get_backend() -> Backend:
    if sys.platform != "win32":
        raise BackendError("การคีย์จริงทำได้เฉพาะบน Windows ที่เปิดโปรแกรม Express อยู่")
    from .winbackend import WindowsBackend

    return WindowsBackend()
