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


def test_demo_source_and_new_settings(tmp_path, monkeypatch):
    from altyazi.capture import DEMO_LINES, DemoSource
    d = DemoSource(hold=4, gap=1)
    a, blank, b = d.frame_at(1.0), d.frame_at(4.5), d.frame_at(6.0)
    assert a.shape == (720, 1280, 3) and (a != blank).any() and (a != b).any()
    assert len(DEMO_LINES) >= 5
    app, ctl = _app(tmp_path, monkeypatch)
    from altyazi.ui.main_window import MainWindow
    win = MainWindow(ctl)
    if ctl.start_demo():                              # motorlar hazırsa başlar; deneme penceresi açılır
        assert ctl.demo and ctl.pipe is not None and ctl.window is not None
        ctl.stop()
        assert not ctl.demo
    home = win.pages["home"]
    home.show_where.buttons["monitor"].click()
    assert ctl.cfg.kaynak.oyun_yeri == "monitor"
    reg = win.pages["regions"]
    tg, sz = reg.extra_rows["yardim"]
    tg.setChecked(False)
    assert not next(z for z in ctl.cfg.bolgeler if z.ad == "yardim").aktif
    reg._gta6()
    assert all(z.aktif for z in ctl.cfg.bolgeler)
    keys = win.pages["settings"].keys
    keys["baslat"][1].setText("num5")
    win.pages["settings"].save()
    assert ctl.cfg.kisayol.baslat2 == "num5"
    tr = win.pages["translate"]
    tr.spk_show.setChecked(False)
    tr.save()
    assert ctl.cfg.ceviri.konusan_goster is False
    look = win.pages["look"]
    look.tv_font.setCurrentIndex(look.tv_font.findData("aksiyon"))
    look.spk_color.setChecked(True)
    look.save()
    assert ctl.cfg.tv.yazi_tipi == "aksiyon" and ctl.cfg.tv.konusan_renk
    if ctl.server is not None:
        assert ctl.server.tv_style["font"] == "aksiyon" and ctl.server.tv_style["speakerColors"] is True
    ctl.shutdown()


def test_pipeline_skips_inactive_zones_and_speaker_option():
    from altyazi import config as config_mod
    from altyazi.kalite import konusan
    from altyazi.pipeline import Pipeline
    cfg = config_mod.Config()
    cfg.bolgeler[0].aktif = False
    p = Pipeline.__new__(Pipeline)
    zones = [z for z in cfg.bolgeler if getattr(z, "aktif", True)]
    assert len(zones) == len(cfg.bolgeler) - 1 and p is not None
    assert konusan.present("LUCIA: Gitmeliyiz.", "LUCIA: We have to go.", False) == "Gitmeliyiz."


def test_round2_settings(tmp_path, monkeypatch):
    app, ctl = _app(tmp_path, monkeypatch)
    from altyazi.ui.main_window import MainWindow
    win = MainWindow(ctl)
    reg = win.pages["regions"]
    reg.select(0)
    z = reg.current()
    reg.center.setChecked(True)
    reg.edges["sol"].setValue(20)
    assert abs(z.alan[0] - 0.20) < 0.01 and abs(z.alan[2] - 0.80) < 0.01      # ortada tut
    reg.edges["ust"].setValue(70)
    assert abs(z.alan[1] - 0.70) < 0.01
    from altyazi.pipeline import DisplayItem
    it = DisplayItem("altyazi", (0.3, 0.85, 0.7, 0.93), (0.1, 0.76, 0.9, 0.97), 0.03, "Hi.", "Selam.", "orta", "alt",
                     255, 1.3, seq=5)
    ctl.show(it)
    app.processEvents()
    assert reg.last_tr.text() == "Selam." and reg.last_en.text() == "Hi."
    tr = win.pages["translate"]
    tr.packs_on.setChecked(False)
    assert ctl.cfg.ceviri.paket_kullan is False
    tr.ocr_engine.setCurrentIndex(tr.ocr_engine.findData("ppocr"))
    tr.sik.setChecked(True)
    tr.mt_threads.setValue(4)
    tr.save()
    assert ctl.cfg.ocr.motor == "ppocr" and ctl.cfg.ocr.sik_oku and ctl.cfg.ceviri.yerel_is_parcacigi == 4
    look = win.pages["look"]
    look.fit.setChecked(False)
    look.save()
    assert ctl.cfg.tv.uydur is False
    if ctl.server is not None:
        assert ctl.server.tv_style["lineScale"] == 0
    about = win.pages["about"]
    about.theme.buttons["acik"].click()
    assert ctl.cfg.gosterim.tema == "acik"
    ctl.shutdown()


def test_light_theme_and_layout_forget(tmp_path):
    from altyazi.oyun.altyazi_yeri import SubtitleLayoutStore
    from altyazi.ui import theme as T
    old = (T.BG, T.QSS)
    try:
        T.apply("acik")
        assert T.BG == T.LIGHT["BG"] and T.LIGHT["CARD_BG"] in T.QSS
    finally:
        T.apply("koyu")
        import importlib
        importlib.reload(T)
    assert T.BG == old[0]
    st = SubtitleLayoutStore(tmp_path / "y.json")
    st.record((0.3, 0.88, 0.7, 0.93), "gta6")
    assert st.current.samples.get("gta6")
    st.forget("gta6")
    assert not st.current.samples.get("gta6")


def test_hold_waits_for_better_reading():
    from altyazi.pipeline import Pipeline
    p = Pipeline.__new__(Pipeline)
    p._pending = {}
    assert p._hold("k", "anything", 0.0, 0, 0) == "anything"           # kapalı: beklemez
    bad = "Ge7 in th3 c@r"
    first = p._hold("k", bad, 10.0, 800, 0)
    assert first is None                                               # bozuk: beklet
    good = "Get in the car, we gotta leave."
    assert p._hold("k", good, 10.2, 800, 0) == good                    # iyi okuma gelince hemen
    assert p._hold("j", bad, 20.0, 800, 0) is None
    assert p._hold("j", bad, 20.9, 800, 0) == bad                      # süre doldu: eldeki en iyi okuma
    assert p._hold("m", "and then we went to the", 0.0, 0, 300) is None  # yarım satır
    assert p._hold("m", "and then we went to the", 0.4, 0, 300) is not None


def test_plug_scene_obs_and_tv_app_version(tmp_path, monkeypatch):
    import re
    from pathlib import Path
    from altyazi.tv import TV_APP_VERSION
    js = Path(__file__).resolve().parents[1] / "tv-web" / "src" / "app.js"
    assert re.search(r"APP_VERSION = '([\d.]+)'", js.read_text("utf-8")).group(1) == TV_APP_VERSION
    assert saglik.check_tv_app("0.4.0", "0.5.0", True)["state"] == "warn"
    assert saglik.check_tv_app("0.5.0", "0.5.0", True)["state"] == "ok"
    assert saglik.check_tv_app(None, "0.5.0", False)["state"] == "off"
    app, ctl = _app(tmp_path, monkeypatch)
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from altyazi.ui.main_window import MainWindow
    win = MainWindow(ctl)
    win.resize(1400, 900)
    win.show()
    app.processEvents()
    home = win.pages["home"]
    got = []
    home.scene.plugged.disconnect()
    home.scene.plugged.connect(got.append)
    sc = home.scene
    g = sc._geo()
    def ev(kind, pt):
        return QMouseEvent(kind, pt, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    from PySide6.QtCore import QEvent
    sc.mousePressEvent(ev(QEvent.MouseButtonPress, g["rest"]))
    sc.mouseMoveEvent(ev(QEvent.MouseMove, g["socket"].center()))
    sc.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, g["socket"].center()))
    assert got == [True]                                             # fiş prize: başlat
    sc.setRunning(True)
    sc.mousePressEvent(ev(QEvent.MouseButtonPress, g["socket"].center()))
    sc.mouseMoveEvent(ev(QEvent.MouseMove, QPointF(50, 50)))
    sc.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, QPointF(50, 50)))
    assert got == [True, False]                                      # çekildi: durdur
    win.go("obs")
    app.processEvents()
    ctl.open_stream_window("#000000")
    assert ctl.stream_window.isVisible()
    ctl.stream_window.close()
    if ctl.server is not None:
        import json
        import urllib.request
        ctl.server.tv_version = None
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{ctl.cfg.sunucu.port}/events?v=0.5.0", timeout=2)
            r.readline()
            r.close()
        except Exception:  # noqa: BLE001
            pass
        assert ctl.tv_app_version() in ("0.5.0", None)
    ctl.shutdown()


def test_brand_assets_and_home_styles(tmp_path, monkeypatch):
    """Marka görselleri (tools/marka_gorsel.py) yerinde; ana ekranın iki görünümü (fiş / kaydırmalı düğme) çalışır."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    marka = root / "altyazi" / "ui" / "marka"
    for name in ("simge.png", "simge_yazisiz.png", "rozet.png", "bot.png", "logo.png", "logo_acik.png", "sahne.png",
                 "sahne_isik.png", "sahne.json"):
        assert (marka / name).stat().st_size > 200, name
    geo = json.loads((marka / "sahne.json").read_text("utf-8"))
    for key in ("screen", "socket", "ps5", "shelf", "plug_rest", "cable_from"):
        assert key in geo
    from PIL import Image
    assert Image.open(root / "tv-android/app/src/main/res/mipmap-nodpi/icon.png").size == (512, 512)
    assert Image.open(root / "tv-android/app/src/main/res/drawable-nodpi/banner.png").size == (640, 360)
    assert "logo.png" in (root / "tv-web/src/index.html").read_text("utf-8")
    assert '"ui" / "marka"' in (root / "packaging/gta6altyazi.spec").read_text("utf-8")    # kuruluma girer

    app, ctl = _app(tmp_path, monkeypatch)
    from altyazi.ui.main_window import MainWindow, app_icon
    assert not app_icon().isNull()
    win = MainWindow(ctl)
    win.resize(1400, 900)
    win.show()
    app.processEvents()
    home = win.pages["home"]
    assert home.stage.currentIndex() == 0                       # varsayılan: fiş
    home._set_style("dugme")
    assert home.stage.currentIndex() == 1 and ctl.cfg.gosterim.ana_ekran == "dugme"
    got = []
    home.slide.toggled.disconnect()
    home.slide.toggled.connect(got.append)
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    sl = home.slide
    pt = QPointF(sl.width() / 2, sl.height() / 2)
    sl.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, pt, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    sl.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, pt, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    assert got == [True]                                        # tıklamak açar
    sl.setOn(True)
    a, b = QPointF(sl.width() - 40, 50), QPointF(10, 50)
    sl.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, a, a, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    sl.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, b, b, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    sl.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, b, b, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    assert got == [True, False]                                 # sola kaydırmak kapatır
    home.tv_prev.setRunning(True)
    home.tv_prev.setText("Bu iş daha bitmedi.", "This isn't over.")
    assert not home.tv_prev.grab().isNull() and not home.scene.grab().isNull()
    ctl.shutdown()
