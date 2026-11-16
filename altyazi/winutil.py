"""Windows pencere yardımcıları (ctypes, ek bağımlılık yok)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"


def set_dpi_aware() -> None:
    """Koordinatlar fiziksel piksel olsun (ekran ölçekleme %125/%150 olsa bile)."""
    if not IS_WIN:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa: BLE001
            pass


def list_windows() -> list[tuple[int, str]]:
    if not IS_WIN:
        return []
    user32 = ctypes.windll.user32
    out: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):  # noqa: ANN001
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                out.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return out


def find_window(part: str) -> tuple[int, str] | None:
    part = part.lower()
    matches = [(h, t) for h, t in list_windows() if part in t.lower() and "altyazi" not in t.lower()]
    # en kısa başlık genelde ana penceredir
    return min(matches, key=lambda m: len(m[1])) if matches else None


def frame_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """Pencerenin ekrandaki görünen sınırları (WGC'nin yakaladığı alanla aynı)."""
    if not IS_WIN:
        return None
    rect = wintypes.RECT()
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect))
    if res != 0:
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
    return rect.left, rect.top, rect.right, rect.bottom


def is_minimized(hwnd: int) -> bool:
    return bool(IS_WIN and ctypes.windll.user32.IsIconic(wintypes.HWND(hwnd)))


def add_cuda_dll_dirs() -> None:
    """pip ile kurulan nvidia-* paketlerinin DLL klasörlerini ekle (CUDA'yı ayrıca kurmaya gerek kalmaz)."""
    if not IS_WIN:
        return
    import os
    import site
    from pathlib import Path

    import sys as _sys
    dirs = []
    for sp in site.getsitepackages():
        dirs += list(Path(sp, "nvidia").glob("*/bin"))
    if getattr(_sys, "frozen", False):   # kurulu sürüm: DLL'ler paketin içinde
        base = Path(getattr(_sys, "_MEIPASS", Path(_sys.executable).parent))
        dirs += [base / "ctranslate2", base / "onnxruntime" / "capi"]
    for bin_dir in dirs:
        if bin_dir.is_dir():
            try:
                os.add_dll_directory(str(bin_dir))
            except OSError:
                pass
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    try:
        import onnxruntime as ort
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
    except Exception:  # noqa: BLE001
        pass


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "GTA6Altyazi"


def autostart_command() -> str:
    import sys
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --arka-plan'
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{exe}" -m altyazi --arka-plan'


def set_autostart(enabled: bool) -> bool:
    """Windows açılışında başlat (kullanıcı kayıt defteri, yönetici izni gerekmez)."""
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
