"""Genel kısayol tuşları (Windows ve macOS). Oyun ya da başka bir pencere öndeyken de çalışır.

macOS'ta NSEvent genel izleyicisi kullanılır; macOS "Erişilebilirlik" izni ister (Sistem Ayarları › Gizlilik ve
Güvenlik › Erişilebilirlik). Kısayoldaki "ctrl" Control, "alt" Option, "win"/"cmd" Command tuşudur."""

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
        if sys.platform == "darwin" and self.bindings:
            self._start_mac()
            return
        if sys.platform != "win32" or not self.bindings:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="kisayol")
        self._thread.start()

    # ------------------------------------------------------------------ macOS
    _MAC_KEYS = {**{str(d): c for d, c in zip("0123456789", (0x1D, 0x12, 0x13, 0x14, 0x15, 0x17, 0x16, 0x1A, 0x1C, 0x19))},
                 **dict(zip("asdfhgzxcvbqweryt", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11))),
                 "o": 0x1F, "u": 0x20, "i": 0x22, "p": 0x23, "l": 0x25, "j": 0x26, "k": 0x28, "n": 0x2D, "m": 0x2E,
                 "space": 0x31, "home": 0x73, "end": 0x77,
                 **dict(zip((f"f{i}" for i in range(1, 13)),
                            (0x7A, 0x78, 0x63, 0x76, 0x60, 0x61, 0x62, 0x64, 0x65, 0x6D, 0x67, 0x6F))),
                 # sayı tuş takımı (kVK_ANSI_Keypad0-9)
                 **dict(zip((f"num{i}" for i in range(10)),
                            (0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5B, 0x5C)))}
    _MAC_MODS = {"shift": 1 << 17, "ctrl": 1 << 18, "alt": 1 << 19, "win": 1 << 20, "cmd": 1 << 20}

    @classmethod
    def parse_mac(cls, combo: str) -> tuple[int, int]:
        mods, key = 0, None
        for part in combo.lower().replace(" ", "").split("+"):
            if part in cls._MAC_MODS:
                mods |= cls._MAC_MODS[part]
            elif part in cls._MAC_KEYS:
                key = cls._MAC_KEYS[part]
            else:
                raise ValueError(f"Tanınmayan tuş: {part!r} ({combo})")
        if key is None:
            raise ValueError(f"Kısayolda tuş yok: {combo}")
        return mods, key

    def _start_mac(self) -> None:
        try:
            import AppKit
        except ImportError:
            log.warning("macOS kısayolları için pyobjc gerekli")
            return
        from . import macutil
        if macutil.accessibility_allowed() is False:
            macutil.accessibility_allowed(prompt=True)
            log.warning("Kısayol tuşları için macOS 'Erişilebilirlik' izni gerekiyor")
        table = {}
        for combo, fn in self.bindings.items():
            try:
                table[self.parse_mac(combo)] = fn
                log.info("Kısayol: %s", combo)
            except ValueError as e:
                log.warning("%s", e)
        mask_mods = (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20)

        def handle(event) -> None:  # noqa: ANN001
            fn = table.get((int(event.modifierFlags()) & mask_mods, int(event.keyCode())))
            if fn:
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    log.exception("Kısayol işlenirken hata")

        def local(event):  # noqa: ANN001, ANN202
            handle(event)
            return event

        mask = AppKit.NSEventMaskKeyDown
        self._mac_monitors = [AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handle),
                              AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(mask, local)]

    def stop(self) -> None:
        for m in getattr(self, "_mac_monitors", []) or []:
            try:
                import AppKit
                AppKit.NSEvent.removeMonitor_(m)
            except Exception:  # noqa: BLE001
                pass
        self._mac_monitors = []
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
