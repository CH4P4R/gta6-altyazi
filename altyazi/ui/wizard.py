"""İlk açılış kurulum sihirbazı."""

from __future__ import annotations

import sys

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import rehber
from ..app import CHIAKI_DOWNLOAD, AppController
from . import theme as T
from .guide import REHBER, Guide
from .parcalar import Backdrop, HelpFab, IconTile, PagerDots, SubtitlePreview
from .widgets import (Card, Dot, IconBadge, Logo, PreviewArt, QrCode, Stepper, button, hbox, label,
                      scroll_page, vbox)

STEPS = ["Hoş geldin", "Nerede oynuyorsun?", "PS5 bağlantısı", "Televizyon", "Çeviri", "Hazır"]
P_WELCOME, P_WHERE, P_PS5, P_TV, P_TRANSLATION, P_DONE = range(6)
__all__ = ["Wizard", "STEPS", "REHBER", "P_WELCOME", "P_WHERE", "P_PS5", "P_TV", "P_TRANSLATION", "P_DONE"]
PSN_SIGNUP = rehber.PSN_SIGNUP


# Sihirbaz uygulamanın geri kalanından daha büyük ve iddialı yazılarla: ilk izlenim burada.
WIZ_QSS = f"""
QWidget {{ font-size: 12pt; }}
#display {{ font-size: 30pt; font-weight: 800; }}
#hero {{ font-size: 34pt; font-weight: 800; }}
#lead {{ font-size: 13.5pt; color: {T.MUTED}; }}
#h1 {{ font-size: 24pt; font-weight: 800; }}
#h2 {{ font-size: 16.5pt; font-weight: 700; }}
#h3 {{ font-size: 13pt; font-weight: 700; }}
#muted {{ color: {T.MUTED}; font-size: 12pt; }}
#faint {{ color: {T.FAINT}; font-size: 11pt; }}
#tag {{ color: {T.A2}; font-size: 10pt; font-weight: 800; letter-spacing: 1px; }}
#badge {{ color: white; font-size: 9.5pt; font-weight: 800; letter-spacing: 1px; padding: 4px 10px;
          border-radius: 11px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {T.A1}, stop:1 {T.A2}); }}
QPushButton {{ font-size: 12.5pt; padding: 12px 20px; border-radius: 12px; }}
QPushButton#primary {{ font-size: 13.5pt; padding: 14px 26px; }}
QPushButton#ghost {{ font-size: 12.5pt; padding: 10px 14px; }}
QLineEdit, QComboBox, QSpinBox {{ font-size: 12.5pt; padding: 11px 14px; border-radius: 11px; }}
QCheckBox {{ font-size: 12.5pt; spacing: 12px; }}
QCheckBox::indicator {{ width: 22px; height: 22px; border-radius: 6px; }}
QPushButton#choice {{ text-align: left; padding: 0; border-radius: 18px; background: {T.SURFACE};
                      border: 2px solid {T.BORDER}; }}
QPushButton#choice:hover {{ border-color: {T.BORDER_HI}; background: {T.SURFACE2}; }}
QPushButton#choice:checked {{ border-color: {T.A1}; background: {T.SURFACE2}; }}
QPushButton#seg {{ padding: 10px 18px; border-radius: 10px; background: transparent; border: 1px solid {T.BORDER_HI};
                   color: {T.MUTED}; }}
QPushButton#seg:checked {{ color: white; border: 0;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {T.A1}, stop:1 {T.A2}); }}
"""


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
    return hbox(vbox(IconBadge(icon, 44), None), vbox(label(title, "h3"), label(text, "muted", wrap=True), spacing=3),
                spacing=16)


def tile(icon: str, title: str, text: str) -> Card:
    """Hoş geldin sayfasındaki büyük özellik kartı."""
    c = Card(margins=20, spacing=10)
    c.setMinimumHeight(190)
    c.add(IconBadge(icon, 52))
    c.add(label(title, "h2"))
    t = label(text, "muted", wrap=True)
    c.add(t)
    c.layout().addStretch(1)
    return c


class ChoiceCard(QPushButton):
    """'Nerede oynuyorsun?' seçeneği: büyük ikon, başlık, açıklama, önerilen etiketi, seçilince onay işareti."""

    def __init__(self, icon: str, title: str, text: str, badge: str = ""):
        super().__init__()
        self.setObjectName("choice")
        self.setCheckable(True)
        self.setMinimumHeight(140)
        self.setCursor(Qt.PointingHandCursor)
        self.icon = IconBadge(icon, 60, active=False)
        t1, t2 = label(title, "h2"), label(text, "muted", wrap=True)
        heads = [t1]
        if badge:
            b = label(badge, "badge")
            b.setFixedHeight(26)
            b.setAlignment(Qt.AlignCenter)
            heads += [b]
        for w in (t1, t2, *heads):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            w.setStyleSheet(w.styleSheet() + "background: transparent;" if w.objectName() != "badge" else w.styleSheet())
        self.tick = IconBadge("check", 30)
        self.tick.setVisible(False)
        text_box = vbox(hbox(*heads, None, spacing=10), t2, spacing=6)
        inner = hbox(self.icon, text_box, 1, self.tick, spacing=18)
        inner.setContentsMargins(22, 18, 22, 18)
        self.setLayout(inner)
        self.toggled.connect(self._toggled)

    def _toggled(self, on: bool) -> None:
        self.icon.setActive(on)
        self.tick.setVisible(on)


def check_row(title: str, text: str, *buttons) -> Card:  # noqa: ANN002
    c = Card(inner=True, margins=14, spacing=4)
    dot = Dot("off")
    c.dot = dot
    head = hbox(dot, label(title, "h3"), None, *buttons, spacing=8)
    c.add(head)
    t = label(text, "muted", wrap=True)
    c.add(t)
    return c


CHOICES = [("tv", "ps", "TV'de oynuyorum",
            "PS5 HDMI ile TV'de, sen kendi kolunla oynarsın. Bilgisayar arka planda izler; Türkçe TV'de, oyunun "
            "üstünde çıkar. chiaki-ng gerekmez.", "ÖNERİLEN"),
           ("monitor", "monitor", "Bilgisayar monitöründe",
            "chiaki-ng ile PS5'i bilgisayarda oynarsın. Türkçe, chiaki penceresinin üstünde çıkar.", ""),
           ("ikisi", "swap", "Bazen TV'de, bazen monitörde",
            "İkisini de kurarız; o gün hangisinde oynuyorsan o çalışır.", "")]


class Wizard(QDialog):
    def __init__(self, ctl: AppController, parent=None):  # noqa: ANN001
        super().__init__(parent)
        self.ctl = ctl
        self.cfg = ctl.edit_config()
        self.setWindowTitle("GTA6 Altyazı · Kurulum")
        self.setModal(True)
        self.setStyleSheet(WIZ_QSS)
        self.setMinimumSize(1040, 700)
        screen = self.screen().availableGeometry() if self.screen() else None
        w, h = 1260, 860
        if screen is not None:
            w, h = min(w, screen.width() - 40), min(h, screen.height() - 40)
        self.resize(max(w, 1040), max(h, 700))
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = Hero()
        side.setFixedWidth(300)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(26, 28, 16, 24)
        sl.addWidget(Logo())
        self.stepper = Stepper(STEPS, big=True)
        sl.addWidget(self.stepper, 1)
        sl.addWidget(label("Ayarları sonra istediğin zaman\nAyarlar sayfasından değiştirebilirsin.", "faint"))
        root.addWidget(side)

        right = Backdrop()                        # Nino gibi yumuşak ışıltılı zemin (bizim renklerle)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(48, 40, 48, 30)
        rl.setSpacing(18)
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        self.back = button("Geri", "ghost", self._back)
        self.skip = button("Bu adımı atla", "ghost", self._next)
        self.next = button("Başlayalım", "primary", self._next)
        self.next.setMinimumWidth(210)
        self.dots = PagerDots(len(STEPS))
        rl.addLayout(hbox(self.back, None, self.dots, None, self.skip, self.next, spacing=10))
        root.addWidget(right, 1)
        self.fab = HelpFab(right)
        self.fab.clicked.connect(self._ask)
        right.resizeEvent = lambda e: (QFrame.resizeEvent(right, e), self.fab.move(right.width() - 86,
                                                                                   right.height() - 150))

        self.where = self.cfg.kaynak.oyun_yeri if self.cfg.kaynak.oyun_yeri in ("monitor", "tv", "ikisi") else "tv"
        for builder in (self._welcome, self._where, self._ps5, self._tv, self._translation, self._done):
            self.stack.addWidget(builder())
        ctl.sourceStatus.connect(self._on_source)
        ctl.tvStatus.connect(self._on_tv)
        ctl.tvFound.connect(self._on_found)
        ctl.testResult.connect(self._on_test)
        ctl.enginesReady.connect(self._on_engines)
        self._go(0)

    # ------------------------------------------------------------------ sayfalar
    PAGE_ICONS = {"Nerede oynuyorsun?": "swap", "PS5 bağlantısı": "ps", "Televizyon": "tv", "Çeviri": "translate"}

    def _ask(self) -> None:
        from .yardim import AskDialog
        if getattr(self, "_ask_dlg", None) is None:
            self._ask_dlg = AskDialog(self.ctl, self)
        self._ask_dlg.show()
        self._ask_dlg.raise_()

    def _page(self, title: str, subtitle: str, icon: str | None = None) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        t = label(title, "display")
        t.setWordWrap(True)
        icon = icon or self.PAGE_ICONS.get(title, "check")
        w.icon = IconTile(icon, 58)                 # Nino: başlığın yanında degrade ikon kutusu
        lay.addLayout(hbox(w.icon, t, 1, spacing=18))
        sub = label(subtitle, "lead", wrap=True)
        sub.setTextFormat(Qt.RichText)
        lay.addWidget(sub)
        w.subtitle = sub
        w.title = t
        lay.addSpacing(8)
        return w, lay

    def _welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(label("GTA 6 · CANLI TÜRKÇE ÇEVİRİ", "tag"))
        head = label(f"Oyun İngilizce,<br><span style='color:{T.A1}'>sen Türkçe oyna.</span>", "hero")
        head.setTextFormat(Qt.RichText)
        lay.addWidget(head)
        lay.addWidget(label("Ekrandaki İngilizce yazıları anında okur, Türkçesini oyunun üstüne yazar. Kurulum 5 dakika.",
                            "lead", wrap=True))
        lay.addSpacing(4)
        tiles = QHBoxLayout()
        tiles.setSpacing(16)
        for icon, title, text in (("translate", "Her yazı Türkçe", "Diyaloglar, yardım kutuları, bildirimler, "
                                   "telefon ve menüler."),
                                  ("tv", "TV'de oyunun üstünde", "Sen TV'de oynarsın; Türkçe, İngilizcenin tam "
                                   "yerinde çıkar."),
                                  ("bolt", "Bekletmez", "İlk çeviri anında gelir, yapay zekâ hemen ardından "
                                   "cilalar.")):
            tiles.addWidget(tile(icon, title, text), 1)
        lay.addLayout(tiles)
        lay.addWidget(PreviewArt(), 1)
        return w

    def _where(self) -> QWidget:
        w, lay = self._page("Nerede oynuyorsun?", "Kurulumu buna göre anlatacağım; sonra Ayarlar'dan değiştirebilirsin.")
        self.where_group = QButtonGroup(self)
        self.where_group.setExclusive(True)
        self.choice_cards = {}
        for key, icon, title, text, badge in CHOICES:
            b = ChoiceCard(icon, title, text, badge)
            b.setChecked(key == self.where)
            b.clicked.connect(lambda _=False, k=key: self._set_where(k))
            self.where_group.addButton(b)
            self.choice_cards[key] = b
            lay.addWidget(b)
        lay.addWidget(label("TV'de oynarken bilgisayar ikinci bir PSN hesabı kullanır (kolun kopmasın diye). "
                            "Hepsini adım adım göstereceğim.", "faint", wrap=True))
        lay.addStretch(1)
        return w

    def _set_where(self, key: str) -> None:
        self.where = key
        self.cfg.kaynak.oyun_yeri = key
        if key == "monitor" and self.cfg.kaynak.tur == "remoteplay":
            self.cfg.kaynak.tur = "pencere"
        self.ps5_guide.set_steps(self._ps5_steps(), self._ps5_extras())
        self.ps5_guide.show_step(0)
        if hasattr(self, "ps5_stack"):
            self._ps5_mode("chiaki" if key == "monitor" else "rp")

    def _ps5(self) -> QWidget:
        w, lay = self._page("PS5 bağlantısı", "")
        self.ps5_page = w
        # Monitörde ve TV'de ikisini birden kuranlar için iki sekme
        self.seg_rp = button("TV için: arka planda bağlan", "seg", lambda: self._ps5_mode("rp"))
        self.seg_chiaki = button("Monitör için: chiaki-ng", "seg", lambda: self._ps5_mode("chiaki"))
        for b in (self.seg_rp, self.seg_chiaki):
            b.setCheckable(True)
        self.seg_row = QWidget()
        self.seg_row.setLayout(hbox(self.seg_rp, self.seg_chiaki, None, spacing=8))
        lay.addWidget(self.seg_row)
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
        self.ps5_stack = QStackedWidget()
        # TV: yerleşik Remote Play (chiaki penceresi gerekmez)
        from .ps5_dialog import Ps5Panel
        self.rp_panel = Ps5Panel(self.ctl, intro=False)
        rp_page = QWidget()
        rpl = QVBoxLayout(rp_page)
        rpl.setContentsMargins(0, 0, 8, 0)
        rpl.addWidget(self.rp_panel)
        rpl.addStretch(1)
        self.ps5_stack.addWidget(scroll_page(rp_page))
        # Monitör: chiaki-ng resimli rehberi
        self.ps5_guide = Guide()
        self.ps5_stack.addWidget(self.ps5_guide)
        lay.addWidget(self.ps5_stack, 1)
        self.ps5_guide.set_steps(self._ps5_steps(), self._ps5_extras())
        self.ctl.ps5Paired.connect(lambda ok, _m: ok and self._sync_rp())
        self._refresh_chiaki()
        self._ps5_mode("chiaki" if self.where == "monitor" else "rp")
        return w

    def _ps5_mode(self, mode: str) -> None:
        self._ps5_view = mode
        self.seg_row.setVisible(self.where == "ikisi")
        self.seg_rp.setChecked(mode == "rp")
        self.seg_chiaki.setChecked(mode == "chiaki")
        self.ps5_stack.setCurrentIndex(0 if mode == "rp" else 1)
        if mode == "rp":
            self.ps5_page.subtitle.setText("Bilgisayar PS5'e arka planda <b>ikinci PSN hesabıyla</b> bağlanıp yalnız "
                                           "altyazıyı okur; sen TV'de kendi hesabınla oynarsın. Bir kez yaparsın, "
                                           "sonra hep kendiliğinden çalışır.")
        else:
            self.ps5_page.subtitle.setText("chiaki-ng, PS5'in görüntüsünü bilgisayara getiren ücretsiz programdır. "
                                           "Adımları sırayla yap; her adımda neye basacağın resimde işaretli.")
        if hasattr(self, "stack"):
            self._update_next()

    def _sync_rp(self) -> None:
        """Eşleme ayarlara yazıldı; sihirbazın kendi ayar kopyası Bitir'de bunu geri silmesin."""
        import copy
        self.cfg.ps5 = copy.deepcopy(self.ctl.cfg.ps5)
        if self.ctl.ps5_paired():
            self.cfg.kaynak.tur = "remoteplay"
            self.cfg.kaynak.oyun_yeri = self.where if self.where in ("tv", "ikisi") else "tv"

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
        # Deneyelim (Nino): TV bağlanınca örnek altyazı gider, "TV'de görüyor musun?" diye sorulur
        self.try_box = Card(inner=True, margins=16, spacing=10)
        self.try_box.add(label("Deneyelim", "h2"))
        self.try_box.add(label("TV'ne örnek bir altyazı gönderildi. Ekranın altında, oyunun üstünde görünmeli.", "muted",
                               wrap=True))
        demo = SubtitlePreview("Bu bir deneme altyazısı. Oyunun üstünde görüyor musun?", "This is a test subtitle.")
        demo.setMinimumHeight(150)
        demo.setMaximumHeight(190)
        self.try_box.add(demo)
        self.try_yes = button("Evet, görüyorum", "primary", self._try_yes)
        self.try_no = button("Hayır", None, self._try_no)
        self.try_box.add(hbox(label("TV'de görüyor musun?", "h3"), None, self.try_no, self.try_yes,
                              button("↻ Tekrar gönder", "ghost", self.ctl.tv_test), spacing=10))
        self.try_msg = label("", "muted", wrap=True)
        self.try_box.add(self.try_msg)
        self.try_box.hide()
        conn.setLayout(vbox(hbox(self.tv_ip, self.tv_scan_btn, self.tv_found, self.tv_conn_btn, spacing=10),
                            self.lg_pass, self.pair_toggle, self.pair_row,
                            hbox(self.tv_dot, self.tv_msg, 1, spacing=6), self.try_box, spacing=8))
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
        w, lay = self._page("Her şey hazır! 🎉", "")
        self.done_page = w
        self.done_tips = Card(margins=20, spacing=14)
        lay.addWidget(self.done_tips)
        self._done_items: list = []
        self.auto_cb = QCheckBox()
        self.auto_cb.setChecked(True)
        lay.addWidget(self.auto_cb)
        qr = QrCode(120)
        qr.setData(self.ctl.server_url("kumanda"))
        lay.addLayout(hbox(qr, vbox(label("Telefon kumandası", "h3"),
                                    label("TV'den oynarken telefonla okut: Ekranı çevir ve Duraklat düğmeleri burada.",
                                          "muted", wrap=True),
                                    label(self.ctl.server_url("kumanda").replace("http://", ""), "faint"), None),
                           spacing=18))
        lay.addStretch(1)
        self._fill_done()
        return w

    def _fill_done(self) -> None:
        """Son sayfa seçime göre: TV'de PS5 kendiliğinden bağlanır, monitörde chiaki ile."""
        tv = self.where in ("tv", "ikisi")
        self.done_page.subtitle.setText(
            "PS5'i aç, kolu açınca <b>kendi hesabını</b> seç ve oyunda İngilizce altyazıyı aç. Çeviri kendiliğinden "
            "başlar, Türkçe TV'de çıkar." if tv else
            "Oyunda İngilizce altyazıyı aç, chiaki-ng'de PS5'e bağlan ve ana ekranda Başlat'a bas.")
        lay = self.done_tips.layout()
        for item in self._done_items:
            lay.removeItem(item)
            while item.count():
                wdg = item.takeAt(0).widget()
                if wdg is not None:
                    wdg.deleteLater()
        tips = [("ps", "PS5 açılınca kendiliğinden", "Bilgisayar PS5'e arka planda bağlanır, çeviri başlar. PS5'i "
                 "kapatınca bekler, açınca yeniden bağlanır.")] if tv else \
            [("play", "Başlat", "Ana ekrandaki büyük düğme. Türkçe chiaki penceresinin üstünde çıkar.")]
        tips += [("translate", "Ekranın tamamını çevir", f"Telefon, menü, harita: {self.cfg.kisayol.tam_ekran.upper()} "
                  "ya da telefon kumandasındaki Ekranı çevir düğmesi."),
                 ("regions", "Altyazı kayık mı?", "Okuma alanları sayfasında Görüntü al'a bas, kutuları gerçek "
                  "altyazının üstüne çek.")]
        self._done_items = []
        for icon, title, text in tips:
            row = feature(icon, title, text)
            lay.addLayout(row)
            self._done_items.append(row)
        self.auto_cb.setText("Bilgisayar açılınca uygulama da açılsın; PS5 açılınca çeviri kendiliğinden başlasın"
                             if tv else "Her şey kendiliğinden olsun: bilgisayar açılınca uygulama açılsın, PS5'i "
                             "açınca chiaki bağlansın ve çeviri başlasın")

    # ------------------------------------------------------------------ gezinme
    def _guide(self, i: int) -> Guide | None:
        if i == P_PS5:
            return self.ps5_guide if getattr(self, "_ps5_view", "") == "chiaki" else None
        return {P_TV: getattr(self, "tv_guide", None)}.get(i)

    def _skipped(self, i: int) -> bool:
        return i == P_TV and self.where == "monitor"

    def _go(self, i: int) -> None:
        if i == P_DONE and hasattr(self, "done_page"):
            self._fill_done()
        self.stack.setCurrentIndex(i)
        self.stepper.setCurrent(i)
        if hasattr(self, "dots"):
            self.dots.setCurrent(i)
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
            self._sync_rp()
            o = self.cfg.otomatik
            on = self.auto_cb.isChecked()
            o.windows_ile_baslat = on
            o.chiaki_gorunce_baslat = True
            self.cfg.ps5.acilinca_baslat = on
            uses_chiaki = self.cfg.kaynak.tur != "remoteplay"
            o.ps5_acilinca_baglan = on and uses_chiaki
            self.ctl.apply_config(self.cfg)
            if on and uses_chiaki and not (o.ps5_adi and o.ps5_ip):
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
        path, _ = QFileDialog.getOpenFileName(self, "chiaki-ng programını seç", "/Applications" if sys.platform == "darwin" else "",
                                                  "Program (*.app *.exe);;Tümü (*)")
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
        if hasattr(self, "try_box") and state == "bagli" and self.try_box.isHidden():
            self.try_box.show()
            self.try_msg.setText("")
            self.ctl.tv_test()

    def _try_yes(self) -> None:
        self.try_msg.setText(f"<span style='color:{T.OK}'>✓ Harika, TV hazır.</span> Devam'a bas.")

    def _try_no(self) -> None:
        brand = self.tv_brand.currentData()
        tips = ["TV uygulaması açık mı? TV'de GTA6 Altyazı uygulamasını aç ve Tekrar gönder'e bas.",
                "Windows'ta güvenlik duvarı TV'yi engelliyor olabilir: programda Bağlantı › İzin ver."]
        if brand == "android":
            tips.insert(1, "Görüntü siyahsa ya da TV kendiliğinden PS5'in girişine geçiyorsa: Altyazı görünümü › "
                           "Android TV görüntü modu › Katman.")
        self.try_msg.setText("<br>".join(f"• {t}" for t in tips))

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
