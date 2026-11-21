"""Yeni arayüz: ortak parçalar, sistem sağlığı denetimleri, akış istatistikleri ve sayfaların çalışması."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from altyazi import saglik  # noqa: E402
from altyazi.remoteplay import StreamStats  # noqa: E402


def test_stream_stats_counts_freezes_and_fps():
    s = StreamStats()
    t = 100.0
    for i in range(300):                       # 10 sn, 30 fps
        s.frame(t + i / 30)
    s.frame(t + 10 + 1.0)                       # 1 sn donma
    s.drop(t + 11)
    sm = s.summary(t + 11.1)
    assert 25 <= sm["fps"] <= 31
    assert sm["donma_dk"] > 0 and sm["kopma_10dk"] == 1 and sm["son_kare_sn"] == 0.1


def test_network_parsing():
    route = "   route to: default\ndestination: default\n  interface: en0\n"
    ports = ("Hardware Port: Ethernet\nDevice: en1\nEthernet Address: x\n\n"
             "Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: y\n")
    assert saglik.mac_default_iface(route) == "en0"
    assert saglik.mac_port_of("en0", ports) == "Wi-Fi" and saglik.mac_port_of("en1", ports) == "Ethernet"
    assert saglik.kind_of("Wi-Fi") == "wifi" and saglik.kind_of("Ethernet 2") == "kablo"
    assert saglik.kind_of("USB 10/100/1000 LAN") == "kablo" and saglik.kind_of(None) == "bilinmiyor"


def test_health_rows():
    bad = {"fps": 24, "donma_dk": 2.6, "kopma_10dk": 0}
    assert saglik.check_network("wifi", bad)["state"] == "warn"
    assert saglik.check_network("kablo", bad)["state"] == "ok"
    assert saglik.check_picture(bad)["state"] == "warn" and "kablo" in saglik.check_picture(bad)["advice"]
    assert saglik.check_picture(None)["state"] == "off"
    assert saglik.check_ps5(True, "bagli", {"kopma_10dk": 0})["sub"] == "Bağlı, kopma yok"
    assert saglik.check_ps5(False, "", None)["state"] == "off"
    assert saglik.check_speed(300, 1)["state"] == "ok" and "0,3 sn" in saglik.check_speed(300, 1)["sub"]
    assert saglik.check_speed(2500, 4)["state"] == "bad"
    assert saglik.check_tv("bagli", "android", "1.2.3.4")["state"] == "ok"
    assert saglik.check_tv("", "lg", "")["sub"] == "Kurulmadı"


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    from altyazi import config as config_mod
    from altyazi.app import AppController
    from altyazi.ui import theme as T
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(T.QSS)
    cfg = config_mod.load()
    cfg.sunucu.port = 18797
    return app, AppController(cfg)


def test_widgets(tmp_path, monkeypatch):
    app, ctl = _app(tmp_path, monkeypatch)
    from altyazi.ui.parcalar import PinInput, RadioCard, RadioGroup, Segmented, Toggle
    pin = PinInput(8)
    seen = []
    pin.changed.connect(seen.append)
    pin._typed(0, "1234-5678")                  # yapıştırma kutulara dağılır, tire atılır
    assert pin.text() == "12345678" and seen[-1] == "12345678"
    pin.clear()
    assert pin.text() == ""
    seg = Segmented([("tv", "TV"), ("pc", "PC")], "pc")
    assert seg.value() == "pc"
    seg.buttons["tv"].click()
    assert seg.value() == "tv"
    t = Toggle("Kalın", True)
    assert t.isChecked() and t.sizeHint().width() > 46
    got = []
    g = RadioGroup(on_change=got.append)
    a, b = g.add("a", RadioCard("A")), g.add("b", RadioCard("B"))
    g.set("a")
    b.clicked.emit()
    assert g.value() == "b" and got == ["b"] and not a.isChecked()
    ctl.shutdown()


def test_pages(tmp_path, monkeypatch):
    app, ctl = _app(tmp_path, monkeypatch)
    from altyazi.ui.main_window import MainWindow
    win = MainWindow(ctl)
    for key in ("look", "translate", "tv", "health", "about", "settings", "history"):
        win.go(key)
        app.processEvents()
    look = win.pages["look"]
    look._preset("sinema")
    assert look.colors.current == "yellow" and look.bg.value() == 0
    assert look.style_cards["sinema"].property("checked")
    look.save()
    assert ctl.cfg.tv.yazi_rengi == "yellow"
    assert ctl.server is None or ctl.server.tv_style["textColor"] == "yellow"
    tr = win.pages["translate"]
    tr.gem.setText("abc")
    assert "kayıtlı" in tr.key_rows["gemini"][0].text()
    tr.qual_group.set("deepl", user=True)
    assert tr.more.body.isVisibleTo(tr.more)
    health = win.pages["health"]
    health._kind = "wifi"
    health.refresh()
    assert "ag" in health.rows and health.rows["ag"].sub.text() == "Wi-Fi"
    assert "Uygulama sürümü" in saglik.info_text(ctl)
    assert saglik.issue_url(ctl).startswith(saglik.ISSUES_URL)
    ctl.shutdown()
