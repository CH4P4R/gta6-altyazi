"""macOS karşılıkları: pencere bulma, uyku engeli, açılışta başlatma, uygulama güvenlik duvarı.

winutil ile aynı adları sağlar; macOS'ta winutil bu fonksiyonları buradan alır. Pencere bilgileri Quartz'tan
(CGWindowListCopyWindowInfo) gelir; koordinatlar Qt gibi "nokta" (Retina'da piksel/2) cinsindendir.
Pencere adlarını okumak için macOS "Ekran Kaydı" izni ister; izin yokken de program adıyla (chiaki-ng) bulunur.
"""

from __future__ import annotations

import logging
import os
import plistlib
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

TITLE_BAR = 28            # macOS pencere başlık çubuğu (nokta)
_NOT_GAME = ("gta6 altyaz", "safari", "google chrome", "firefox", "finder", "github", "releases", "discord")


def _windows_info() -> list[dict]:
    import Quartz

    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    return list(Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or [])


def _all_windows_info() -> list[dict]:
    import Quartz

    return list(Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID) or [])


def _label(w: dict) -> str:
    owner = str(w.get("kCGWindowOwnerName") or "")
    title = str(w.get("kCGWindowName") or "")
    return f"{owner} - {title}" if title and title != owner else owner


def list_windows() -> list[tuple[int, str]]:
    """Görünen, normal katmandaki pencereler: [(pencere numarası, 'Program - Başlık')]."""
    out = []
    me = os.getpid()
    for w in _windows_info():
        if int(w.get("kCGWindowLayer", 0)) != 0 or int(w.get("kCGWindowOwnerPID", 0)) == me:
            continue
        b = w.get("kCGWindowBounds") or {}
        if float(b.get("Width", 0)) < 200 or float(b.get("Height", 0)) < 150:
            continue
        out.append((int(w["kCGWindowNumber"]), _label(w)))
    return out


def find_window(part: str) -> tuple[int, str] | None:
    """Program adında ya da başlığında 'part' geçen en büyük pencere (chiaki-ng'nin oyun penceresi)."""
    part = part.lower()
    best, best_area = None, 0.0
    me = os.getpid()
    for w in _windows_info():
        if int(w.get("kCGWindowLayer", 0)) != 0 or int(w.get("kCGWindowOwnerPID", 0)) == me:
            continue
        owner = str(w.get("kCGWindowOwnerName") or "").lower()
        label = _label(w)
        if part not in owner and part not in label.lower():
            continue
        if part not in owner and any(x in label.lower() for x in _NOT_GAME):
            continue                   # tarayıcıda açık "chiaki-ng" sayfası vb.
        b = w.get("kCGWindowBounds") or {}
        area = float(b.get("Width", 0)) * float(b.get("Height", 0))
        if area > best_area:
            best, best_area = (int(w["kCGWindowNumber"]), label), area
    return best


def _info(wid: int) -> dict | None:
    for w in _all_windows_info():
        if int(w.get("kCGWindowNumber", -1)) == wid:
            return w
    return None


def frame_bounds(wid: int) -> tuple[int, int, int, int] | None:
    w = _info(wid)
    if not w:
        return None
    b = w.get("kCGWindowBounds") or {}
    x, y = int(b.get("X", 0)), int(b.get("Y", 0))
    return x, y, x + int(b.get("Width", 0)), y + int(b.get("Height", 0))


def _screen_rects() -> list[tuple[int, int, int, int]]:
    import Quartz

    err, ids, n = Quartz.CGGetActiveDisplayList(16, None, None)
    out = []
    for d in (ids or [])[:n]:
        r = Quartz.CGDisplayBounds(d)
        out.append((int(r.origin.x), int(r.origin.y), int(r.origin.x + r.size.width), int(r.origin.y + r.size.height)))
    return out


def client_bounds(wid: int) -> tuple[int, int, int, int] | None:
    """İç alan: tam ekranda pencerenin tamamı, pencere modunda başlık çubuğu hariç."""
    fb = frame_bounds(wid)
    if not fb:
        return None
    try:
        fullscreen = any(fb == s for s in _screen_rects())
    except Exception:  # noqa: BLE001
        fullscreen = False
    if fullscreen:
        return fb
    x0, y0, x1, y1 = fb
    return x0, min(y1, y0 + TITLE_BAR), x1, y1


def is_minimized(wid: int) -> bool:
    w = _info(wid)
    return w is None or not w.get("kCGWindowIsOnscreen", False)


# ------------------------------------------------------------------------------------------- sistem
_caffeinate: subprocess.Popen | None = None


def keep_awake(on: bool) -> None:
    """Çeviri sürerken Mac uyumasın (caffeinate; program kapanınca kendiliğinden biter)."""
    global _caffeinate
    if on and _caffeinate is None:
        try:
            _caffeinate = subprocess.Popen(["caffeinate", "-dims", "-w", str(os.getpid())])
        except OSError as e:
            log.warning("Uyku engeli açılamadı: %s", e)
    elif not on and _caffeinate is not None:
        _caffeinate.terminate()
        _caffeinate = None


AGENT = Path.home() / "Library" / "LaunchAgents" / "com.gta6altyazi.app.plist"


def autostart_command() -> list[str]:
    return [sys.executable, "--arka-plan"] if getattr(sys, "frozen", False) else \
        [sys.executable, "-m", "altyazi.ui.run", "--arka-plan"]


def set_autostart(enabled: bool) -> bool:
    """Oturum açılınca simge durumunda başlat (LaunchAgent)."""
    try:
        if enabled:
            AGENT.parent.mkdir(parents=True, exist_ok=True)
            AGENT.write_bytes(plistlib.dumps({"Label": "com.gta6altyazi.app", "ProgramArguments": autostart_command(),
                                              "RunAtLoad": True, "ProcessType": "Interactive"}))
        else:
            AGENT.unlink(missing_ok=True)
        return True
    except OSError as e:
        log.warning("Açılışta başlatma ayarlanamadı: %s", e)
        return False


FW = "/usr/libexec/ApplicationFirewall/socketfilterfw"


def _app_path() -> str:
    """Güvenlik duvarına eklenecek program: .app paketinin içindeki çalıştırılabilir dosya."""
    return sys.executable


def firewall_ok() -> bool | None:
    """macOS uygulama güvenlik duvarı kapalıysa ya da bu program izinliyse True."""
    try:
        state = subprocess.run([FW, "--getglobalstate"], capture_output=True, text=True, timeout=10).stdout.lower()
        if "disabled" in state or "state = 0" in state:
            return True
        app = subprocess.run([FW, "--getappblocked", _app_path()], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    low = app.lower()
    if "permitted" in low or "izin" in low:
        return True
    if "blocked" in low:
        return False
    return None


def firewall_allow(make_private: bool = False) -> str:
    """Yönetici şifresiyle (macOS sorar) bu programın gelen bağlantılarına izin ver."""
    exe = _app_path().replace("\\", "\\\\").replace('"', '\\"')
    cmd = f'{FW} --add \\"{exe}\\" ; {FW} --unblockapp \\"{exe}\\"'
    script = f'do shell script "{cmd}" with administrator privileges'
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return "hata"
    if r.returncode != 0:
        return "iptal" if "-128" in (r.stderr or "") else "hata"
    return "tamam" if firewall_ok() is not False else "hata"


def network_is_public() -> bool | None:
    return None                      # macOS'ta Windows'taki gibi "Ortak ağ" ayrımı yok


def set_dpi_aware() -> None:
    pass


def add_cuda_dll_dirs() -> None:
    pass


# ------------------------------------------------------------------------------------------- izinler
def screen_capture_allowed() -> bool | None:
    """'Ekran Kaydı' izni verilmiş mi (macOS 10.15+)."""
    try:
        import Quartz
        return bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:  # noqa: BLE001
        return None


def request_screen_capture() -> None:
    """İzin penceresini aç (bir kez sorar; reddedilirse Sistem Ayarları'ndan verilir)."""
    try:
        import Quartz
        Quartz.CGRequestScreenCaptureAccess()
    except Exception:  # noqa: BLE001
        pass


def open_privacy_settings(pane: str = "ScreenCapture") -> None:
    """Sistem Ayarları › Gizlilik ve Güvenlik'in ilgili bölümünü aç (ScreenCapture, Accessibility, LocalNetwork)."""
    subprocess.Popen(["open", f"x-apple.systempreferences:com.apple.preference.security?Privacy_{pane}"])


def accessibility_allowed(prompt: bool = False) -> bool | None:
    """Genel kısayol tuşları için 'Erişilebilirlik' izni."""
    try:
        import ApplicationServices as AS
        if prompt:
            return bool(AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: True}))
        return bool(AS.AXIsProcessTrusted())
    except Exception:  # noqa: BLE001
        return None


def raise_overlay(widget) -> None:  # noqa: ANN001
    """Qt penceresini tam ekran uygulamaların (chiaki-ng) da üstünde, bütün masaüstlerinde göster; tıklamayı geçir."""
    try:
        import AppKit
        import objc

        view = objc.objc_object(c_void_p=int(widget.winId()))
        win = view.window()
        if win is None:
            return
        win.setLevel_(AppKit.NSScreenSaverWindowLevel)
        win.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                   | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
                                   | AppKit.NSWindowCollectionBehaviorStationary
                                   | AppKit.NSWindowCollectionBehaviorIgnoresCycle)
        win.setIgnoresMouseEvents_(True)
        win.setHasShadow_(False)
        if hasattr(win, "setHidesOnDeactivate_"):
            win.setHidesOnDeactivate_(False)
    except Exception as e:  # noqa: BLE001
        log.warning("Katman penceresi ayarlanamadı: %s", e)
