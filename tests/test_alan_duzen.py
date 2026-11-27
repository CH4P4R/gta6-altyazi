"""Okuma alanlarını ekranda fareyle düzenleme: geometri (alan_duzen.RegionEdit) ve pencereye bağlanması."""

from altyazi.alan_duzen import MIN_W, RegionEdit
from altyazi.config import BolgeCfg, Config


def edit():
    cfg = Config()
    cfg.bolgeler = [BolgeCfg(ad="altyazi", alan=[0.1, 0.8, 0.9, 0.95]),
                    BolgeCfg(ad="yardim", alan=[0.02, 0.05, 0.3, 0.2], tur="arayuz", beyaz_min=200)]
    return cfg, RegionEdit.from_config(cfg.bolgeler)


def test_move_resize_and_clamp():
    _cfg, ed = edit()
    assert ed.hit(0.15, 0.1) == (1, "move")
    assert ed.press(0.15, 0.1)
    ed.move(0.25, 0.2)                                      # 0.1 sağa, 0.1 aşağı
    x0, y0, x1, y1 = ed.regions[1].alan
    assert abs(x0 - 0.12) < 1e-9 and abs(y0 - 0.15) < 1e-9 and abs(x1 - 0.40) < 1e-9
    ed.move(-5, -5)                                         # ekran dışına taşınamaz
    assert ed.regions[1].alan[0] == 0.0 and ed.regions[1].alan[1] == 0.0
    ed.release()
    # sağ alt köşeden büyüt
    x0, y0, x1, y1 = ed.regions[0].alan
    assert ed.hit(x1, y1) == (0, "br")
    ed.press(x1, y1)
    ed.move(x1 + 0.05, 2.0)
    assert ed.regions[0].alan[2] == x1 + 0.05 and ed.regions[0].alan[3] == 1.0
    ed.move(-3, -3)                                         # en küçük boyun altına inmez
    a = ed.regions[0].alan
    assert a[2] - a[0] >= MIN_W - 1e-9 and a[3] > a[1]


def test_add_toggle_remove_and_apply_keeps_settings():
    cfg, ed = edit()
    i = ed.add(0.7, 0.3)
    assert ed.regions[i].ad == "ek1"
    assert not ed.remove(0), "ana altyazı alanı silinmez"
    ed.toggle(1)
    out = ed.apply_to(cfg.bolgeler)
    assert [b.ad for b in out] == ["altyazi", "yardim", "ek1"]
    assert out[1].aktif is False and out[1].beyaz_min == 200, "okuma ayarları korunur"
    assert out[2].tur == "arayuz" and abs(out[2].alan[0] - 0.55) < 1e-6
    ed.remove(1)
    assert [b.ad for b in ed.apply_to(cfg.bolgeler)] == ["altyazi", "ek1"]


def test_overlay_window_edit_mode(qtbot=None):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from altyazi.overlay import Bridge, Painter, VideoWindow
    w = VideoWindow(Painter("Arial", False), Bridge())
    w.resize(1000, 500)
    w.show()
    app.processEvents()
    cfg, ed = edit()
    got = []
    w.start_edit(ed, got.append)
    w.grab()                                                  # düzenleme katmanı çizilebiliyor
    area = w._edit_area()

    def ev(kind, x, y, button=Qt.LeftButton):
        pos = QPointF(area.left() + x * area.width(), area.top() + y * area.height())
        return QMouseEvent(kind, pos, pos, button, button if kind != QMouseEvent.Type.MouseButtonRelease else
                           Qt.NoButton, Qt.NoModifier)
    w.mousePressEvent(ev(QMouseEvent.Type.MouseButtonPress, 0.15, 0.1))
    w.mouseMoveEvent(ev(QMouseEvent.Type.MouseMove, 0.35, 0.1))
    w.mouseReleaseEvent(ev(QMouseEvent.Type.MouseButtonRelease, 0.35, 0.1))
    w._finish(True)
    assert got and got[0] is ed and abs(ed.regions[1].alan[0] - 0.22) < 0.01
    assert w.painter_.edit is None
    w.close()
