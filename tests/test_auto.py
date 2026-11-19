import os
import socket
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from altyazi import ps5  # noqa: E402


def fake_ps5(awake: bool):
    """127.0.0.1 üstünde SRCH'e cevap veren sahte PS5. (port, durdur) döndürür."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    s.settimeout(0.2)
    stop = threading.Event()

    def run():
        while not stop.is_set():
            try:
                data, addr = s.recvfrom(1024)
            except socket.timeout:
                continue
            if data.startswith(b"SRCH * HTTP/1.1") and b"00030010" in data:
                code = "200 Ok" if awake else "620 Server Standby"
                s.sendto(f"HTTP/1.1 {code}\nhost-id:ABC\nhost-type:PS5\nhost-name:PS5-123\n"
                         f"host-request-port:997\ndevice-discovery-protocol-version:00030010\n".encode(), addr)
        s.close()
    threading.Thread(target=run, daemon=True).start()
    return s.getsockname()[1], stop


@pytest.mark.parametrize("awake", [True, False])
def test_discover_ps5(awake):
    port, stop = fake_ps5(awake)
    try:
        found = ps5.discover(0.8, targets=["127.0.0.1"], port=port)
    finally:
        stop.set()
    assert len(found) == 1
    c = found[0]
    assert (c.ip, c.name, c.awake, c.host_type) == ("127.0.0.1", "PS5-123", awake, "PS5")


def test_parse_garbage():
    assert ps5.parse_response(b"hello", "1.2.3.4") is None


@pytest.fixture
def ctl(tmp_path, monkeypatch):
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    from altyazi import config as config_mod
    from altyazi.app import AppController
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(AppController, "warmup", lambda self: None)
    cfg = config_mod.load()
    cfg.sunucu.port = 18788
    c = AppController(cfg)
    c.state = "hazir"
    calls = []
    monkeypatch.setattr(c, "start", lambda: (calls.append("start"), setattr(c, "state", "calisiyor")))
    monkeypatch.setattr(c, "stop", lambda: (calls.append("stop"), setattr(c, "state", "hazir")))
    c.calls = calls
    yield c
    c._src_timer.stop()
    c._ps5_timer.stop()


def test_chiaki_args(ctl):
    assert ctl.chiaki_args(True) == []                     # PS5 adı/IP yoksa sadece uygulamayı aç
    ctl.cfg.otomatik.ps5_adi, ctl.cfg.otomatik.ps5_ip = "PS5-123", "192.168.1.30"
    assert ctl.chiaki_args(True) == ["stream", "PS5-123", "192.168.1.30", "--exit-app-on-stream-exit", "--fullscreen"]
    assert ctl.chiaki_args(False) == []


def test_auto_start_and_stop_with_chiaki_window(ctl):
    ctl._auto_source(True)
    assert ctl.calls == ["start"]
    ctl._auto_source(True)                                  # zaten çalışıyor: tekrar başlatma
    assert ctl.calls == ["start"]
    ctl._auto_source(False)                                 # pencere kapandı
    assert ctl.calls == ["start", "stop"]


def test_user_stop_is_respected_until_window_reopens(ctl, monkeypatch):
    ctl._auto_source(True)
    ctl._user_stopped = True                                # kullanıcı elle durdurdu
    ctl.state = "hazir"
    ctl._auto_source(True)
    assert ctl.calls == ["start"]                           # pencere hâlâ açık: kendiliğinden başlamaz
    ctl._auto_source(False)
    ctl._auto_source(True)                                  # pencere yeniden açıldı
    assert ctl.calls == ["start", "start"]


def test_remote_commands(ctl):
    from PySide6.QtWidgets import QApplication
    r = ctl.command("durum")
    assert r["durum"] == "hazir" and r["mesaj"] == "Çeviri kapalı"
    got = []
    ctl._uiCommand.connect(got.append)
    assert ctl.command("baslat_durdur")["mesaj"] == "Başlatılıyor..."
    assert ctl.command("baglan")["mesaj"].startswith("chiaki")
    QApplication.processEvents()
    assert got == ["toggle", "baglan"]


def test_chiaki_window_crop_to_game_image():
    """chiaki pencere modunda: başlık çubuğu ve siyah bantlar kırpılır, TV'deki yazı kaymasın."""
    from altyazi.winutil import crop_in_frame, fit_aspect
    # 1280x800 iç alan (16:10): üstte/altta 40 px bant, oyun 1280x720
    assert fit_aspect((100, 131, 1380, 931)) == (100, 171, 1380, 891)
    # 21:9 pencere: sağda solda bant
    assert fit_aspect((0, 0, 2560, 1080)) == (320, 0, 2240, 1080)
    # kare pencerenin tamamı (31 px başlık çubuğu dahil), ekran ölçeği 1:1
    captured = (100, 100, 1380, 931)
    inner = fit_aspect((100, 131, 1380, 931))
    assert crop_in_frame(1280, 831, captured, inner) == (0, 71, 1280, 791)
    # tam ekran 16:9: kırpma yok
    assert crop_in_frame(1920, 1080, (0, 0, 1920, 1080), fit_aspect((0, 0, 1920, 1080))) is None


def test_old_user_config_gets_phone_zone_once(tmp_path, monkeypatch):
    """Ayarlarını kaydetmiş kullanıcıya yeni telefon alanı bir kez eklenir; silerse geri gelmez."""
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from altyazi import config
    cfg = config.load()
    cfg.bolgeler = [b for b in cfg.bolgeler if b.ad != "telefon"]
    cfg.gocler = []
    config.save(cfg)
    again = config.load()
    assert [b.ad for b in again.bolgeler].count("telefon") == 1 and "telefon-alani" in again.gocler
    again.bolgeler = [b for b in again.bolgeler if b.ad != "telefon"]        # kullanıcı sildi
    config.save(again)
    assert "telefon" not in [b.ad for b in config.load().bolgeler]
