"""ส่งปุ่มจริงบน Windows ด้วย Win32 API ผ่าน ctypes (ไม่ต้องติดตั้งไลบรารีเพิ่ม)

ความปลอดภัย
- จำโปรเซสของหน้าต่าง Express ไว้ ถ้าหน้าต่างที่อยู่ด้านหน้าไม่ใช่โปรเซสนั้น Runner จะหยุดพักทันที
- หยุดฉุกเฉิน: เลื่อนเมาส์ไปมุมซ้ายบนสุดของจอหลัก หรือกด Ctrl+Shift+Q
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

from .backends import Backend, BackendError
from .keyspec import EXTENDED, VK

if sys.platform != "win32":  # pragma: no cover
    raise ImportError("winbackend ใช้ได้เฉพาะบน Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAPVK_VK_TO_VSC = 0

CF_TEXT = 1
CF_UNICODETEXT = 13
CF_LOCALE = 16
GMEM_MOVEABLE = 0x0002
LCID_THAI = 0x041E

SW_RESTORE = 9
WM_INPUTLANGCHANGEREQUEST = 0x0050
LANG_THAI = 0x041E

VK_CONTROL, VK_SHIFT, VK_Q = 0x11, 0x10, 0x51


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _INPUTUNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = (("type", wintypes.DWORD), ("u", _INPUTUNION))


WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.IsIconic.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = ()
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = (wintypes.HWND,)
user32.BringWindowToTop.restype = wintypes.BOOL
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.ShowWindow.restype = wintypes.BOOL
user32.GetLastActivePopup.argtypes = (wintypes.HWND,)
user32.GetLastActivePopup.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
user32.AttachThreadInput.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.OpenClipboard.argtypes = (wintypes.HWND,)
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = ()
user32.EmptyClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = ()
user32.CloseClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
user32.SetClipboardData.restype = wintypes.HANDLE
user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
user32.GetKeyboardLayout.restype = wintypes.HKL
user32.GetKeyboardLayoutList.argtypes = (ctypes.c_int, ctypes.POINTER(wintypes.HKL))
user32.GetKeyboardLayoutList.restype = ctypes.c_int
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostMessageW.restype = wintypes.BOOL

kernel32.GetCurrentThreadId.argtypes = ()
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = (wintypes.HANDLE,)
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = (wintypes.HANDLE,)
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = (wintypes.HANDLE,)
kernel32.GlobalFree.restype = wintypes.HANDLE


def _pid_of(hwnd) -> int:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _title_of(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def enum_windows() -> list[tuple[int, str, int]]:
    """หน้าต่างที่มองเห็นและมีชื่อ เรียงจากบนสุดลงล่าง: (hwnd, title, pid)"""
    found: list[tuple[int, str, int]] = []

    @WNDENUMPROC
    def cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = _title_of(hwnd)
            if title.strip():
                found.append((hwnd, title, _pid_of(hwnd)))
        return True

    user32.EnumWindows(cb, 0)
    return found


def _has_thai(text: str) -> bool:
    return any("฀" <= ch <= "๿" for ch in text)


class WindowsBackend(Backend):
    name = "windows"
    abort_hint = "เลื่อนเมาส์ไปมุมซ้ายบนสุดของจอ หรือกด Ctrl+Shift+Q"

    def __init__(self) -> None:
        self.hwnd = None
        self.pid = 0
        self.title = ""
        self._my_pid = os.getpid()
        self._thai_warned = False

    # ------------------------------------------------------------ หน้าต่าง
    def list_windows(self) -> list[str]:
        seen: list[str] = []
        for _, title, pid in enum_windows():
            if pid != self._my_pid and title not in seen:
                seen.append(title)
        return seen

    def prepare(self, window_title: str) -> str:
        needle = window_title.strip().lower()
        if not needle:
            raise BackendError("ยังไม่ได้ระบุชื่อหน้าต่าง Express")
        matches = [
            (hwnd, title, pid)
            for hwnd, title, pid in enum_windows()
            if pid != self._my_pid and needle in title.lower()
        ]
        if not matches:
            raise BackendError(f"ไม่พบหน้าต่างที่ชื่อมีคำว่า \"{window_title}\" ให้เปิดโปรแกรม Express ก่อน")
        pids = {pid for _, _, pid in matches}
        if len(pids) > 1:
            names = " / ".join(sorted({t for _, t, _ in matches})[:5])
            raise BackendError(
                f"พบหลายโปรแกรมที่ชื่อหน้าต่างมีคำว่า \"{window_title}\" ({names}) "
                "ให้ระบุชื่อหน้าต่างในเทมเพลตให้เจาะจงขึ้น หรือปิดโปรแกรมที่ไม่ใช้"
            )
        self.hwnd, self.title, self.pid = matches[0]
        return self.title

    def target_active(self) -> bool:
        fg = user32.GetForegroundWindow()
        return bool(fg) and self.pid != 0 and _pid_of(fg) == self.pid

    def activate(self) -> None:
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            raise BackendError("หน้าต่าง Express ถูกปิดไปแล้ว")
        if self.target_active():
            return
        if user32.IsIconic(self.hwnd):
            user32.ShowWindow(self.hwnd, SW_RESTORE)
        target = user32.GetLastActivePopup(self.hwnd) or self.hwnd
        fg = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        cur_tid = kernel32.GetCurrentThreadId()
        attached = bool(fg_tid and fg_tid != cur_tid and user32.AttachThreadInput(cur_tid, fg_tid, True))
        try:
            user32.BringWindowToTop(target)
            user32.SetForegroundWindow(target)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)

    def abort_requested(self) -> bool:
        pt = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(pt)) and 0 <= pt.x <= 2 and 0 <= pt.y <= 2:
            return True
        down = lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)  # noqa: E731
        return down(VK_CONTROL) and down(VK_SHIFT) and down(VK_Q)

    # ------------------------------------------------------------ แป้นพิมพ์
    @staticmethod
    def _send(inputs: list[INPUT]) -> None:
        arr = (INPUT * len(inputs))(*inputs)
        sent = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            err = ctypes.get_last_error()
            raise BackendError(
                f"ส่งปุ่มไม่สำเร็จ (Windows error {err}) ถ้า Express เปิดแบบ Run as administrator "
                "ให้เปิด EX-AutoKey แบบ administrator ด้วย"
            )

    @staticmethod
    def _vk_input(name: str, up: bool) -> INPUT:
        vk = VK[name]
        flags = KEYEVENTF_KEYUP if up else 0
        if name in EXTENDED:
            flags |= KEYEVENTF_EXTENDEDKEY
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0))

    def press(self, key: str, mods: tuple[str, ...] = ()) -> None:
        inputs = [self._vk_input(m, False) for m in mods]
        inputs.append(self._vk_input(key, False))
        inputs.append(self._vk_input(key, True))
        inputs += [self._vk_input(m, True) for m in reversed(mods)]
        self._send(inputs)

    def type_char(self, ch: str) -> None:
        data = ch.encode("utf-16-le")
        inputs: list[INPUT] = []
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i : i + 2], "little")
            for up in (False, True):
                flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
                inputs.append(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=unit, dwFlags=flags, time=0, dwExtraInfo=0)))
        self._send(inputs)

    def before_text(self, text: str) -> None:
        """Express เป็นโปรแกรมแบบ ANSI ต้องใช้แป้นพิมพ์ภาษาไทยอยู่ ตัวอักษรไทยจึงจะไม่กลายเป็น '?'"""
        if not _has_thai(text):
            return
        fg = user32.GetForegroundWindow()
        if not fg:
            return
        tid = user32.GetWindowThreadProcessId(fg, None)
        current = user32.GetKeyboardLayout(tid) or 0
        if (current & 0xFFFF) == LANG_THAI:
            return
        n = user32.GetKeyboardLayoutList(0, None)
        layouts = (wintypes.HKL * max(n, 1))()
        n = user32.GetKeyboardLayoutList(n, layouts)
        thai = next((h for h in layouts[:n] if h and (h & 0xFFFF) == LANG_THAI), None)
        if thai is None:
            if not self._thai_warned:
                self._thai_warned = True
                self.notify("เครื่องนี้ไม่มีแป้นพิมพ์ภาษาไทย ถ้าตัวอักษรไทยใน Express กลายเป็น '?' ให้ใช้โหมด 'วางผ่าน Clipboard'")
            return
        user32.PostMessageW(fg, WM_INPUTLANGCHANGEREQUEST, 0, thai)
        time.sleep(0.15)

    # ------------------------------------------------------------ Clipboard
    @staticmethod
    def _put_clipboard(fmt: int, data: bytes) -> None:
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            raise BackendError("จองหน่วยความจำสำหรับ Clipboard ไม่ได้")
        p = kernel32.GlobalLock(h)
        if not p:
            kernel32.GlobalFree(h)
            raise BackendError("เขียน Clipboard ไม่ได้")
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(fmt, h):
            kernel32.GlobalFree(h)
            raise BackendError("เขียน Clipboard ไม่ได้")

    def set_clipboard(self, text: str) -> None:
        for _ in range(20):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            raise BackendError("เปิด Clipboard ไม่ได้ เพราะมีโปรแกรมอื่นใช้อยู่")
        try:
            user32.EmptyClipboard()
            self._put_clipboard(CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
            # ใส่แบบ ANSI ภาษาไทย (cp874) ด้วย ให้โปรแกรมรุ่นเก่าอ่านภาษาไทยได้ถูกต้อง
            self._put_clipboard(CF_TEXT, text.encode("cp874", errors="replace") + b"\0")
            self._put_clipboard(CF_LOCALE, LCID_THAI.to_bytes(4, "little"))
        finally:
            user32.CloseClipboard()

    def paste_text(self, text: str) -> None:
        self.set_clipboard(text)
        self.press("V", ("CTRL",))
