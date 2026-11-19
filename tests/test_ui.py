import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")


def test_main_window_and_wizard_build(tmp_path, monkeypatch):
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    from altyazi import config as config_mod
    from altyazi.app import AppController
    from altyazi.pipeline import DisplayItem
    from altyazi.ui import theme as T
    from altyazi.ui.main_window import MainWindow
    from altyazi.ui.wizard import Wizard

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(T.QSS)
    cfg = config_mod.load()
    cfg.sunucu.port = 18787
    ctl = AppController(cfg)
    win = MainWindow(ctl)
    for key in win.pages:
        win.go(key)
        app.processEvents()
    it = DisplayItem("altyazi", (0.3, 0.85, 0.7, 0.93), (0.1, 0.76, 0.9, 0.97), 0.03, "Hi.", "Selam.", "orta", "alt",
                     255, 1.3, source="yerel", quality=1, latency_ms=40, seq=1)
    ctl.show(it)
    app.processEvents()
    assert 1 in win.pages["home"].items
    assert win.pages["history"].table.rowCount() == 1
    wiz = Wizard(ctl, win)
    from altyazi.ui.wizard import P_PS5, P_TV, REHBER, STEPS
    for i in range(len(STEPS)):
        wiz._go(i)
        app.processEvents()
    # resimli rehber: her seçimde adımlar baştan sona gezilir, görseller var
    for where in ("monitor", "tv", "ikisi"):
        wiz._set_where(where)
        wiz._go(P_PS5)
        g = wiz.ps5_guide
        names = [st.get("img") for st in g.steps if st.get("img")]
        assert all((REHBER / f"{n}.png").exists() for n in names)
        assert any(st.get("img") == "kol-usb" for st in g.steps) == (where != "tv")
        assert (g.steps[0]["title"].startswith("İkinci PSN")) == (where != "monitor")
        steps = 0
        while g.can_next():
            wiz.next.click()
            steps += 1
        assert steps == len(g.steps) - 1
        wiz.next.click()                       # rehber bitti: sonraki ana adım
        assert wiz.stack.currentIndex() == (P_TV if where != "monitor" else P_TV + 1)
    assert all((REHBER / f"{st['img']}.png").exists() for st in wiz.tv_guide.steps)
    # ayar kaydetme: kullanıcı klasörüne yazılır ve geri okunur
    new = ctl.edit_config()
    new.tv.ip = "192.168.1.40"
    config_mod.save(new)
    assert config_mod.load().tv.ip == "192.168.1.40"
    deadline = time.time() + 15
    while ctl.state == "hazirlaniyor" and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    ctl.shutdown()
