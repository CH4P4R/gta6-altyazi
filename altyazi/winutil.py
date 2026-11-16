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


# ---------------------------------------------------------------- uyku engeli ve güvenlik duvarı
# (fikirler CouchSubs'tan: SleepGuard ve yerel ağ güvenlik duvarı kuralı; https://github.com/yorulmazsinan/couchsubs)
_ES_CONTINUOUS, _ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
FIREWALL_RULE = "GTA6 Altyazı (yerel ağ)"


def keep_awake(on: bool) -> None:
    """Çeviri sürerken bilgisayar uykuya geçmesin (oyun kumandayla oynanır, fare/klavye boşta kalır)."""
    if sys.platform != "win32":
        return
    flags = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if on else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


def _program() -> str:
    return sys.executable


def firewall_ok() -> bool | None:
    """Bu program için izin kuralı var mı? (Windows dışında None)"""
    if sys.platform != "win32":
        return None
    import subprocess

    try:
        out = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return FIREWALL_RULE in out


def firewall_allow() -> bool:
    """Yönetici izniyle (UAC sorusu) TV ve telefonun bu programa bağlanmasına izin ver.

    Kural yalnız Özel ağ profilinde ve yalnız yerel alt ağdan gelen bağlantılar içindir. Windows'un ilk açılıştaki
    soruya "İptal" denince bu program için kendiliğinden koyduğu engelleme kuralları da kaldırılır.
    """
    if sys.platform != "win32":
        return False
    exe = _program().replace("'", "''")
    ps = (f"$p='{exe}';"
          "Get-NetFirewallApplicationFilter -Program $p -ErrorAction SilentlyContinue | Get-NetFirewallRule | "
          "Where-Object {$_.Action -eq 'Block'} | Remove-NetFirewallRule;"
          f"Remove-NetFirewallRule -DisplayName '{FIREWALL_RULE}' -ErrorAction SilentlyContinue;"
          f"New-NetFirewallRule -DisplayName '{FIREWALL_RULE}' -Direction Inbound -Action Allow -Program $p "
          "-Profile Private -RemoteAddress LocalSubnet -Protocol TCP | Out-Null;"
          f"New-NetFirewallRule -DisplayName '{FIREWALL_RULE}' -Direction Inbound -Action Allow -Program $p "
          "-Profile Private -RemoteAddress LocalSubnet -Protocol UDP | Out-Null")
    args = f'-NoProfile -WindowStyle Hidden -Command "{ps}"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 0)
    return rc > 32


def network_is_public() -> bool | None:
    """Etkin ağ 'Ortak' profilde mi? (Öyleyse TV/telefon bağlanamaz; Özel yapılmalı.)"""
    if sys.platform != "win32":
        return None
    import subprocess

    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-NetConnectionProfile | Where-Object {$_.IPv4Connectivity -ne 'Disconnected'}).NetworkCategory"],
                             capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    cats = out.split()
    return bool(cats) and all(c == "Public" for c in cats)
