# -*- coding: utf-8 -*-
"""Защита от второго экземпляра: named mutex (Windows) + фокусирование окна.

Повторный запуск не создаёт второй процесс, а разворачивает и активирует
уже открытое окно работающего экземпляра (п.4 ТЗ)."""

import ctypes
import sys
from ctypes import wintypes

_MUTEX_NAME = "TimeTracker::single-instance::1f0a7c3e"
_WINDOW_PREFIX = "TimeTracker"
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9


class SingleInstance:
    """acquire() -> True, если мы первый экземпляр; иначе False."""

    def __init__(self):
        self._handle = None

    def acquire(self) -> bool:
        if sys.platform != "win32":
            # Целевая ОС — Windows; на других платформах (разработка) не блокируем.
            self._handle = object()
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            # Не удалось создать мьютекс — не блокируем приложение.
            return True
        if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self):
        if sys.platform == "win32" and self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def focus_existing_window() -> bool:
    """Найти видимое окно с заголовком «TimeTracker…» и вывести его на передний план."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    found: list[wintypes.HWND] = []

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def on_window(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.startswith(_WINDOW_PREFIX):
                    found.append(hwnd)
                    return False
        return True

    user32.EnumWindows(enum_proc(on_window), 0)
    if not found:
        return False
    hwnd = found[0]
    user32.ShowWindow(hwnd, _SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True
