"""İlk açılış kurulum sihirbazı."""

from __future__ import annotations

import sys

import webbrowser

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import rehber
from ..app import CHIAKI_DOWNLOAD, AppController
from . import theme as T
from .guide import REHBER, Guide
from .parcalar import Backdrop, HelpFab, IconTile, PagerDots, RadioCard, RadioGroup, Segmented, SubtitlePreview
from .widgets import (Card, Dot, Icon, IconBadge, Logo, PreviewArt, QrCode, Stepper, button, draw_icon, hbox, label,
                      scroll_page, vbox)

STEPS = ["Hoş geldin", "Nerede oynuyorsun?", "PS5 bağlantısı", "Televizyon", "Çeviri", "Hazır"]
P_WELCOME, P_WHERE, P_PS5, P_TV, P_TRANSLATION, P_DONE = range(6)
__all__ = ["Wizard", "STEPS", "REHBER", "P_WELCOME", "P_WHERE", "P_PS5", "P_TV", "P_TRANSLATION", "P_DONE"]
PSN_SIGNUP = rehber.PSN_SIGNUP


# Sihirbaz uygulamanın geri kalanından daha büyük ve iddialı yazılarla: ilk izlenim burada.
def wiz_qss() -> str:
    return f"""
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

# Hoş geldin: kuruluma başlamadan önce elde olması gerekenler (Nino'daki "İhtiyacınız olanlar")
NEEDS = [("ps", "PS5", "Bu bilgisayarla aynı Wi-Fi ağında"),
         ("tv", "Akıllı TV", "Android TV, Google TV, LG ya da Samsung"),
         ("user", "İkinci PSN hesabı", "Ücretsiz, 2 dakikada açılır")]

# Televizyon: önce TV türü seçilir, sonra o markanın resimli adımları gelir
TV_KINDS = [("android", "tv", "Android TV / Google TV",
             "TCL, iFFALCON, Sony, Philips, Vestel, Arçelik, Beko, Grundig ve diğer Android TV'ler."),
            ("lgsam", "tv", "LG ya da Samsung", "LG webOS ve Samsung Tizen TV'ler."),
            ("yok", "monitor", "TV'm yok, bu bilgisayarın ekranında göster",
             "Oyunu bilgisayarda Remote Play ile oynarsın; altyazı oyun penceresinin üstünde görünür. TV'yi sonra da "
             "bağlayabilirsin.")]
TV_NAMES = {"android": "Android TV / Google TV", "lg": "LG (webOS)", "samsung": "Samsung (Tizen)"}

ENGINE_NAMES = {"gemini": "Gemini", "claude": "Claude", "deepl": "DeepL", "yerelai": "Yerel yapay zekâ"}
TEST_LINE = "Get in the car, we're leaving right now!"


def draw_glyph(p: QPainter, name: str, r: QRectF, color: QColor, width: float) -> None:
    """draw_icon'da olmayan iki ikon (kişi, kilit); gerisi draw_icon'a gider."""
    if name not in ("user", "lock"):
        draw_icon(p, name, r, color, width)
        return
    p.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    if name == "user":                                   # baş ve omuzlar
        p.drawEllipse(QRectF(x + w * .32, y + h * .08, w * .36, h * .36))
        p.drawArc(QRectF(x + w * .12, y + h * .54, w * .76, h * .76), 0, 180 * 16)
    else:                                                # asma kilit
        p.drawRoundedRect(QRectF(x + w * .2, y + h * .44, w * .6, h * .46), 2, 2)
        p.drawArc(QRectF(x + w * .32, y + h * .1, w * .36, h * .6), 0, 180 * 16)
        for sx in (x + w * .32, x + w * .68):
            p.drawLine(QPointF(sx, y + h * .4), QPointF(sx, y + h * .44))
    p.restore()


class GlyphTile(IconTile):
    """IconTile; draw_icon'da olmayan 'user' ve 'lock' ikonlarını da çizer."""

    def paintEvent(self, e) -> None:  # noqa: ANN001, N802
        super().paintEvent(e)
        if self.icon in ("user", "lock"):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            r = QRectF(1, 1, self.width() - 2, self.height() - 2)
            m = r.width() * 0.25
            draw_glyph(p, self.icon, r.adjusted(m, m, -m, -m), QColor("white"), max(2.0, r.width() / 20))


class Glyph(Icon):
    """Küçük çizgi ikon (Icon gibi), kilit ve kişi dahil."""

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_glyph(p, self.name, QRectF(self.rect()).adjusted(1, 1, -1, -1), self.color, 1.6)


def need_card(icon: str, title: str, text: str) -> Card:
    """Hoş geldin sayfasındaki 'İhtiyacınız olanlar' kartı: ikon kutusu, kalın başlık, soluk açıklama."""
    c = Card(margins=16, spacing=0)
    row = QHBoxLayout()
    row.setSpacing(14)
    row.addWidget(GlyphTile(icon, 42, glow=False), 0, Qt.AlignTop)
    c.title = label(title, "h3")
    c.sub = label(text, "muted", wrap=True)
    c.sub.setStyleSheet("font-size: 11pt;")
    row.addLayout(vbox(c.title, c.sub, None, spacing=3), 1)
    c.add(row)
    return c


def step_num(n: int) -> QWidget:
    """Numaralı adımın degrade yuvarlağı (Nino'daki 1-2-3)."""
    b = label(str(n))
    b.setFixedSize(28, 28)
    b.setAlignment(Qt.AlignCenter)
    b.setStyleSheet(f"color: white; font-size: 11pt; font-weight: 800; border-radius: 14px; background: "
                    f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {T.A1}, stop:1 {T.A2});")
    return b


class Wizard(QDialog):
    def __init__(self, ctl: AppController, parent=None):  # noqa: ANN001
        super().__init__(parent)
        self.ctl = ctl
        self.cfg = ctl.edit_config()
        self.setWindowTitle("GTA6 Altyazı · Kurulum")
        self.setModal(True)
        self.setStyleSheet(wiz_qss())
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
        self.demo_btn = button("▷  Deneme modu (konsol olmadan dene)", "ghost", self._demo,
                               "Kurulumu bitirmeden örnek görüntüyle her şeyi dene")
        self.demo_btn.setStyleSheet(f"color: {T.A2};")
        rl.addLayout(hbox(self.back, self.demo_btn, None, self.dots, None, self.skip, self.next, spacing=10))
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
        lay.addWidget(label("Ekrandaki İngilizce yazıları anında okur, Türkçesini oyunun üstüne yazar: diyaloglar, "
                            "yardım kutuları, telefon mesajları ve menüler.", "lead", wrap=True))
        perks = QHBoxLayout()                     # eski büyük özellik kartlarının kısa hali
        perks.setSpacing(22)
        for icon, text in (("translate", "Her yazı Türkçe"), ("tv", "TV'de oyunun üstünde"),
                           ("bolt", "Bekletmez, anında gelir")):
            perks.addLayout(hbox(IconBadge(icon, 30), label(text, "muted"), spacing=9))
        perks.addStretch(1)
        lay.addLayout(perks)
        lay.addSpacing(6)
        clock = Icon("history", 18, T.MUTED)
        self.welcome_time = label("Kurulum yaklaşık 5 dakika sürer.", "muted")
        lay.addLayout(hbox(label("İHTİYACINIZ OLANLAR", "tag"), None, clock, self.welcome_time, spacing=8))
        needs = QHBoxLayout()
        needs.setSpacing(14)
        self.need_cards = []
        for icon, title, text in NEEDS:
            c = need_card(icon, title, text)
            self.need_cards.append(c)
            needs.addWidget(c, 1)
        lay.addLayout(needs)
        mon = button("▭  Monitörde Remote Play ile oynuyorum", "link", lambda: self._quick_where("monitor"))
        cap = button("⏚  Capture Card'ım var", "link", lambda: self._quick_where("capture"))
        lay.addLayout(hbox(mon, None, cap, spacing=10))
        lay.addSpacing(2)
        art = PreviewArt()
        art.setMinimumHeight(150)
        lay.addWidget(art, 1)
        return scroll_page(w)                     # küçük pencerede kırpılmasın, kaydırılsın

    def _quick_where(self, kind: str) -> None:
        """Hoş geldin sayfasındaki kısayollar (Nino): monitörde oynayan ya da capture kartı olan."""
        if kind == "capture":
            self.cfg.kaynak.tur = "capture"
            self._set_where("monitor")
            self.cfg.kaynak.tur = "capture"
        else:
            self._set_where("monitor")
        self._go(P_WHERE)

    def _demo(self) -> None:
        """Deneme modu: ayarları kaydedip sihirbazı kapatır, örnek görüntüyle çeviriyi başlatır."""
        self.ctl.apply_config(self.cfg)
        self.accept()
        if self.ctl.state == "hazir":
            self.ctl.start_demo()
        else:
            self.ctl._notice("Motorlar hazırlanıyor; birkaç saniye sonra ana ekrandaki Deneme modu'na bas")

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
        if key in getattr(self, "choice_cards", {}):          # Televizyon sayfasından değiştiyse ilk seçim de güncellensin
            self.choice_cards[key].setChecked(True)
        self.ps5_guide.set_steps(self._ps5_steps(), self._ps5_extras())
        self.ps5_guide.show_step(0)
        if hasattr(self, "ps5_stack"):
            self._ps5_mode("chiaki" if key == "monitor" else "rp")
        if hasattr(self, "tv_kinds"):
            self._tv_sync_kind()

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

    TV_SUB_CHOOSE = ("Türkçe altyazıyı TV'de oyunun üstünde göstermek için TV'ye küçük bir uygulama kurulur; bunu "
                     "bilgisayar ağ üzerinden kendisi yapar. Önce hangi televizyonun olduğunu seç.")
    TV_SUB_GUIDE = ("TV'ye küçük bir uygulama kurulur; bunu bilgisayar ağ üzerinden kendisi yapar. Resimli adımları "
                    "sırayla izle.")

    def _tv(self) -> QWidget:
        w, lay = self._page("Televizyon", self.TV_SUB_CHOOSE)
        self.tv_page = w
        # Marka listesi asıl kaynak olarak kalır (gizli); kartlar yalnız bunun seçimini değiştirir
        self.tv_brand = QComboBox()
        for key, text in rehber.TV_BRANDS:
            self.tv_brand.addItem(text, key)
        self.tv_brand.setCurrentIndex(max(0, self.tv_brand.findData(self.cfg.tv.marka)))
        self.tv_brand.hide()
        self.tv_stack = QStackedWidget()
        # 1) TV türü seçimi (Nino gibi üç büyük kart)
        choose = QWidget()
        cl = QVBoxLayout(choose)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)
        self.tv_kinds = RadioGroup(self._tv_kind)
        self.tv_kind_cards: dict[str, RadioCard] = {}
        for kind, icon, title, text in TV_KINDS:
            card = RadioCard(title, text)
            card.title_l.setObjectName("h2")
            card.lay.setContentsMargins(22, 20, 22, 20)
            card.lay.itemAt(0).layout().insertWidget(1, GlyphTile(icon, 46, glow=False), 0, Qt.AlignTop)
            card.body_l.setContentsMargins(98, 2, 0, 0)
            self.tv_kinds.add(kind, card)
            self.tv_kind_cards[kind] = card
            cl.addWidget(card)
        self.tv_lgsam = Segmented([("lg", "LG"), ("samsung", "Samsung")],
                                  self.cfg.tv.marka if self.cfg.tv.marka in ("lg", "samsung") else "lg")
        self.tv_lgsam.setFixedWidth(260)
        self.tv_lgsam.changed.connect(lambda _v: self.tv_kinds.set("lgsam", user=True))
        self.tv_kind_cards["lgsam"].add(hbox(label("Markası:", "muted"), self.tv_lgsam, None, spacing=12))
        self.tv_none_msg = label("Tamam, TV adımını atlıyoruz. Devam'a bas; PS5 bağlantısı sayfasında bilgisayarda "
                                 "oynamak için gereken adımlar da var.", "faint", wrap=True)
        self.tv_kind_cards["yok"].add(self.tv_none_msg)
        cl.addStretch(1)
        self.tv_stack.addWidget(choose)
        # 2) seçilen markanın resimli adımları
        guide_page = QWidget()
        gl = QVBoxLayout(guide_page)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(10)
        self.tv_brand_lbl = label("", "h3")
        gl.addLayout(hbox(label("Televizyon:", "muted"), self.tv_brand_lbl, self.tv_brand, None,
                          button("TV'yi değiştir", "ghost", lambda: self._tv_phase("choose")), spacing=8))
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
        gl.addWidget(self.tv_guide, 1)
        self.tv_stack.addWidget(guide_page)
        lay.addWidget(self.tv_stack, 1)
        self.tv_brand.currentIndexChanged.connect(self._tv_brand_changed)
        self.tv_brand.currentIndexChanged.connect(self._tv_brand_external)
        self._tv_brand_changed()
        self._tv_phase("guide" if self.cfg.tv.ip else "choose")     # daha önce kurulduysa doğrudan adımlar
        return w

    def _tv_brand_changed(self, *_a) -> None:  # noqa: ANN002
        brand = self.tv_brand.currentData()
        self.cfg.tv.marka = brand
        self.lg_pass.setVisible(brand == "lg")
        self.pair_toggle.setVisible(brand == "android")
        self.pair_row.setVisible(brand == "android" and self.pair_toggle.isChecked())
        self.tv_guide.index = 0
        self.tv_guide.set_steps(rehber.TV_STEPS[brand], {"baglan": self.tv_conn, "pcip": self.pc_ip})
        self.tv_brand_lbl.setText(TV_NAMES.get(brand, brand))
        if brand in ("lg", "samsung"):
            self.tv_lgsam.setValue(brand)
        self._tv_sync_kind()

    def _tv_brand_external(self, *_a) -> None:  # noqa: ANN002
        """Marka kartlar dışından değiştirildiyse (ör. kod ya da eski arayüz) doğrudan o markanın adımları."""
        if not getattr(self, "_tv_from_card", False):
            self._tv_phase("guide")

    def _tv_sync_kind(self) -> None:
        brand = self.tv_brand.currentData()
        self.tv_kinds.set("yok" if self.where == "monitor" else ("android" if brand == "android" else "lgsam"))

    def _tv_kind(self, kind: str) -> None:
        """TV türü kartına basıldı: marka listesini ayarla; 'TV'm yok' seçilirse bilgisayar ekranına geç."""
        if kind == "yok":
            if self.where != "monitor":
                self._where_before_tv = self.where
            self._set_where("monitor")
        else:
            if self.where == "monitor":
                self._set_where(getattr(self, "_where_before_tv", "tv"))
            brand = "android" if kind == "android" else (self.tv_lgsam.value() or "lg")
            self._tv_from_card = True
            try:
                self.tv_brand.setCurrentIndex(self.tv_brand.findData(brand))
            finally:
                self._tv_from_card = False
            self.tv_kinds.set(kind)
        if hasattr(self, "stack"):
            self._update_next()

    def _tv_choosing(self) -> bool:
        return self.tv_stack.currentIndex() == 0

    def _tv_phase(self, phase: str) -> None:
        self.tv_stack.setCurrentIndex(0 if phase == "choose" else 1)
        self.tv_page.subtitle.setText(self.TV_SUB_CHOOSE if phase == "choose" else self.TV_SUB_GUIDE)
        if phase == "choose":
            self._tv_sync_kind()
        if hasattr(self, "stack"):
            self._update_next()

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
        # Gemini seçiliyken Nino gibi numaralı üç adım
        self.gemini_steps = QWidget()
        self.gemini_steps.setLayout(vbox(*(hbox(step_num(n), self._rich(text), spacing=12) for n, text in (
            (1, "<b>Ücretsiz anahtar al</b>'a bas ve Google hesabınla giriş yap."),
            (2, "<b>Create API key</b>'e bas ve anahtarı kopyala."),
            (3, "Anahtarı buraya yapıştır ve <b>Kaydet ve dene</b>'ye bas."))), spacing=6, margins=(0, 4, 0, 4)))
        card.add(self.gemini_steps)
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
        lay.addWidget(card)
        self.eng_dot = Dot("warn")
        self.eng_msg = label("Motorlar hazırlanıyor...", "muted", wrap=True)
        self.test_btn = button("Kaydet ve dene", None, self._test)
        self.test_out = label("", "muted", wrap=True)
        test_row = hbox(self.test_btn, 14, self.eng_dot, spacing=6)
        test_row.addWidget(self.eng_msg, 1)
        lay.addLayout(test_row)
        lay.addWidget(self.test_out)
        # Anahtar çalışınca (Nino): ✓ Gemini hazır + deneme çevirisinin önizlemesi + kısa bilgiler
        self.ok_box = QFrame()
        self.ok_box.setObjectName("cardAccent")
        okl = QHBoxLayout(self.ok_box)
        okl.setContentsMargins(18, 14, 14, 14)
        okl.setSpacing(16)
        self.ok_title = label("", "h2")
        self.ok_sub = label("", "muted", wrap=True)
        left = vbox(hbox(GlyphTile("check", 46), vbox(self.ok_title, self.ok_sub, spacing=2), spacing=14), 4,
                    spacing=6)
        self.ok_info: list = []
        for icon in ("lock", "bolt", "settings"):
            t = label("", "faint", wrap=True)
            self.ok_info.append(t)
            g = Glyph(icon, 16, T.FAINT)
            row = QHBoxLayout()
            row.setSpacing(9)
            row.addWidget(g, 0, Qt.AlignTop)
            row.addWidget(t, 1)
            left.addLayout(row)
        left.addStretch(1)
        okl.addLayout(left, 1)
        self.ok_preview = SubtitlePreview("Arabaya bin, hemen gidiyoruz!", TEST_LINE)
        self.ok_preview.setMinimumHeight(0)
        self.ok_preview.setFixedSize(288, 162)
        self.ok_preview.set_style(lineScale=1.6)
        okl.addWidget(self.ok_preview, 0, Qt.AlignTop)
        self.ok_box.hide()
        lay.addWidget(self.ok_box)
        lay.addStretch(1)
        self.engine.currentIndexChanged.connect(self._engine_changed)
        self._engine_changed()
        if self.ctl.engine_info:
            self._on_engines(self.ctl.engine_info)
        self.tr_scroll = scroll_page(w)
        return self.tr_scroll

    @staticmethod
    def _rich(text: str):  # noqa: ANN205
        lb = label(text, "muted", wrap=True)
        lb.setTextFormat(Qt.RichText)
        return lb

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
        if i == P_TV:
            return None if not hasattr(self, "tv_stack") or self._tv_choosing() else self.tv_guide
        return None

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
        if i == P_TV and not self._tv_choosing():        # rehberin başındayken Geri: TV türü seçimine dön
            self._tv_phase("choose")
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
        if i == P_TV and self._tv_choosing() and self.where != "monitor" and self.sender() is not self.skip:
            self._tv_phase("guide")                       # TV türü seçildi: o markanın resimli adımları
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
        "gemini": "Anahtar sayfası aistudio.google.com'da açılır. Ücretsiz kotası oyun için genelde yeter.",
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
        self.key_btn.setText("Ücretsiz anahtar al" if eng == "gemini" else "Anahtar al")
        self.gemini_steps.setVisible(eng == "gemini")
        if hasattr(self, "ok_box"):                       # motor değişti: önceki "hazır" geçerli değil
            self.ok_box.hide()
            self.test_out.show()

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
        self.test_out.show()
        self.ok_box.hide()
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
            eng = self.engine.currentData()
            if eng in ENGINE_NAMES and info.get("kalite") != eng:
                self.test_out.setText(f"{ENGINE_NAMES[eng]} açılamadı: anahtarı kontrol edip yeniden <b>Kaydet ve "
                                      "dene</b>'ye bas. O zamana kadar bu bilgisayardaki ücretsiz çeviri çalışır.")
            elif eng in ENGINE_NAMES:
                self.test_out.setText(f"{ENGINE_NAMES[eng]} deneniyor...")
            self.ctl.test_translation(TEST_LINE)

    def _on_test(self, r) -> None:  # noqa: ANN001
        if not hasattr(self, "_results"):
            self._results = []
        self._results.append(f"<b>{r.text}</b> <span style='color:{T.FAINT}'>· {r.source} · {r.ms:.0f} ms</span>")
        self.test_out.setText("<br>".join(self._results))
        eng = self.engine.currentData()
        if eng in ENGINE_NAMES and r.source.split("/")[-1] == eng:    # çeviri o motordan geldi: anahtar çalışıyor
            self._show_ready(eng, r.text)

    def _show_ready(self, eng: str, text: str = "") -> None:
        """Nino'daki başarı ekranı: ✓ <motor> hazır, deneme çevirisi önizlemede, altta kısa bilgiler."""
        name = ENGINE_NAMES.get(eng, eng)
        self.ok_title.setText(f"{name} hazır")
        self.ok_sub.setText(f"Altyazılar artık {name} ile çevrilecek.")
        if text:
            text = text if len(text) <= 52 else text[:50].rstrip() + "…"
            # önizleme tek satır: uzun çeviride yazı küçülsün ki kutudan taşmasın
            self.ok_preview.text = text
            self.ok_preview.set_style(lineScale=max(1.1, min(1.6, 58 / max(len(text), 1))))
        others = [{"yerelai": "yerel bir modeli", "gemini": "Gemini"}.get(k, ENGINE_NAMES[k])
                  for k in ("deepl", "claude", "gemini", "yerelai") if k != eng]
        if eng == "yerelai":
            others[-1] = "Gemini'yi"
        free = eng in ("gemini", "deepl")
        self.ok_info[0].setText("Yalnızca oyunun altyazıları gönderilir." if eng != "yerelai" else
                                "Çeviri bu bilgisayarda yapılır; hiçbir şey dışarı gönderilmez.")
        self.ok_info[1].setText("Ücretsiz sınır dolarsa bu bilgisayardaki ücretsiz çeviri devreye girer." if free else
                                f"{name} yanıt vermezse bu bilgisayardaki ücretsiz çeviri devreye girer.")
        self.ok_info[2].setText(f"{', '.join(others[:-1])} ya da {others[-1]} daha sonra Ayarlar › Çeviri ve "
                                "paketler'den seçebilirsin.")
        self.gemini_steps.hide()
        self.test_out.hide()
        self.ok_box.show()
        QTimer.singleShot(0, lambda: self.tr_scroll.ensureWidgetVisible(self.ok_box, 0, 0))   # küçük pencerede de görünsün
