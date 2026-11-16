"""Genel kısayol tuşları (Windows). Oyun ya da başka bir pencere öndeyken de çalışır."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from ctypes import wintypes
from typing import Callable

log = logging.getLogger(__name__)

MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
NAMED = {f"f{i}": 0x6F + i for i in range(1, 13)} | {f"num{i}": 0x60 + i for i in range(10)} | {
    "space": 0x20, "pause": 0x13, "home": 0x24, "end": 0x23, "insert": 0x2D}


def parse(combo: str) -> tuple[int, int]:
    """'ctrl+shift+9' -> (modifier bayrakları, sanal tuş kodu)."""
    mods, vk = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in MODS:
            mods |= MODS[part]
        elif part in NAMED:
            vk = NAMED[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        else:
            raise ValueError(f"Tanınmayan tuş: {part!r} ({combo})")
    if vk is None:
        raise ValueError(f"Kısayolda tuş yok: {combo}")
    return mods, vk


class Hotkeys:
    def __init__(self, bindings: dict[str, Callable[[], None]]):
        self.bindings = bindings
        self._thread: threading.Thread | None = None
        self._tid = 0

    def start(self) -> None:
        if sys.platform != "win32" or not self.bindings:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="kisayol")
        self._thread.start()

    def stop(self) -> None:
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, 0x0012, 0, 0)  # WM_QUIT

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        actions = {}
        for i, (combo, fn) in enumerate(self.bindings.items(), start=1):
            try:
                mods, vk = parse(combo)
            except ValueError as e:
                log.warning("%s", e)
                continue
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                actions[i] = fn
                log.info("Kısayol: %s", combo)
            else:
                log.warning("Kısayol kaydedilemedi (başka program kullanıyor olabilir): %s", combo)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in actions:
                try:
                    actions[msg.wParam]()
                except Exception:  # noqa: BLE001
                    log.exception("Kısayol işlenirken hata")
        for i in actions:
            user32.UnregisterHotKey(None, i)
