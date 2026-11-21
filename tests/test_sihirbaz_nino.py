"""Sihirbazdaki Nino benzeri eklemeler: ihtiyaç kartları, TV türü kartları, çeviri 'hazır' ekranı, yardım önerileri."""

import os
import time
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    from altyazi.ui import theme as T
    a = QApplication.instance() or QApplication([])
    a.setStyleSheet(T.QSS)
    return a


@pytest.fixture()
def wiz(app, tmp_path, monkeypatch):
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from altyazi import config as config_mod
    from altyazi.app import AppController
    from altyazi.ui.wizard import Wizard

    cfg = config_mod.load()
    cfg.sunucu.port = 18993
    ctl = AppController(cfg)
    w = Wizard(ctl)
    w.show()
    app.processEvents()
    yield w
    w.close()
    deadline = time.time() + 15
    while ctl.state == "hazirlaniyor" and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    ctl.shutdown()


def click(widget):  # noqa: ANN001
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.mouseClick(widget, Qt.LeftButton)


def test_welcome_lists_what_you_need(wiz):
    titles = [c.title.text() for c in wiz.need_cards]
    assert titles == ["PS5", "Akıllı TV", "İkinci PSN hesabı"]
    subs = [c.sub.text() for c in wiz.need_cards]
    assert "Wi-Fi" in subs[0] and "Samsung" in subs[1] and "Ücretsiz" in subs[2]
    assert "5 dakika" in wiz.welcome_time.text()
    assert all(c.isVisibleTo(wiz) for c in wiz.need_cards)


def test_lg_samsung_card_and_segment_set_brand(wiz, app):
    from altyazi.ui.wizard import P_TV
    wiz._set_where("tv")
    wiz._go(P_TV)
    wiz._tv_phase("choose")
    assert wiz.tv_stack.currentIndex() == 0 and wiz._guide(P_TV) is None
    click(wiz.tv_kind_cards["lgsam"])
    app.processEvents()
    assert wiz.tv_brand.currentData() == "lg" and wiz.cfg.tv.marka == "lg"
    assert wiz.tv_kinds.value() == "lgsam" and not wiz.tv_lgsam.isHidden()
    assert not wiz.lg_pass.isHidden()
    wiz.tv_lgsam.buttons["samsung"].click()
    assert wiz.tv_brand.currentData() == "samsung" and wiz.cfg.tv.marka == "samsung"
    assert wiz.lg_pass.isHidden()
    assert wiz.tv_stack.currentIndex() == 0              # kartlar seçimi değiştirir, sayfayı değil
    wiz.next.click()                                     # Devam: o markanın resimli adımları
    assert wiz.stack.currentIndex() == P_TV and wiz.tv_stack.currentIndex() == 1
    assert wiz.tv_guide.steps[0]["title"].startswith("Uygulamalar")
    assert "Samsung" in wiz.tv_brand_lbl.text()
    wiz.back.click()                                     # rehberin başında Geri: TV türü seçimine döner
    assert wiz.stack.currentIndex() == P_TV and wiz.tv_stack.currentIndex() == 0
    click(wiz.tv_kind_cards["android"])
    assert wiz.tv_brand.currentData() == "android"
    # marka listesi dışarıdan değişirse doğrudan adımlar gösterilir ve kartlar eşlenir
    wiz.tv_brand.setCurrentIndex(wiz.tv_brand.findData("lg"))
    assert wiz.tv_stack.currentIndex() == 1 and wiz.tv_kinds.value() == "lgsam" and wiz.tv_lgsam.value() == "lg"


def test_no_tv_card_switches_to_monitor_and_skips(wiz):
    from altyazi.ui.wizard import P_TRANSLATION, P_TV
    wiz._set_where("tv")
    wiz._go(P_TV)
    wiz._tv_phase("choose")
    click(wiz.tv_kind_cards["yok"])
    assert wiz.where == "monitor" and wiz.cfg.kaynak.oyun_yeri == "monitor"
    assert wiz.choice_cards["monitor"].isChecked()
    assert not wiz.tv_none_msg.isHidden()
    wiz.next.click()
    assert wiz.stack.currentIndex() == P_TRANSLATION
    wiz.back.click()                                     # TV adımı artık atlanır
    assert wiz.stack.currentIndex() == P_TV - 1
    wiz._go(P_TV)
    click(wiz.tv_kind_cards["android"])                  # vazgeçti: önceki seçim geri gelir
    assert wiz.where == "tv" and wiz.cfg.kaynak.oyun_yeri == "tv"


def test_translation_ready_card(wiz, monkeypatch):
    from altyazi.ui.wizard import P_TRANSLATION, TEST_LINE
    wiz._go(P_TRANSLATION)
    wiz.engine.setCurrentIndex(wiz.engine.findData("gemini"))
    assert wiz.gemini_steps.isVisibleTo(wiz) and wiz.key_btn.text() == "Ücretsiz anahtar al"
    sent = []
    monkeypatch.setattr(wiz.ctl, "test_translation", sent.append)
    wiz._pending_test = True
    wiz._on_engines({"ocr": "CPU", "hizli": None, "kalite": "gemini"})
    assert sent == [TEST_LINE]
    assert not wiz.ok_box.isVisibleTo(wiz)
    wiz._on_test(types.SimpleNamespace(text="Arabaya bin.", source="yerel", ms=5, quality=1))
    assert not wiz.ok_box.isVisibleTo(wiz)               # hızlı katman anahtarın çalıştığını göstermez
    wiz._on_test(types.SimpleNamespace(text="Arabaya bin, hemen gidiyoruz!", source="gemini", ms=600, quality=2))
    assert wiz.ok_box.isVisibleTo(wiz)
    assert wiz.ok_title.text() == "Gemini hazır" and "Gemini ile" in wiz.ok_sub.text()
    assert wiz.ok_preview.text == "Arabaya bin, hemen gidiyoruz!"
    assert "altyazıları" in wiz.ok_info[0].text() and "Ücretsiz sınır" in wiz.ok_info[1].text()
    assert wiz.ok_info[2].text().startswith("DeepL, Claude ya da yerel bir modeli")
    assert not wiz.gemini_steps.isVisibleTo(wiz)
    # motor değişince eski "hazır" kalkar; Claude önbellekten gelse de tanınır
    wiz.engine.setCurrentIndex(wiz.engine.findData("claude"))
    assert not wiz.ok_box.isVisibleTo(wiz) and not wiz.gemini_steps.isVisibleTo(wiz)
    assert wiz.key_btn.text() == "Anahtar al"
    wiz._on_test(types.SimpleNamespace(text="Arabaya bin.", source="önbellek/claude", ms=1, quality=2))
    assert wiz.ok_title.text() == "Claude hazır"
    # seçilen motor açılamadıysa uyarı
    wiz._pending_test = True
    wiz._on_engines({"ocr": "CPU", "hizli": None, "kalite": None})
    assert "açılamadı" in wiz.test_out.text()


def test_help_chat_suggestions(app, monkeypatch):
    from altyazi.ui.yardim import GREETING, SUGGESTIONS, AskDialog
    dlg = AskDialog(types.SimpleNamespace(engine=None))
    dlg.show()
    assert "Merhaba! Ben yardımcın" in GREETING and "hangi cihazlar" in dlg.view.toPlainText()
    assert [b.text() for b in dlg.chip_buttons] == SUGGESTIONS
    assert all(b.objectName() == "chip" for b in dlg.chip_buttons)
    assert dlg.chips.isVisibleTo(dlg)
    asked = []
    monkeypatch.setattr(dlg.bot, "ask", lambda q, photo=None: asked.append(q) or "Tamam, **TV** ile başlayalım.")
    dlg.chip_buttons[1].click()
    deadline = time.time() + 5
    while not dlg.send_btn.isEnabled() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert asked == ["PS5 + bilgisayar monitörü"]
    assert not dlg.chips.isVisibleTo(dlg)
    text = dlg.view.toPlainText()
    assert "PS5 + bilgisayar monitörü" in text and "Tamam, TV ile başlayalım." in text
    dlg.close()
