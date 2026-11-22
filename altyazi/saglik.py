# SPDX-License-Identifier: AGPL-3.0-only
"""Sistem sağlığı (Nino'nun "Sistem sağlığı" sayfası): ağ, PS5 bağlantısı ve görüntüsü, çeviri hızı, TV.

Her denetim {anahtar, ikon, başlık, alt yazı, durum, öneri} döndürür; durum: ok (İyi) | warn (İyileştirilebilir) |
bad (Sorun) | off (bilinmiyor / kullanılmıyor). Cihaz bilgileri sorun bildirirken eklenir; ad, seri numarası ya da
adres içermez.
"""

from __future__ import annotations

import platform
import re
import subprocess
import sys
import time
from pathlib import Path

STATE_TEXT = {"ok": "İyi", "warn": "İyileştirilebilir", "bad": "Sorun", "off": "—"}
ISSUES_URL = "https://github.com/CH4P4R/gta6-altyazi/issues/new"


def _run(cmd: list[str], timeout: float = 4.0) -> str:
    try:
        kw = {"creationflags": 0x08000000} if sys.platform == "win32" else {}      # CREATE_NO_WINDOW
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw).stdout
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------- ağ türü
def mac_default_iface(route_out: str) -> str | None:
    m = re.search(r"interface:\s*(\S+)", route_out)
    return m.group(1) if m else None


def mac_port_of(iface: str, ports_out: str) -> str | None:
    """`networksetup -listallhardwareports` çıktısında aygıtın adı (Wi-Fi, Ethernet, USB 10/100/1000 LAN...)."""
    for block in re.split(r"\n\s*\n", ports_out):
        port = re.search(r"Hardware Port:\s*(.+)", block)
        dev = re.search(r"Device:\s*(\S+)", block)
        if port and dev and dev.group(1) == iface:
            return port.group(1).strip()
    return None


def kind_of(name: str | None) -> str:
    """Arayüz ya da bağlantı adından tür: wifi | kablo | bilinmiyor."""
    if not name:
        return "bilinmiyor"
    n = name.lower()
    if any(k in n for k in ("wi-fi", "wifi", "wireless", "wlan", "airport", "802.11", "kablosuz")):
        return "wifi"
    if any(k in n for k in ("ethernet", "lan", "thunderbolt", "usb", "eth", "kablolu")):
        return "kablo"
    return "bilinmiyor"


def network_kind() -> str:
    try:
        if sys.platform == "darwin":
            iface = mac_default_iface(_run(["route", "-n", "get", "default"]))
            if not iface:
                return "bilinmiyor"
            port = mac_port_of(iface, _run(["networksetup", "-listallhardwareports"]))
            return kind_of(port) if port else "bilinmiyor"
        if sys.platform == "win32":
            alias = _run(["powershell", "-NoProfile", "-Command",
                          "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | "
                          "Select-Object -First 1).InterfaceAlias"]).strip()
            return kind_of(alias) if alias else "bilinmiyor"
        out = _run(["ip", "route", "show", "default"])
        m = re.search(r"dev\s+(\S+)", out)
        if m:
            return "wifi" if Path(f"/sys/class/net/{m.group(1)}/wireless").exists() else "kablo"
    except Exception:  # noqa: BLE001
        pass
    return "bilinmiyor"


# --------------------------------------------------------------------------- denetimler
def check_network(kind: str, stream: dict | None) -> dict:
    title = {"wifi": "Wi-Fi", "kablo": "Kablo (Ethernet)"}.get(kind, "Bilinmiyor")
    bad_stream = bool(stream and (stream.get("donma_dk", 0) > 1 or stream.get("kopma_10dk", 0) > 0))
    if kind == "wifi" and bad_stream:
        return _row("ag", "Bu bilgisayarın ağı", title, "warn",
                    "PS5 görüntüsü veri kaybediyor. Bilgisayarı modeme kabloyla bağla (USB-C Ethernet adaptörü olur). "
                    "Olmuyorsa modeme yaklaş ve 5 GHz Wi-Fi kullan.")
    if kind == "wifi":
        return _row("ag", "Bu bilgisayarın ağı", title, "ok",
                    "Sorun yok. Görüntü takılırsa en iyisi bilgisayarı ve PS5'i modeme kabloyla bağlamak.")
    return _row("ag", "Bu bilgisayarın ağı", title, "ok" if kind == "kablo" else "off", "")


def check_ps5(paired: bool, state: str, stream: dict | None) -> dict:
    if not paired:
        return _row("ps5", "PS5 bağlantısı", "Eşli değil", "off", "Bağlantı sayfasından bir kez bağla.")
    drops = (stream or {}).get("kopma_10dk", 0)
    if state == "bagli":
        return _row("ps5", "PS5 bağlantısı", "Bağlı, kopma yok" if not drops else f"Bağlı, son 10 dk {drops} kopma",
                    "ok" if not drops else "warn",
                    "" if not drops else "PS5'i modeme kabloyla bağla; Wi-Fi'de akış kopabiliyor.")
    if state == "kopuk":
        return _row("ps5", "PS5 bağlantısı", "Koptu, yeniden bağlanıyor", "bad",
                    "PS5 açık ve aynı ağda mı? Dinlenme modundaysa uyandırılır.")
    if state == "baglaniyor":
        return _row("ps5", "PS5 bağlantısı", "Bağlanıyor", "warn", "")
    return _row("ps5", "PS5 bağlantısı", "Eşleşti (çeviri kapalı)", "ok", "")


def check_picture(stream: dict | None) -> dict:
    if not stream or not stream.get("fps"):
        return _row("goruntu", "PS5 görüntüsü", "Çeviri açıkken ölçülür", "off", "")
    fz, fps = stream.get("donma_dk", 0), stream.get("fps", 0)
    sub = f"Saniyede {fps:g} kare, dakikada {fz:g} donma"
    if fz > 1 or fps < 15:
        return _row("goruntu", "PS5 görüntüsü", sub, "warn",
                    "Görüntü donunca altyazı okunamaz. PS5'i ve bu bilgisayarı modeme kabloyla bağla.")
    return _row("goruntu", "PS5 görüntüsü", sub, "ok", "")


def check_speed(avg_ms: float | None, count: int) -> dict:
    if avg_ms is None:
        return _row("hiz", "Çeviri hızı", "Çeviri açıkken ölçülür", "off", "")
    sub = f"Satır başına {avg_ms / 1000:.1f} sn ({count} satır)".replace(".", ",")
    if avg_ms <= 900:
        return _row("hiz", "Çeviri hızı", sub, "ok", "")
    if avg_ms <= 2000:
        return _row("hiz", "Çeviri hızı", sub, "warn", "Hazır paket ve yerel model en hızlısı; yapay zekâ biraz bekletir.")
    return _row("hiz", "Çeviri hızı", sub, "bad", "Çeviri motoru yavaş: Çeviri sayfasından Ücretsiz ya da Gemini'yi dene.")


def check_tv(state: str, brand: str, ip: str) -> dict:
    name = {"android": "Android TV", "lg": "LG webOS", "samsung": "Samsung Tizen"}.get(brand, "TV")
    if state == "bagli":
        return _row("tv", "TV", f"{name} · bağlı", "ok", "")
    if state == "hata":
        return _row("tv", "TV", f"{name} · bağlanamadı", "bad",
                    "TV açık ve aynı ağda mı? Bağlantı sayfasında güvenlik duvarı iznini kontrol et.")
    if not ip:
        return _row("tv", "TV", "Kurulmadı", "off", "Bağlantı sayfasından TV'yi bağla.")
    return _row("tv", "TV", f"{name} · çeviri başlayınca bağlanır", "ok", "")


def _ver(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


def check_tv_app(reported: str | None, expected: str, connected: bool) -> dict:
    if not reported:
        return _row("tvapp", "TV uygulaması", "TV bağlanınca sürümü görünür" if not connected else
                    "Sürüm bilgisi gelmedi (eski TV uygulaması)", "off" if not connected else "warn",
                    "" if not connected else "Bağlantı › TV › Bağlan, kur ve başlat ile TV uygulamasını güncelle.")
    if _ver(reported) and _ver(expected) and _ver(reported) < _ver(expected):
        return _row("tvapp", "TV uygulaması", f"Kurulu sürüm {reported} · yenisi {expected}", "warn",
                    "Bağlantı › TV › Bağlan, kur ve başlat ile güncelle (yeni renkler ve yazı tipi için gerekir).")
    return _row("tvapp", "TV uygulaması", f"Kurulu (sürüm {reported})", "ok", "")


def _row(key: str, title: str, sub: str, state: str, advice: str) -> dict:
    icons = {"ag": "swap", "ps5": "ps", "goruntu": "play", "hiz": "bolt", "tv": "tv", "tvapp": "copy"}
    return {"key": key, "icon": icons.get(key, "check"), "title": title, "sub": sub, "state": state,
            "advice": advice}


def stream_stats(ctl) -> dict | None:  # noqa: ANN001
    try:
        session = ctl.pipe.source.session
        return session.stats.summary(time.monotonic())
    except Exception:  # noqa: BLE001
        return None


def checks(ctl, kind: str | None = None) -> list[dict]:  # noqa: ANN001
    stream = stream_stats(ctl)
    kind = kind or network_kind()
    rows = [check_network(kind, stream)]
    if ctl.cfg.kaynak.tur == "remoteplay" or ctl.cfg.ps5.anahtar:
        rows.append(check_ps5(bool(ctl.cfg.ps5.anahtar), ctl.rp_state[0], stream))
        rows.append(check_picture(stream))
    rows.append(check_speed(ctl.avg_latency(), len(getattr(ctl, "latencies", []) or [])))
    rows.append(check_tv(ctl.tv_state[0], ctl.cfg.tv.marka, ctl.cfg.tv.ip))
    from .tv import TV_APP_VERSION
    version = ctl.tv_app_version() if hasattr(ctl, "tv_app_version") else None
    rows.append(check_tv_app(version, TV_APP_VERSION, ctl.tv_state[0] == "bagli"))
    return rows


# --------------------------------------------------------------------------- cihaz bilgileri
def device_model() -> str:
    if sys.platform == "darwin":
        return _run(["sysctl", "-n", "hw.model"]).strip() or platform.machine()
    return platform.machine()


def os_name() -> str:
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0]}"
    if sys.platform == "win32":
        return f"Windows {platform.release()} ({platform.version()})"
    return platform.platform()


def device_info(ctl) -> list[tuple[str, str]]:  # noqa: ANN001
    from . import __version__
    info = ctl.engine_info or {}
    brand = {"android": "Android TV", "lg": "LG webOS", "samsung": "Samsung Tizen"}.get(ctl.cfg.tv.marka, "TV")
    tv = {"bagli": "bağlı", "baglaniyor": "bağlanıyor", "hata": "hata", "onay": "onay bekliyor"}.get(ctl.tv_state[0],
                                                                                                    "bağlı değil")
    src = {"remoteplay": "PS5 · arka planda (ikinci hesap)", "pencere": "Pencere (chiaki-ng / Remote Play)",
           "capture": "Yakalama kartı", "video": "Video dosyası"}.get(ctl.cfg.kaynak.tur, ctl.cfg.kaynak.tur)
    state = {"calisiyor": "çeviri açık", "hazir": "hazır", "hazirlaniyor": "hazırlanıyor", "hata": "hata"}.get(
        ctl.state, ctl.state)
    rp = ctl.rp_state[0]
    if ctl.cfg.kaynak.tur == "remoteplay" and rp:
        state += f", PS5: {rp}"
    return [("Uygulama sürümü", __version__), ("Cihaz modeli", device_model()), ("İşletim sistemi", os_name()),
            ("Yazı okuma", str(info.get("ocr", "…"))),
            ("Çeviri", " + ".join(x for x in (info.get("hizli"), info.get("kalite")) if x) or "yok"),
            ("TV", f"{brand} · {tv}" + (f" · TV uygulaması {ctl.tv_app_version()}" if
                                         getattr(ctl, "tv_app_version", lambda: None)() else "")),
            ("Görüntü kaynağı", src), ("Şu anki durum", state)]


def info_text(ctl) -> str:  # noqa: ANN001
    return "\n".join(f"{k}: {v}" for k, v in device_info(ctl))


def issue_url(ctl) -> str:  # noqa: ANN001
    from urllib.parse import urlencode
    body = ("**Ne oldu?**\n\n\n**Ne bekliyordun?**\n\n\n**Cihaz bilgileri**\n```\n" + info_text(ctl) + "\n```\n")
    return ISSUES_URL + "?" + urlencode({"title": "Sorun: ", "body": body})
