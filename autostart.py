# -*- coding: utf-8 -*-
"""윈도우 시작 시 자동 실행. 사용자 레지스트리 Run 키라 관리자 권한이 필요 없다."""
import os
import sys

try:
    import winreg
except ImportError:
    winreg = None

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "DontMissClass"


def _command():
    if getattr(sys, "frozen", False):
        return '"%s" --background' % sys.executable
    py = sys.executable.replace("python.exe", "pythonw.exe")
    return '"%s" "%s" --background' % (py, os.path.abspath(sys.argv[0]))


def set_enabled(on):
    """켜거나 끈다. 실패하면 False(보안 프로그램이 막는 경우 등)."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def is_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, NAME)
        return True
    except OSError:
        return False
