"""ทดสอบส่วนที่ใช้ Win32 API (รันเฉพาะบน Windows เช่นใน GitHub Actions)"""

import ctypes
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="ต้องรันบน Windows")


def test_input_struct_size():
    from exautokey import winbackend as wb

    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(wb.INPUT) == expected


def test_enum_windows_and_prepare_errors():
    from exautokey.backends import BackendError
    from exautokey.winbackend import WindowsBackend, enum_windows

    assert isinstance(enum_windows(), list)
    be = WindowsBackend()
    assert isinstance(be.list_windows(), list)
    with pytest.raises(BackendError):
        be.prepare("ไม่มีหน้าต่างชื่อนี้แน่นอน-9f3c")
    assert be.abort_requested() in (True, False)


def test_clipboard_roundtrip():
    from exautokey.winbackend import WindowsBackend, kernel32, user32

    be = WindowsBackend()
    try:
        be.set_clipboard("ทดสอบ 123")
    except Exception as exc:  # runner บางเครื่องไม่มี clipboard
        pytest.skip(f"clipboard ไม่พร้อม: {exc}")
    user32.GetClipboardData.argtypes = (ctypes.c_uint,)
    user32.GetClipboardData.restype = ctypes.c_void_p
    assert user32.OpenClipboard(None)
    try:
        h = user32.GetClipboardData(13)
        p = kernel32.GlobalLock(h)
        text = ctypes.wstring_at(p)
        kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()
    assert text == "ทดสอบ 123"
