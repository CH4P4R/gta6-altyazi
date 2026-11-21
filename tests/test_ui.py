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
    from altyazi.harcama import tracker
    tracker.add("claude-opus-5-5", {"input_tokens": 300, "output_tokens": 60, "speed": "fast"})
    app.processEvents()
    home = win.pages["home"]
    assert home.spend.text().startswith("Claude: bu oturum") and "toplam" in home.spend_sub.text()
    assert (tmp_path / "harcama.json").exists() or tracker.path is not None
    assert win.pages["history"].table.rowCount() == 1
    wiz = Wizard(ctl, win)
    from altyazi.ui.wizard import P_PS5, P_TV, REHBER, STEPS
    for i in range(len(STEPS)):
        wiz._go(i)
        app.processEvents()
    # resimli rehber: her seçimde adımlar baştan sona gezilir, görseller var
    # TV'de: chiaki rehberi yok, PS5'e arka planda bağlanma paneli; Devam doğrudan TV adımına
    wiz._set_where("tv")
    wiz._go(P_PS5)
    assert wiz.ps5_stack.currentIndex() == 0 and wiz.seg_row.isHidden()
    assert wiz._guide(P_PS5) is None
    wiz.next.click()
    assert wiz.stack.currentIndex() == P_TV
    # Monitörde ve ikisinde: chiaki-ng resimli rehberi baştan sona gezilir, görseller var
    for where in ("monitor", "ikisi"):
        wiz._set_where(where)
        wiz._go(P_PS5)
        if where == "ikisi":
            assert not wiz.seg_row.isHidden() and wiz.ps5_stack.currentIndex() == 0
            wiz.seg_chiaki.click()
        assert wiz.ps5_stack.currentIndex() == 1
        g = wiz.ps5_guide
        names = [st.get("img") for st in g.steps if st.get("img")]
        assert all((REHBER / f"{n}.png").exists() for n in names)
        assert any(st.get("img") == "kol-usb" for st in g.steps)
        assert (g.steps[0]["title"].startswith("İkinci PSN")) == (where != "monitor")
        steps = 0
        while g.can_next():
            wiz.next.click()
            steps += 1
        assert steps == len(g.steps) - 1
        wiz.next.click()                       # rehber bitti: sonraki ana adım
        assert wiz.stack.currentIndex() == (P_TV if where != "monitor" else P_TV + 1)
    # Son sayfa seçime göre
    wiz._set_where("tv")
    wiz._go(len(STEPS) - 1)
    assert "kendiliğinden" in wiz.done_page.subtitle.text() and "chiaki" not in wiz.auto_cb.text()
    wiz._set_where("monitor")
    wiz._go(len(STEPS) - 1)
    assert "chiaki" in wiz.done_page.subtitle.text()
    assert all((REHBER / f"{st['img']}.png").exists() for st in wiz.tv_guide.steps)
    # TV adımı: marka seçince o markanın resimli adımları gelir, LG parolası yalnız LG'de görünür
    wiz._go(P_TV)
    for brand, first in (("samsung", "Uygulamalar"), ("lg", "LG geliştirici"), ("android", "TV'de geliştirici")):
        wiz.tv_brand.setCurrentIndex(wiz.tv_brand.findData(brand))
        app.processEvents()
        g = wiz.tv_guide
        assert g.index == 0 and g.steps[0]["title"].startswith(first)
        assert all((REHBER / f"{st['img']}.png").exists() for st in g.steps if st.get("img"))
        assert (not wiz.lg_pass.isHidden()) == (brand == "lg")      # bağlan adımında görünür
        assert wiz.cfg.tv.marka == brand
    wiz.tv_brand.setCurrentIndex(wiz.tv_brand.findData("samsung"))
    g = wiz.tv_guide
    g.show_step(next(i for i, st in enumerate(g.steps) if st.get("id") == "pcip"))
    assert "IP" in wiz.pc_ip.text() and wiz.pc_ip.isVisibleTo(wiz)
    tvp = win.pages["tv"]
    tvp.brand.setCurrentIndex(tvp.brand.findData("samsung"))
    assert "123" in tvp.howto.text() and "Host PC IP" in tvp.howto.text()
    tvp._open_guide()
    assert win.pages["guide"].guides[win.pages["guide"].group.checkedId()]["key"] == "samsung" \
        if win.pages["guide"].group.checkedId() >= 0 else True
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
