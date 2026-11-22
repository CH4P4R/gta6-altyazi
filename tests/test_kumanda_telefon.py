"""Telefon kumandası: /kumanda sayfası, /marka/ görselleri ve kartların bilgisi (AppController.command("durum"))."""

import http.client
import json
import socket
import time
import types

import pytest

from altyazi import server
from altyazi.server import EventServer


def free_port():
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def srv(tmp_path, monkeypatch):
    (tmp_path / "simge.png").write_bytes(b"\x89PNG\r\n\x1a\nsahte")
    (tmp_path / "sahne.json").write_text('{"w": 1600, "h": 900}', encoding="utf-8")
    (tmp_path / "gizli.txt").write_text("gizli", encoding="utf-8")
    monkeypatch.setattr(server, "MARKA_DIR", tmp_path)
    port = free_port()
    s = EventServer(port, on_command=lambda ad: {"durum": "hazir"} if ad == "durum" else {"mesaj": "ok"})
    s.start()
    time.sleep(0.2)
    s.port = port
    return s


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    c.request("GET", path)          # http.client yolu olduğu gibi gönderir ('..' düzeltilmez)
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, dict(r.getheaders()), body


def test_marka_serves_files(srv):
    st, h, body = get(srv.port, "/marka/simge.png")
    assert st == 200 and body.startswith(b"\x89PNG")
    assert h["Content-Type"] == "image/png" and h["Cache-Control"] == "max-age=3600"
    st, h, body = get(srv.port, "/marka/sahne.json?v=2")
    assert st == 200 and json.loads(body) == {"w": 1600, "h": 900}
    assert h["Content-Type"].startswith("application/json")


@pytest.mark.parametrize("path", [
    "/marka/../server.py", "/marka/..%2Fserver.py", "/marka/%2e%2e/app.py", "/marka/../../altyazi/app.py",
    "/marka/gizli.txt", "/marka/Simge.png", "/marka/alt/simge.png", "/marka/simge.png/", "/marka/",
    "/marka/yok.png", "/marka/simge.png%00.json", "/marka/.png",
])
def test_marka_rejects_bad_names(srv, path):
    st, _, body = get(srv.port, path)
    assert st == 404
    assert b"PNG" not in body and b"gizli" not in body


def test_kumanda_page_has_new_screens(srv):
    for path in ("/kumanda", "/ekran"):
        st, h, body = get(srv.port, path)
        assert st == 200 and h["Content-Type"].startswith("text/html")
        page = body.decode("utf-8")
        assert "<title>GTA6 Altyazı</title>" in page and 'name="theme-color"' in page
        for s in ("Çeviriyi başlat", "Hazır", "Altyazı açık", "Altyazı kapalı", "Fişi takın", "Fişi çekin",
                  "Ekranı çevir", "Duraklat", "Son çeviriler", "TÜRKÇE ALTYAZI", "Devam", "Geç",
                  "/marka/sahne.json", "/marka/rozet.png", "env(safe-area-inset-bottom)", "prefers-reduced-motion"):
            assert s in page, s
        assert "innerHTML" not in page            # sunucudan gelen yazı yalnız textContent ile basılır
        assert "http://" not in page and "https://" not in page   # dış bağlantı yok (SVG xmlns da gerekmiyor)


def test_remote_string_is_plain():
    assert "\\" not in server.REMOTE              # düz (r olmayan) Python dizgisi: kaçış karakteri kaymasın


def _fake_ctl(**kw):
    from altyazi.config import Config
    ctl = types.SimpleNamespace(cfg=Config(), state="hazir", ps5_state="acik", pipe=None, engine=None, engine_info={},
                                history=[], server=None)
    for k, v in kw.items():
        setattr(ctl, k, v)
    return ctl


def test_durum_keeps_old_keys_and_adds_card_info():
    from altyazi.app import AppController
    ctl = _fake_ctl()
    ctl.cfg.ps5.ad = "PS5-777"
    ctl.cfg.kaynak.oyun_yeri = "tv"
    ctl.engine_info = {"kalite": "claude", "hizli": "yerel (GPU)"}
    pack = types.SimpleNamespace(count=1200)
    ctl.engine = types.SimpleNamespace(packs=types.SimpleNamespace(packs=[pack, types.SimpleNamespace(count=300)]))
    ctl.history = [object()] * 12
    ctl.server = types.SimpleNamespace(tv_count=1)
    d = AppController.command(ctl, "durum")
    for k in ("durum", "ps5", "duraklatildi", "remoteplay", "mesaj"):
        assert k in d
    assert d["durum"] == "hazir" and d["ps5"] == "acik" and d["duraklatildi"] is False and d["mesaj"] == "Çeviri kapalı"
    assert d["ps5_adi"] == "PS5-777" and d["cikis"] == "TV" and d["tv_bagli"] is True and d["ceviri"] == "Claude"
    assert d["paket_oyun"] == 2 and d["paket_satir"] == 1500 and d["paket_acik"] is True
    assert d["oturum_satir"] == 12 and d["surum"]
    json.dumps(d)                                  # sayfaya JSON olarak gider


def test_card_info_is_defensive():
    from altyazi.app import remote_card_info
    # motorlar hazır değil: paket alanları yok, motor adı ayardan
    ctl = _fake_ctl()
    ctl.cfg.ceviri.kalite = "yok"
    ctl.cfg.ceviri.hizli = "google"
    ctl.cfg.otomatik.ps5_adi = "PS5-123"
    ctl.cfg.kaynak.oyun_yeri = "monitor"
    d = remote_card_info(ctl)
    assert "paket_oyun" not in d and "paket_satir" not in d
    assert d["ceviri"] == "Google" and d["ps5_adi"] == "PS5-123" and d["cikis"] == "Bilgisayar" and d["tv_bagli"] is False
    # bozuk durum: hiçbir alan hata fırlatmaz
    broken = types.SimpleNamespace(cfg=None, engine=types.SimpleNamespace(), history=None, server=object())
    d = remote_card_info(broken)
    assert isinstance(d, dict) and "ps5_adi" not in d and "paket_oyun" not in d
    assert remote_card_info(object()).keys() <= {"surum"}
