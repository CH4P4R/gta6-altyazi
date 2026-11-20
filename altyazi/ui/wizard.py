"""İlk açılış kurulum sihirbazı."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import rehber
from ..app import CHIAKI_DOWNLOAD, AppController
from . import theme as T
from .guide import REHBER, Guide
from .widgets import Card, Dot, Icon, Logo, PreviewArt, QrCode, Stepper, button, hbox, label, vbox

STEPS = ["Hoş geldin", "Nerede oynayacaksın?", "PS5 ve chiaki-ng", "Televizyon", "Çeviri", "Hazır"]
P_WELCOME, P_WHERE, P_PS5, P_TV, P_TRANSLATION, P_DONE = range(6)
__all__ = ["Wizard", "STEPS", "REHBER", "P_WELCOME", "P_WHERE", "P_PS5", "P_TV", "P_TRANSLATION", "P_DONE"]
PSN_SIGNUP = rehber.PSN_SIGNUP


class Hero(QWidget):
    """Sihirbazın sol panelindeki degrade arka plan."""

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width() * 0.6, self.height())
        g.setColorAt(0, QColor("#1c1027"))
        g.setColorAt(0.55, QColor("#140f1d"))
        g.setColorAt(1, QColor("#2a1420"))
        p.fillRect(self.rect(), QBrush(g))
        glow = QColor(T.A1)
        glow.setAlphaF(0.10)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(-120, self.height() - 260, 380, 380)
        glow2 = QColor(T.A2)
        glow2.setAlphaF(0.08)
        p.setBrush(glow2)
        p.drawEllipse(self.width() - 140, -100, 260, 260)


def feature(icon: str, title: str, text: str) -> QHBoxLayout:
    ic = Icon(icon, 26, T.A2)
    return hbox(vbox(ic, None), vbox(label(title, "h3"), label(text, "muted", wrap=True), spacing=2), spacing=14)


def check_row(title: str, text: str, *buttons) -> Card:  # noqa: ANN002
    c = Card(inner=True, margins=14, spacing=4)
    dot = Dot("off")
    c.dot = dot
    head = hbox(dot, label(title, "h3"), None, *buttons, spacing=8)
    c.add(head)
    t = label(text, "muted", wrap=True)
    c.add(t)
    return c


CHOICES = [("monitor", "tv", "🖥️  Bilgisayar monitöründe",
            "chiaki-ng ile PS5'i bilgisayarda oynarım. Türkçe, chiaki penceresinin üstünde çıkar."),
           ("tv", "tv", "📺  TV'de",
            "PS5 HDMI ile TV'de, ben TV'den oynarım. Bilgisayar arka planda izler, Türkçe TV'de çıkar."),
           ("ikisi", "tv", "🔁  Bazen monitörde, bazen TV'de",
            "İkisini de kurarız; o gün hangisinde oynuyorsan o çalışır.")]


class Wizard(QDialog):
    def __init__(self, ctl: AppController, parent=None):  # noqa: ANN001
        super().__init__(parent)
        self.ctl = ctl
        self.cfg = ctl.edit_config()
        self.setWindowTitle("GTA6 Altyazı · Kurulum")
        self.setModal(True)
        self.resize(1120, 780)
        self.setMinimumSize(1000, 700)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = Hero()
        side.setFixedWidth(270)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(24, 26, 16, 22)
        sl.addWidget(Logo())
        self.stepper = Stepper(STEPS)
        sl.addWidget(self.stepper, 1)
        sl.addWidget(label("Ayarları sonra istediğin zaman\nAyarlar sayfasından değiştirebilirsin.", "faint"))
        root.addWidget(side)

        right = QFrame()
        right.setObjectName("page")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(40, 34, 40, 26)
        rl.setSpacing(16)
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        self.back = button("Geri", "ghost", self._back)
        self.skip = button("Bu adımı atla", "ghost", self._next)
        self.next = button("Başlayalım", "primary", self._next)
        self.next.setMinimumWidth(170)
        rl.addLayout(hbox(self.back, None, self.skip, self.next, spacing=10))
        root.addWidget(right, 1)

        self.where = self.cfg.kaynak.oyun_yeri if self.cfg.kaynak.oyun_yeri in ("monitor", "tv", "ikisi") else "ikisi"
        for builder in (self._welcome, self._where, self._ps5, self._tv, self._translation, self._done):
            self.stack.addWidget(builder())
        ctl.sourceStatus.connect(self._on_source)
        ctl.tvStatus.connect(self._on_tv)
        ctl.tvFound.connect(self._on_found)
        ctl.testResult.connect(self._on_test)
        ctl.enginesReady.connect(self._on_engines)
        self._go(0)

    # ------------------------------------------------------------------ sayfalar
    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        t = label(title, "display")
        lay.addWidget(t)
        lay.addWidget(label(subtitle, "muted", wrap=True))
        lay.addSpacing(6)
        return w, lay

    def _welcome(self) -> QWidget:
        w, lay = self._page("Oyun İngilizce, sen Türkçe oyna.",
                            "GTA 6'daki yazıları anında okuyup Türkçesini İngilizcenin tam yerine yazar. "
                            "Kurulum birkaç dakika sürer.")
        lay.addLayout(feature("translate", "Her yazı Türkçe",
                              "Diyalog altyazıları, sol üstteki yardım kutusu, sağ üstteki bildirimler. Telefon "
                              "ve menüler için tek tuşla tüm ekran."))
        lay.addLayout(feature("tv", "TV'de ve Discord yayınında",
                              "Sen TV'de gecikmesiz oynarsın; altyazı TV'de oyunun üstünde ve arkadaşlarının "
                              "izlediği yayında görünür."))
        lay.addLayout(feature("bolt", "Bekletmez",
                              "Ekran kartındaki model ilk çeviriyi ~50 ms'de gösterir, yapay zeka birkaç yüz ms sonra "
                              "daha doğal haliyle günceller. Aynı yazı tekrar çıkınca anında gelir."))
        lay.addSpacing(6)
        lay.addWidget(PreviewArt(), 1)
        return w

    def _where(self) -> QWidget:
        w, lay = self._page("Nerede oynayacaksın?",
                            "Kurulumu buna göre anlatacağım. Sonra Ayarlar'dan değiştirebilirsin.")
        self.where_group = QButtonGroup(self)
        self.where_group.setExclusive(True)
        for key, icon, title, text in CHOICES:
            b = QPushButton()
            b.setCheckable(True)
            b.setChecked(key == self.where)
            b.setMinimumHeight(92)
            t1, t2 = label(title, "h2"), label(text, "muted", wrap=True)
            for t in (t1, t2):
                t.setAttribute(Qt.WA_TransparentForMouseEvents)
                t.setStyleSheet("background: transparent;")
            inner = vbox(t1, t2, spacing=4)
            inner.setContentsMargins(20, 14, 20, 14)
            b.setLayout(inner)
            b.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 0; border-radius: 14px;"
                f" background: {T.SURFACE2}; border: 2px solid {T.BORDER}; color: {T.TEXT}; }}"
                f"QPushButton:hover {{ border-color: {T.BORDER_HI}; }}"
                f"QPushButton:checked {{ border-color: {T.A1}; background: {T.SURFACE3}; }}")
            b.clicked.connect(lambda _=False, k=key: self._set_where(k))
            self.where_group.addButton(b)
            lay.addWidget(b)
        lay.addWidget(label("Monitörde oynarken kendi PSN hesabını, TV'de oynarken ikinci bir PSN hesabı kullanırsın "
                            "(TV'deki kolun kopmasın diye). Hepsini adım adım göstereceğim.", "faint", wrap=True))
        lay.addStretch(1)
        return w

    def _set_where(self, key: str) -> None:
        self.where = key
        self.cfg.kaynak.oyun_yeri = key
        self.ps5_guide.set_steps(self._ps5_steps(), self._ps5_extras())
        self.ps5_guide.show_step(0)

    def _ps5(self) -> QWidget:
        w, lay = self._page("PS5 ve chiaki-ng",
                            "chiaki-ng, PS5'in görüntüsünü ağ üzerinden bilgisayara getiren ücretsiz programdır. "
                            "Adımları sırayla yap; her adımda neye basacağın resimde işaretli.")
        # 1. adımın düğmeleri: indir / gözat / aç + bulundu mu
        self.chiaki_btn_open = button("chiaki-ng'yi aç", None, self._open_chiaki)
        self.chiaki_state = label("", "muted", wrap=True)
        self.chiaki_dot = Dot("off")
        act1 = QWidget()
        act1.setLayout(vbox(hbox(button("İndirme sayfasını aç", "primary", lambda: webbrowser.open(CHIAKI_DOWNLOAD)),
                                 button("chiaki.exe'yi seç", None, self._browse_chiaki), self.chiaki_btn_open, None,
                                 spacing=10),
                            hbox(self.chiaki_dot, self.chiaki_state, 1, spacing=6), spacing=8))
        self.act_psn = QWidget()
        self.act_psn.setLayout(hbox(button("PSN hesabı aç", "primary", lambda: webbrowser.open(PSN_SIGNUP)), None))
        self.conn_dot = Dot("off")
        self.conn_state = label("chiaki-ng'de PS5'e bağlanınca burası yeşil olur.", "muted", wrap=True)
        self.act_conn = QWidget()
        self.act_conn.setLayout(hbox(self.conn_dot, self.conn_state, 1, spacing=6))
        self.act_chiaki = act1
        self.ps5_guide = Guide()
        lay.addWidget(self.ps5_guide, 1)
        self.ps5_guide.set_steps(self._ps5_steps(), self._ps5_extras())
        self._refresh_chiaki()
        return w

    def _ps5_steps(self) -> list[dict]:
        return rehber.chiaki_steps(self.where)

    def _ps5_extras(self) -> dict:
        return {"psn": self.act_psn, "indir": self.act_chiaki, "baglan": self.act_conn}

    def _tv(self) -> QWidget:
        w, lay = self._page("Televizyon",
                            "Türkçe altyazıyı TV'de oyunun üstünde göstermek için TV'ye küçük bir uygulama kurulur. "
                            "Bunu bilgisayar ağ üzerinden kendisi yapar. Önce TV'nin markasını seç, sonra resimli "
                            "adımları sırayla izle.")
        self.tv_brand = QComboBox()
        for key, text in rehber.TV_BRANDS:
            self.tv_brand.addItem(text, key)
        self.tv_brand.setCurrentIndex(max(0, self.tv_brand.findData(self.cfg.tv.marka)))
        lay.addLayout(hbox(label("TV markası", "h3"), self.tv_brand, None, spacing=12))
        self.tv_ip = QLineEdit(self.cfg.tv.ip)
        self.tv_ip.setPlaceholderText("TV'nin IP adresi")
        self.tv_scan_btn = button("Ağda ara", None, self._scan)
        self.tv_found = QComboBox()
        self.tv_found.hide()
        self.tv_found.currentIndexChanged.connect(lambda i: self.tv_ip.setText(self.tv_found.itemData(i) or
                                                                               self.tv_ip.text()))
        self.tv_conn_btn = button("Bağlan ve kur", "primary", self._tv_connect)
        self.lg_pass = QLineEdit(self.cfg.tv.lg_parola)
        self.lg_pass.setPlaceholderText("LG Passphrase (Developer Mode ekranında, ör. A1B2C3)")
        self.pair_addr = QLineEdit()
        self.pair_addr.setPlaceholderText("Eşleştirme penceresindeki adres:port (ana ekrandaki değil)")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("Kod")
        self.pair_code.setFixedWidth(100)
        self.tv_dot = Dot("off")
        self.tv_msg = label("", "muted", wrap=True)
        conn = QWidget()
        self.pair_row = QWidget()
        self.pair_row.setLayout(hbox(self.pair_addr, self.pair_code,
                                     button("Eşleştir", None, lambda: self.ctl.tv_pair(self.pair_addr.text().strip(),
                                                                                       self.pair_code.text().strip())),
                                     spacing=10))
        self.pair_toggle = QCheckBox("Gelişmiş: TV'de USB hata ayıklama yok, kablosuz eşleştirme kodu kullanacağım")
        self.pair_toggle.toggled.connect(lambda on: self.pair_row.setVisible(on and self.tv_brand.currentData() == "android"))
        conn.setLayout(vbox(hbox(self.tv_ip, self.tv_scan_btn, self.tv_found, self.tv_conn_btn, spacing=10),
                            self.lg_pass, self.pair_toggle, self.pair_row,
                            hbox(self.tv_dot, self.tv_msg, 1, spacing=6), spacing=8))
        self.tv_conn = conn
        from ..tv import local_ip
        try:
            pc_ip = local_ip()
        except OSError:
            pc_ip = "ağ bağlantısı yok"
        self.pc_ip = label(f"Bu bilgisayarın IP'si: <b>{pc_ip}</b> (Host PC IP'ye bunu yaz)", "h3")
        self.pc_ip.setTextFormat(Qt.RichText)
        self.tv_guide = Guide()
        lay.addWidget(self.tv_guide, 1)
        self.tv_brand.currentIndexChanged.connect(self._tv_brand_changed)
        self._tv_brand_changed()
        return w

    def _tv_brand_changed(self, *_a) -> None:  # noqa: ANN002
        brand = self.tv_brand.currentData()
        self.cfg.tv.marka = brand
        self.lg_pass.setVisible(brand == "lg")
        self.pair_toggle.setVisible(brand == "android")
        self.pair_row.setVisible(brand == "android" and self.pair_toggle.isChecked())
        self.tv_guide.index = 0
        self.tv_guide.set_steps(rehber.TV_STEPS[brand], {"baglan": self.tv_conn, "pcip": self.pc_ip})

    def _translation(self) -> QWidget:
        w, lay = self._page("Çeviri",
                            "Ekran kartındaki yerel model her zaman çalışır: internetsiz, ücretsiz ve anında. Üstüne "
                            "isteğe bağlı bir yapay zekâ daha doğal Türkçe verir. Ücretsiz seçenekler de var; herkes "
                            "kendi anahtarını kullanır, kimse başkasının çevirisini ödemez.")
        c = self.cfg.ceviri
        card = Card(inner=True, margins=16)
        self.engine = QComboBox()
        for key, text in (("gemini", "Google Gemini · ücretsiz anahtar (önerilen ücretsiz seçenek)"),
                          ("claude", "Claude · en iyi kalite (ücretli, kendi Anthropic hesabın)"),
                          ("deepl", "DeepL · ücretsiz plan (ayda 500 bin karakter)"),
                          ("yerelai", "Yerel yapay zekâ · Ollama / LM Studio (ücretsiz, internetsiz)"),
                          ("yok", "Şimdilik yok · yalnız yerel model")):
            self.engine.addItem(text, key)
        self.engine.setCurrentIndex(max(0, self.engine.findData(c.kalite if c.kalite != "claude" or c.claude_anahtar
                                                                else "gemini")))
        card.add(label("Kalite katmanı", "h3"))
        card.add(self.engine)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key_btn = button("Anahtar al", None, self._open_key_page)
        self.key_row = QWidget()
        self.key_row.setLayout(hbox(self.key, self.key_btn, spacing=8))
        card.add(self.key_row)
        self.model = QComboBox()
        self.model.addItem("Claude Opus 5.5 · en iyi kalite (hızlı mod açık)", "claude-opus-5-5")
        self.model.addItem("Claude Haiku 5.5 · daha hızlı ve ucuz", "claude-haiku-5-5")
        self.model.setCurrentIndex(max(0, self.model.findData(c.claude_model)))
        card.add(self.model)
        self.lai_url = QLineEdit(c.yerelai_adres)
        self.lai_model = QLineEdit(c.yerelai_model)
        self.lai_box = QWidget()
        self.lai_box.setLayout(vbox(hbox(self.lai_url, self.lai_model, spacing=8),
                                    hbox(button("Ollama'yı indir", None, lambda: webbrowser.open(rehber.OLLAMA_DOWNLOAD)),
                                         label("Kurduktan sonra komut satırında <b>ollama pull qwen2.5:7b</b> yaz.",
                                               "faint", wrap=True), spacing=10), spacing=8))
        card.add(self.lai_box)
        self.engine_hint = label("", "faint", wrap=True)
        self.engine_hint.setTextFormat(Qt.RichText)
        card.add(self.engine_hint)
        self.engine.currentIndexChanged.connect(self._engine_changed)
        self._engine_changed()
        lay.addWidget(card)
        self.eng_dot = Dot("warn")
        self.eng_msg = label("Motorlar hazırlanıyor...", "muted", wrap=True)
        lay.addLayout(hbox(self.eng_dot, self.eng_msg, 1, spacing=6))
        self.test_btn = button("Kaydet ve dene", None, self._test)
        self.test_out = label("", "muted", wrap=True)
        lay.addLayout(hbox(self.test_btn, None))
        lay.addWidget(self.test_out)
        lay.addStretch(1)
        if self.ctl.engine_info:
            self._on_engines(self.ctl.engine_info)
        return w

    def _done(self) -> QWidget:
        w, lay = self._page("Her şey hazır!",
                            "Oyunda İngilizce altyazıyı aç, chiaki-ng'de PS5'e bağlan ve ana ekranda başlat'a bas.")
        tips = Card(inner=True, margins=16, spacing=10)
        tips.add(feature("play", "Başlat", "Ana ekrandaki büyük düğme. Altyazı kasada, TV'de ve OBS'de birlikte görünür."))
        tips.add(feature("tv", "Discord yayını",
                         "Bilgisayarda ikinci bir Discord hesabıyla sesli kanala gir, sesini kapat ve TÜM EKRANI "
                         "paylaş. Sen telefondan ya da başka bir cihazdan kendi hesabınla konuş (kulaklıkla)."))
        tips.add(feature("regions", "GTA 6 çıkınca",
                         "Okuma alanları sayfasında Görüntü al'a bas, kutuları gerçek altyazının üstüne çek."))
        lay.addWidget(tips)
        self.auto_cb = QCheckBox("Her şey kendiliğinden olsun: bilgisayar açılınca uygulama açılsın, PS5'i açınca "
                                 "chiaki bağlansın ve çeviri başlasın")
        self.auto_cb.setChecked(True)
        lay.addWidget(self.auto_cb)
        qr = QrCode(110)
        qr.setData(self.ctl.server_url("kumanda"))
        lay.addLayout(hbox(qr, vbox(label("Telefon kumandası", "h3"),
                                    label("TV'den oynarken telefonla okut: Ekranı çevir ve Duraklat düğmeleri burada.",
                                          "muted", wrap=True),
                                    label(self.ctl.server_url("kumanda").replace("http://", ""), "faint"), None),
                           spacing=16))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ gezinme
    def _guide(self, i: int) -> Guide | None:
        return {P_PS5: getattr(self, "ps5_guide", None), P_TV: getattr(self, "tv_guide", None)}.get(i)

    def _skipped(self, i: int) -> bool:
        return i == P_TV and self.where == "monitor"

    def _go(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        self.stepper.setCurrent(i)
        self.back.setVisible(i > 0)
        self.skip.setVisible(i in (P_PS5, P_TV, P_TRANSLATION))
        self._update_next()

    def _update_next(self) -> None:
        i = self.stack.currentIndex()
        if i == P_PS5 and hasattr(self, "chiaki_state"):
            self._refresh_chiaki()
        g = self._guide(i)
        if g is not None and g.can_next():
            self.next.setText("Sonraki adım")
        else:
            self.next.setText({P_WELCOME: "Başlayalım", P_DONE: "Bitir"}.get(i, "Devam"))

    def _back(self) -> None:
        i = self.stack.currentIndex()
        g = self._guide(i)
        if g is not None and g.can_back():
            g.back()
            self._update_next()
            return
        j = i - 1
        while j > 0 and self._skipped(j):
            j -= 1
        self._go(max(0, j))

    def _next(self, skip_step: bool = False) -> None:
        i = self.stack.currentIndex()
        g = self._guide(i)
        if g is not None and g.can_next() and self.sender() is not self.skip:
            g.next()
            self._update_next()
            return
        if i == P_TV:
            self.cfg.tv.ip = self.tv_ip.text().strip()
        if i == P_TRANSLATION:
            self._save_translation()
        if i == P_DONE:
            if self.where == "monitor":
                self.cfg.tv.ip = ""
            o = self.cfg.otomatik
            on = self.auto_cb.isChecked()
            o.windows_ile_baslat = on
            o.chiaki_gorunce_baslat = True
            o.ps5_acilinca_baglan = on
            self.ctl.apply_config(self.cfg)
            if on and not (o.ps5_adi and o.ps5_ip):
                self.ctl.find_ps5(save=True)
            self.accept()
            return
        j = i + 1
        while self._skipped(j):
            j += 1
        self._go(j)

    # ------------------------------------------------------------------ PS5
    def _refresh_chiaki(self) -> None:
        from ..app import find_chiaki
        path = find_chiaki(self.cfg.kaynak.chiaki_yolu)
        self.chiaki_state.setText(f"chiaki-ng bulundu: {path}" if path else
                                  "chiaki-ng henüz bulunamadı. Kurunca bu satır yeşil olur.")
        self.chiaki_dot.setState("ok" if path else "off")
        self.chiaki_btn_open.setEnabled(bool(path))

    def _browse_chiaki(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "chiaki-ng programını seç", "", "Program (*.exe);;Tümü (*)")
        if path:
            self.cfg.kaynak.chiaki_yolu = path
            self.ctl.apply_config(self.cfg)
            self.cfg = self.ctl.edit_config()
            self._refresh_chiaki()

    def _open_chiaki(self) -> None:
        self.ctl.launch_chiaki()

    def _on_source(self, ok: bool, title: str) -> None:
        if not hasattr(self, "conn_dot"):
            return
        self.conn_dot.setState("ok" if ok else "off")
        self.conn_state.setText(f"✓ chiaki-ng penceresi bulundu: {title}" if ok else
                                "chiaki-ng'de PS5'e bağlanınca burası yeşil olur.")

    # ------------------------------------------------------------------ TV
    def _scan(self) -> None:
        self.cfg.tv.marka = self.tv_brand.currentData()      # tarama markanın portuna göre yapılır
        self.ctl.apply_config(self.cfg)
        self.cfg = self.ctl.edit_config()
        self.tv_scan_btn.setEnabled(False)
        self.tv_scan_btn.setText("Aranıyor...")
        self.ctl.tv_scan()

    def _on_found(self, found: list) -> None:
        self.tv_scan_btn.setEnabled(True)
        self.tv_scan_btn.setText("Ağda ara")
        self.tv_found.clear()
        for host, kind in found:
            self.tv_found.addItem(f"{host} ({kind})", host)
        self.tv_found.setVisible(bool(found))
        self.tv_msg.setText(f"{len(found)} cihaz bulundu." if found else
                            "TV bulunamadı. Geliştirici seçeneklerini kontrol et ya da IP'yi elle yaz.")

    def _tv_connect(self) -> None:
        ip = self.tv_ip.text().strip()
        if not ip:
            self.tv_msg.setText("TV'nin IP adresini yaz ya da Ağda ara'ya bas.")
            return
        self.cfg.tv.ip = ip
        self.cfg.tv.marka = self.tv_brand.currentData()
        self.cfg.tv.lg_parola = self.lg_pass.text().strip()
        self.ctl.apply_config(self.cfg)
        self.cfg = self.ctl.edit_config()
        self.ctl.tv_connect(ip, force_install=True)

    def _on_tv(self, state: str, msg: str) -> None:
        if hasattr(self, "tv_dot"):
            self.tv_dot.setState({"bagli": "ok", "baglaniyor": "warn", "onay": "info", "hata": "bad"}.get(state, "off"))
            self.tv_msg.setText(msg)

    # ------------------------------------------------------------------ çeviri
    ENGINE_HINTS = {
        "gemini": "Google hesabınla aistudio.google.com'a gir, <b>Create API key</b>'e bas, anahtarı buraya yapıştır. "
                  "Ücretsiz kotası oyun için genelde yeter.",
        "claude": "console.anthropic.com'da <b>Create Key</b>'e bas. Kullandıkça Anthropic hesabından ücretlenir; "
                  "önbellekteki ve paketteki satırlar ücretsizdir.",
        "deepl": "deepl.com'da <b>DeepL API Free</b> planına üye ol (kart ister, ücret almaz); anahtarın sonu <b>:fx</b> "
                 "ile biter.",
        "yerelai": "Bilgisayarında çalışan yapay zekâ: anahtar, kota ve ücret yok. Ekran kartı varsa bir satır 1-2 saniyede gelir.",
        "yok": "Yalnız yerel model çevirir: anında ve ücretsiz, argoda biraz daha zayıf. Sonra Çeviri sayfasından "
               "istediğin motoru ekleyebilirsin.",
    }

    def _key_field(self, eng: str) -> str:
        return {"claude": "claude_anahtar", "gemini": "gemini_anahtar", "deepl": "deepl_anahtar"}.get(eng, "")

    def _engine_changed(self) -> None:
        eng = self.engine.currentData()
        prev = getattr(self, "_eng_prev", None)
        if prev and self._key_field(prev):
            setattr(self.cfg.ceviri, self._key_field(prev), self.key.text().strip())
        self._eng_prev = eng
        field_name = self._key_field(eng)
        self.key_row.setVisible(bool(field_name))
        if field_name:
            self.key.setText(getattr(self.cfg.ceviri, field_name))
            self.key.setPlaceholderText({"claude": "Claude API anahtarı (sk-ant-...)", "gemini": "Gemini API anahtarı",
                                         "deepl": "DeepL API anahtarı (…:fx)"}[eng])
        self.model.setVisible(eng == "claude")
        self.lai_box.setVisible(eng == "yerelai")
        self.engine_hint.setText(self.ENGINE_HINTS[eng])

    def _open_key_page(self) -> None:
        webbrowser.open({"claude": rehber.CLAUDE_KEYS, "gemini": rehber.GEMINI_KEYS,
                         "deepl": rehber.DEEPL_SIGNUP}.get(self.engine.currentData(), rehber.GEMINI_KEYS))

    def _save_translation(self) -> None:
        c = self.cfg.ceviri
        eng = self.engine.currentData()
        if self._key_field(eng):
            setattr(c, self._key_field(eng), self.key.text().strip())
        c.claude_model = self.model.currentData()
        c.claude_hizli_mod = c.claude_model == "claude-opus-5-5"
        c.yerelai_adres = self.lai_url.text().strip() or "http://localhost:11434/v1"
        c.yerelai_model = self.lai_model.text().strip() or "qwen2.5:7b"
        c.kalite = eng

    def _test(self) -> None:
        self._save_translation()
        self.ctl.apply_config(self.cfg)
        self.cfg = self.ctl.edit_config()
        self.test_out.setText("Motorlar yeniden hazırlanıyor, sonra denenecek...")
        self._pending_test = True

    def _on_engines(self, info: dict) -> None:
        if not hasattr(self, "eng_msg"):
            return
        hizli = info.get("hizli") or "yok"
        kalite = info.get("kalite") or "kapalı"
        self.eng_dot.setState("ok")
        self.eng_msg.setText(f"OCR: {info.get('ocr')} · Yerel çeviri: {hizli} · Yapay zeka: {kalite}")
        if getattr(self, "_pending_test", False):
            self._pending_test = False
            self._results = []
            self.ctl.test_translation("You think you can just walk in here and take what's mine, man?")

    def _on_test(self, r) -> None:  # noqa: ANN001
        if not hasattr(self, "_results"):
            self._results = []
        self._results.append(f"<b>{r.text}</b> <span style='color:{T.FAINT}'>· {r.source} · {r.ms:.0f} ms</span>")
        self.test_out.setText("<br>".join(self._results))
