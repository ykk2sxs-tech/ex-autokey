"""ตำแหน่งโฟลเดอร์ของโปรแกรม (ใช้ได้ทั้งตอนรันจากซอร์สและจากไฟล์ .exe)"""

from __future__ import annotations

import os
import shutil
import sys

from . import APP_NAME


def bundled_dir() -> str:
    """โฟลเดอร์ที่เก็บไฟล์ที่มากับโปรแกรม (templates, samples)"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(folder: str) -> bool:
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".write-test")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def app_dir() -> str:
    """โฟลเดอร์สำหรับเก็บเทมเพลตและ log ของผู้ใช้"""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else bundled_dir()
    if _writable(base):
        return base
    alt = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    os.makedirs(alt, exist_ok=True)
    return alt


def templates_dir() -> str:
    folder = os.path.join(app_dir(), "templates")
    if not os.path.isdir(folder):
        src = os.path.join(bundled_dir(), "templates")
        if os.path.isdir(src) and os.path.abspath(src) != os.path.abspath(folder):
            shutil.copytree(src, folder)
        else:
            os.makedirs(folder, exist_ok=True)
    return folder


def samples_dir() -> str:
    folder = os.path.join(app_dir(), "samples")
    if not os.path.isdir(folder):
        src = os.path.join(bundled_dir(), "samples")
        if os.path.isdir(src) and os.path.abspath(src) != os.path.abspath(folder):
            shutil.copytree(src, folder)
    return folder


def logs_dir() -> str:
    folder = os.path.join(app_dir(), "logs")
    os.makedirs(folder, exist_ok=True)
    return folder
