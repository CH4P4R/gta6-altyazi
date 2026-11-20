"""Windows pencere yardımcıları (ctypes, ek bağımlılık yok)."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"


log = logging.getLogger(__name__)

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


_NOT_GAME = ("altyazi", "altyazı", "google chrome", "firefox", "microsoft edge", "opera", "brave", "github",
             "dosya gezgini", "file explorer", "releases", "notepad", "not defteri", "discord")


def _exe_name(hwnd: int) -> str:
    """Pencerenin programının dosya adı (ör. chiaki.exe); okunamazsa boş."""
    if not IS_WIN:
        return ""
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(520)
            size = wintypes.DWORD(520)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:  # noqa: BLE001
        pass
    return ""


def find_window(part: str) -> tuple[int, str] | None:
    """Başlığında 'part' geçen oyun penceresi. Önce programı gerçekten chiaki olanlar; tarayıcıda açık 'chiaki-ng
    releases' sayfası, aynı adlı klasör ya da bizim pencerelerimiz yakalanmaz."""
    part = part.lower()
    matches = [(h, t) for h, t in list_windows() if part in t.lower()]
    by_exe = [(h, t) for h, t in matches if part in _exe_name(h)]
    pool = by_exe or [(h, t) for h, t in matches if not any(x in t.lower() for x in _NOT_GAME)]
    # en kısa başlık genelde ana penceredir
    return min(pool, key=lambda m: len(m[1])) if pool else None


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


def client_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """Pencerenin iç alanı (başlık çubuğu ve kenarlıklar hariç), ekran koordinatlarında."""
    if not IS_WIN:
        return None
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return None
    pt = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(pt))
    return pt.x, pt.y, pt.x + rect.right, pt.y + rect.bottom


def fit_aspect(box: tuple[int, int, int, int], aspect: float = 16 / 9) -> tuple[int, int, int, int]:
    """Kutunun ortasına sığan en büyük 16:9 alan (chiaki görüntüyü pencereye oranı bozmadan, siyah bantla sığdırır)."""
    l, t, r, b = box
    w, h = r - l, b - t
    if w <= 0 or h <= 0:
        return box
    if w / h > aspect:                      # pencere daha geniş: sağda solda bant
        vw = round(h * aspect)
        x = l + (w - vw) // 2
        return x, t, x + vw, b
    vh = round(w / aspect)                  # pencere daha uzun: üstte altta bant
    y = t + (h - vh) // 2
    return l, y, r, y + vh


def video_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """chiaki penceresinde oyun görüntüsünün ekrandaki yeri (başlık çubuğu ve siyah bantlar hariç)."""
    c = client_bounds(hwnd)
    return fit_aspect(c) if c and c[2] > c[0] and c[3] > c[1] else frame_bounds(hwnd)


def crop_in_frame(frame_w: int, frame_h: int, captured: tuple[int, int, int, int],
                  inner: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    """Yakalanan karede (ekranda 'captured' alanını kaplar) 'inner' alanının piksel kutusu. Kırpmaya gerek yoksa None."""
    cl, ct, cr, cb = captured
    if cr <= cl or cb <= ct:
        return None
    sx, sy = frame_w / (cr - cl), frame_h / (cb - ct)
    x0 = max(0, round((inner[0] - cl) * sx))
    y0 = max(0, round((inner[1] - ct) * sy))
    x1 = min(frame_w, round((inner[2] - cl) * sx))
    y1 = min(frame_h, round((inner[3] - ct) * sy))
    if x1 - x0 < frame_w * 0.3 or y1 - y0 < frame_h * 0.3:
        return None                          # anlamsız sonuç: kırpma
    if x0 <= 1 and y0 <= 1 and x1 >= frame_w - 1 and y1 >= frame_h - 1:
        return None
    return x0, y0, x1, y1


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
def keep_awake(on: bool) -> None:
    """Çeviri sürerken bilgisayar uykuya geçmesin (oyun kumandayla oynanır, fare/klavye boşta kalır)."""
    if sys.platform != "win32":
        return
    flags = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if on else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


FIREWALL_RULE = "GTA6 Altyazı (yerel ağ)"          # eski sürümlerin kural adı (kaldırılır)
FIREWALL_GROUP = "GTA6Altyazi.LocalNetwork"        # yeni kurallar bu grupta (ASCII: kod sayfası derdi yok)


def _program() -> str:
    return sys.executable


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _powershell(script: str, timeout: float = 30) -> int | None:
    """PowerShell betiğini (çıktısını okumadan) çalıştır, çıkış kodunu döndür. Betik base64 gider: tırnak/Türkçe
    karakter sorunu olmaz."""
    import base64
    import subprocess

    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                           capture_output=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.returncode


def firewall_ok() -> bool | None:
    """Bu program için Özel ağda yerel cihazlardan gelen bağlantı izni var mı? (Windows dışında None)

    CouchSubs'taki gibi: Özel profilde 'gelen bütün bağlantıları engelle' açıksa ya da bu programa engel kuralı varsa
    izin yok sayılır.
    """
    if sys.platform != "win32":
        return None
    exe = _ps_quote(_program())
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$p = {exe}
$prof = Get-NetFirewallProfile -Name Private
if ($prof.Enabled -eq 'True' -and $prof.AllowInboundRules -eq 'False') {{ exit 4 }}
$mine = Get-NetFirewallApplicationFilter -Program $p | Get-NetFirewallRule | Where-Object {{ $_.Direction -eq 'Inbound' -and $_.Enabled -eq 'True' }}
if ($mine | Where-Object {{ $_.Action -eq 'Block' }}) {{ exit 3 }}
$allow = $mine | Where-Object {{ $_.Action -eq 'Allow' -and ($_.Profile -match 'Private|Any') }}
if ($allow) {{ exit 0 }} else {{ exit 3 }}
"""
    rc = _powershell(script)
    if rc == 0:
        return True
    return False if rc in (3, 4) else None


def _shell_execute_wait(file: str, params: str, timeout_ms: int = 120000) -> int | None:
    """Yönetici olarak çalıştır (UAC sorusu), bitmesini bekle, çıkış kodunu döndür. İptal edilirse None."""
    from ctypes import wintypes as wt

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wt.HWND), ("lpVerb", wt.LPCWSTR),
                    ("lpFile", wt.LPCWSTR), ("lpParameters", wt.LPCWSTR), ("lpDirectory", wt.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wt.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wt.LPCWSTR), ("hkeyClass", wt.HKEY), ("dwHotKey", wt.DWORD),
                    ("hIconOrMonitor", wt.HANDLE), ("hProcess", wt.HANDLE)]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040 | 0x00000400          # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
    info.lpVerb = "runas"
    info.lpFile = file
    info.lpParameters = params
    info.nShow = 0
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        return None
    try:
        ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, timeout_ms)
        code = wt.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return int(code.value)
    finally:
        ctypes.windll.kernel32.CloseHandle(info.hProcess)


def firewall_script(exe: str, make_private: bool) -> str:
    """Yönetici olarak çalışan betik: (istenirse Ortak ev ağını Özel yap), bu programın engel kurallarını kaldır,
    Özel ağda yalnız yerel alt ağdan TCP/UDP izni ekle ve doğrula (CouchSubs LocalFirewallPolicy gibi)."""
    p = _ps_quote(exe)
    g = _ps_quote(FIREWALL_GROUP)
    private = ("Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' -and "
               "$_.IPv4Connectivity -ne 'Disconnected' } | Set-NetConnectionProfile -NetworkCategory Private\n"
               if make_private else "")
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
$p = {p}
{private}Get-NetFirewallApplicationFilter -Program $p | Get-NetFirewallRule | Where-Object {{ $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' }} | Remove-NetFirewallRule
Get-NetFirewallRule -Group {g} | Remove-NetFirewallRule
Get-NetFirewallRule -DisplayName 'GTA6 Altyaz* (yerel a*)' | Remove-NetFirewallRule
$ErrorActionPreference = 'Stop'
try {{
  New-NetFirewallRule -DisplayName 'GTA6 Altyazi - yerel TCP' -Group {g} -Direction Inbound -Action Allow -Program $p -Profile Private -RemoteAddress LocalSubnet -Protocol TCP | Out-Null
  New-NetFirewallRule -DisplayName 'GTA6 Altyazi - yerel UDP' -Group {g} -Direction Inbound -Action Allow -Program $p -Profile Private -RemoteAddress LocalSubnet -Protocol UDP | Out-Null
}} catch {{ exit 5 }}
if ((Get-NetFirewallRule -Group {g} | Measure-Object).Count -lt 2) {{ exit 6 }}
exit 0
"""


def firewall_allow(make_private: bool = False) -> str:
    """Yönetici izniyle (UAC) TV ve telefonun bu programa bağlanmasına izin ver ve sonucu doğrula.

    Döner: 'tamam' | 'iptal' (UAC'ye Hayır denildi) | 'hata' (kural yazılamadı) | 'desteklenmiyor'
    """
    if sys.platform != "win32":
        return "desteklenmiyor"
    import base64

    enc = base64.b64encode(firewall_script(_program(), make_private).encode("utf-16-le")).decode()
    rc = _shell_execute_wait("powershell.exe", f"-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {enc}")
    if rc is None:
        return "iptal"
    if rc != 0:
        log.warning("Güvenlik duvarı kuralı yazılamadı (çıkış kodu %s)", rc)
        return "hata"
    return "tamam" if firewall_ok() is not False else "hata"


def network_is_public() -> bool | None:
    """Etkin ağ 'Ortak' profilde mi? (Öyleyse TV/telefon bağlanamaz; Özel yapılmalı.)"""
    if sys.platform != "win32":
        return None
    import subprocess

    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-NetConnectionProfile | Where-Object {$_.IPv4Connectivity -ne 'Disconnected'}).NetworkCategory"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    cats = (out or "").split()
    return bool(cats) and all(c == "Public" for c in cats)
