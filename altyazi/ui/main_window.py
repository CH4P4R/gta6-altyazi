"""Ana pencere ve sayfalar.

Düzen GameTranslator, CouchSubs ve Nino Game Translator'dan esinlenir (solda gruplu menü, ortada büyük durum ve tek
başlat düğmesi, PS5 / Bilgisayar / TV kartları, başlıklı ayar kartları, canlı önizlemeli altyazı görünümü); renkler ve
kimlik bizim (Vice City gün batımı).
"""

from __future__ import annotations

import json
import sys
import time
import webbrowser

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QSlider, QSpinBox,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import __version__
from ..app import CHIAKI_DOWNLOAD, AppController, open_path
from ..config import BolgeCfg
from . import theme as T
from .parcalar import (TEXT_COLORS, Backdrop, Chips, Collapsible, ColorDots, HealthRow, HelpFab, IconTile, Pill,
                       PlugScene, RadioCard, RadioGroup, SectionCard, Segmented, SlideToggle, StyleCard, SubtitlePreview,
                       Toggle, TvPreview, FontChoice, ViewChoice)
from .region_editor import PRESETS, RegionCanvas
from .widgets import Card, Icon, Logo, NavButton, QrCode, Sparkline, Toast, button, hbox, label, scroll_page, vbox

QCheckBox = Toggle          # bütün açma/kapama seçenekleri anahtar görünümünde


def page_header(title: str, subtitle: str, icon: str | None = None) -> QHBoxLayout:
    col = vbox(label(title, "h1"), label(subtitle, "muted", wrap=True), spacing=4)
    if not icon:
        return hbox(col, spacing=0)
    return hbox(IconTile(icon, 52), 4, col, spacing=14)


def combo(items: list[tuple[str, str]], current: str) -> QComboBox:
    c = QComboBox()
    for value, text in items:
        c.addItem(text, value)
    i = c.findData(current)
    c.setCurrentIndex(max(0, i))
    return c


def slider(lo: int, hi: int, val: int) -> QSlider:
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    return s


def field(title: str, w: QWidget, hint: str = "") -> QVBoxLayout:
    items = [label(title, "h3"), w]
    if hint:
        items.append(label(hint, "faint", wrap=True))
    return vbox(*items, spacing=6)


def slider_row(title: str, s: QSlider, fmt) -> QVBoxLayout:  # noqa: ANN001
    """Başlık solda, değer sağda (mavi yerine bizim turuncu), altında kaydırıcı (GameTranslator düzeni)."""
    val = label("", "h3")
    val.setStyleSheet(f"color:{T.A2};")
    s.valueChanged.connect(lambda v: val.setText(fmt(v)))
    val.setText(fmt(s.value()))
    return vbox(hbox(label(title, "h3"), None, val), s, spacing=6)


def page_shell(widget: QWidget, title: str, subtitle: str, icon: str | None = None, scroll: bool = True) -> QVBoxLayout:
    """Sayfa iskeleti: ortalanmış, en çok 1180 px genişlikte içerik; uzun sayfalar kayar. İçerik düzenini döndürür."""
    content = QWidget()
    content.setObjectName("transparent")
    outer = QHBoxLayout(content)
    outer.setContentsMargins(36, 30, 36, 30)
    col_w = QWidget()
    col_w.setMaximumWidth(1180)
    col = QVBoxLayout(col_w)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(16)
    col.addLayout(page_header(title, subtitle, icon))
    col.addSpacing(4)
    outer.addStretch(0)
    outer.addWidget(col_w, 1)
    outer.addStretch(0)
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(scroll_page(content) if scroll else content)
    return col


def _transparent(w: QWidget) -> QWidget:
    """Sayfa zemini boyanmasın (arkadaki ışıltı görünsün). Biçim alt öğelere geçmesin diye yalnız kendi adına yazılır."""
    if not w.objectName():
        w.setObjectName("clear")
    w.setStyleSheet(f"#{w.objectName()} {{ background: transparent; }}")
    return w


# ============================================================================ Ana ekran
class _DeviceCard(Card):
    """PS5 / Bilgisayar / TV kartı: ikon ve durum etiketi üstte, büyük başlık, açıklama, altta eylem."""

    def __init__(self, icon: str, title: str, action: str | None = None, slot=None):  # noqa: ANN001
        super().__init__(margins=20, spacing=6)
        self.icon = Icon(icon, 28, T.A2)
        self.pill = Pill("", "off")
        self.add(hbox(self.icon, None, self.pill))
        self.add(6)
        self.title = label(title, "h2")
        self.title.setStyleSheet("font-size: 17pt;")
        self.add(self.title)
        self.status = label("", "muted", wrap=True)
        self.status.setMinimumHeight(38)
        self.status.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.add(self.status)
        self.action = None
        if action:
            self.action = button(action, "link", slot)
            self.add(hbox(self.action, None))
        self.setMinimumWidth(220)

    def add(self, w, stretch: int = 0):  # noqa: ANN001
        if isinstance(w, int):
            self.lay.addSpacing(w)
            return w
        return super().add(w, stretch)

    def set(self, state: str, pill: str, text: str) -> None:
        self.pill.set(state, pill)
        self.status.setText(text)


class _LiveRow(QFrame):
    """Son çeviri kartındaki eski satır: Türkçe üstte, İngilizcesi altta (CouchSubs canlı altyazı)."""

    def __init__(self, it):  # noqa: ANN001
        super().__init__()
        self.seq = it.seq
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(2)
        self.tr = label("", "prevTr", wrap=True)
        self.en = label("", "faint", wrap=True)
        lay.addWidget(self.tr)
        lay.addWidget(self.en)
        self.setStyleSheet(f"QFrame {{ border-top: 1px solid {T.BORDER}; }} QLabel {{ border: 0; }}")
        self.update_item(it)

    def update_item(self, it) -> None:  # noqa: ANN001
        self.tr.setText(it.text)
        self.en.setText(it.english)


class HomePage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        content = QWidget()
        content.setObjectName("clearHome")
        content.setStyleSheet("#clearHome { background: transparent; }")
        outer = QHBoxLayout(content)
        outer.setContentsMargins(36, 26, 36, 24)
        col_w = QWidget()
        col_w.setMaximumWidth(1120)
        root = QVBoxLayout(col_w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        outer.addStretch(1)
        outer.addWidget(col_w, 30)
        outer.addStretch(1)

        # --- güncelleme kartı (yeni sürüm varsa görünür)
        self.upd = SectionCard(accent=True, margins=14)
        self.upd_title = label("", "h3")
        self.upd_text = label("Tek tıkla indirilir ve kurulur; ayarların, anahtarların ve paketlerin korunur. "
                              "Program kapanıp yeni sürümle yeniden açılır.", "muted", wrap=True)
        self.upd_btn = button("Güncelle", "primary", self._update)
        self.upd.add(hbox(vbox(self.upd_title, self.upd_text, spacing=2), None, self.upd_btn, spacing=14))
        self.upd.hide()
        root.addWidget(self.upd)
        ctl.updateAvailable.connect(self._on_update)
        ctl.updateProgress.connect(self._on_update_progress)

        # --- sahne: mor gün batımı duvarında TV, sehpa, PS5 ve priz; ya da TV önizlemesi + kaydırmalı düğme
        stage = QFrame()
        stage.setObjectName("stagePanel")
        stage.setStyleSheet("#stagePanel { border-radius: 26px; border: 1px solid rgba(255, 120, 190, 0.20);"
                            " background: qradialgradient(cx:0.5, cy:0.32, radius:0.95, fx:0.5, fy:0.28,"
                            " stop:0 #3d1554, stop:0.55 #1f0c33, stop:1 #0c0614); }")
        sv = QVBoxLayout(stage)
        sv.setContentsMargins(22, 16, 22, 14)
        sv.setSpacing(6)
        self.sub = label("", "eyebrow")                     # kısa durum: HAZIR / ÇEVİRİ ÇALIŞIYOR
        self.style_sw = Segmented([("fis", "Salon"), ("dugme", "Cam düğme")], ctl.cfg.gosterim.ana_ekran
                                  if ctl.cfg.gosterim.ana_ekran in ("fis", "dugme") else "fis")
        self.style_sw.setFixedWidth(220)
        self.style_sw.setToolTip("Ana ekranın görünümü: fişi prize sürükle ya da kaydırmalı düğme")
        self.style_sw.changed.connect(self._set_style)
        sv.addLayout(hbox(self.sub, None, self.style_sw, spacing=8))
        self.stage = QStackedWidget()
        _transparent(self.stage)
        self.scene = PlugScene()                            # fişi prize sürükle
        self.scene.plugged.connect(self._plugged)
        self.stage.addWidget(self.scene)
        slider_page = QWidget()
        _transparent(slider_page)
        spl = QVBoxLayout(slider_page)
        spl.setContentsMargins(0, 0, 0, 0)
        spl.setSpacing(4)
        self.tv_prev = TvPreview()
        self.slide = SlideToggle()
        self.slide.toggled.connect(self._plugged)
        spl.addWidget(self.tv_prev, 1)
        spl.addLayout(hbox(None, self.slide, None))
        self.stage.addWidget(slider_page)
        self.stage.setMinimumHeight(470)
        sv.addWidget(self.stage, 1)
        self.stage_cap = label("", "faint")
        self.stage_cap.setAlignment(Qt.AlignCenter)
        self.stage_cap.setStyleSheet("color: rgba(255, 228, 240, 0.78); font-size: 11pt;")
        sv.addWidget(self.stage_cap)
        root.addWidget(stage)
        self._set_style(self.style_sw.value(), save=False)

        # --- durum ve düğmeler (GameTranslator'ın tek düğmesi sahnenin altında)
        bar = Card(margins=18, spacing=10)
        self.state_title = label("Hazırlanıyor", "h2")
        self.state_hint = label("Çeviri modelleri ve yazı okuyucu yükleniyor.", "muted", wrap=True)
        self.start = button("▶  Çeviriyi Başlat", "primaryBig", ctl.toggle)
        self.start.setMinimumWidth(220)
        how = button("Nasıl çalışır ›", "link", lambda: self.window().go("guide"))
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addLayout(vbox(self.state_title, self.state_hint, spacing=2), 1)
        head.addWidget(how)
        head.addSpacing(10)
        head.addWidget(self.start)
        bar.add(head)
        self.show_where = Segmented([("tv", "TV"), ("monitor", "Bilgisayar ekranı"), ("ikisi", "İkisi de")],
                                    ctl.cfg.kaynak.oyun_yeri)
        self.show_where.setFixedWidth(400)
        self.show_where.changed.connect(self._set_where)
        demo = button("▷  Deneme modu (konsol olmadan dene)", "link", self._demo,
                      "Örnek görüntüyle her şeyi dene: konsol, hesap ya da TV gerekmez")
        bar.add(hbox(label("Altyazıyı göster", "faint"), self.show_where, 14, demo, None, spacing=10))
        self.stats = label("", "stat")
        keys = ctl.cfg.kisayol
        self.keys_hint = label(f"Kısayol: {keys.tam_ekran.upper()} ekranı çevir · {keys.duraklat.upper()} duraklat",
                               "faint")
        # gecikme ve Claude harcaması (kalite katmanı Claude ise)
        self.lat = label("—", "h3")
        self.spark = Sparkline()
        self.spark.setFixedSize(150, 30)
        self.spend = label("", "faint")
        self.spend_sub = label("", "faint")
        tip = ("Claude'un her yanıtta bildirdiği token sayısı × Anthropic liste fiyatı. Önbellekten ve hazır paketten\n"
               "gelen çeviriler ücretsizdir. Kesin fatura: console.anthropic.com › Billing.")
        self.spend.setToolTip(tip)
        self.spend_sub.setToolTip(tip)
        bar.add(hbox(self.stats, None, label("Ortalama gecikme", "faint"), self.lat, label("ms", "faint"), self.spark,
                     12, vbox(self.spend, self.spend_sub, spacing=0), spacing=6))
        bar.add(self.keys_hint)
        root.addWidget(bar)

        # --- PS5 / Bilgisayar / TV kartları
        grid = QGridLayout()
        grid.setSpacing(16)
        self.c_ps = _DeviceCard("ps", "PS5", "PS5'i bağla ›", self._ps_action)
        self.c_pc = _DeviceCard("monitor", "Bilgisayar", "Çeviri ayarları ›", lambda: self.window().go("translate"))
        self.c_tv = _DeviceCard("tv", "TV", "TV'yi bağla ›", lambda: self.window().go("tv"))
        self.c_tv.add(hbox(button("TV'de test et", "link", ctl.tv_test, "TV'ye deneme altyazısı gönder"), 14,
                           button("TV uygulamasını yeniden kur", "link", self._tv_reinstall), None, spacing=0))
        self.c_eng = self.c_pc                                 # eski ad
        self.tv_play_btn = button("TV'de oynuyorum (chiaki'siz) ›", "link", self._open_ps5,
                                  "Oyunu TV'de oynarsın; bilgisayar PS5'e arka planda ikinci hesapla bağlanır")
        self.c_ps.add(hbox(self.tv_play_btn, None))
        self.tv_play_btn.hide()
        for i, w in enumerate((self.c_ps, self.c_pc, self.c_tv)):
            grid.addWidget(w, 0, i)
            grid.setColumnStretch(i, 1)
        root.addLayout(grid)

        # --- son çeviri (CouchSubs canlı altyazı) + telefon/ikinci ekran
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        feed = Card(margins=20, spacing=6)
        self.fs_btn = button("Ekranı çevir", None, lambda: ctl.command("tam_ekran"),
                             "Telefon, menü, harita gibi ekrandaki tüm yazıları çevir")
        self.pause_btn = button("Duraklat", None, self._pause)
        feed.add(hbox(label("Son çeviri", "h3"), None, self.fs_btn, self.pause_btn, spacing=8))
        self.empty = label("Oyunda altyazı çıkınca çevirisi burada ve TV'de görünür.", "liveEn", wrap=True)
        self.empty.setStyleSheet("font-size: 15pt;")
        self.live_tr = label("", "liveTr", wrap=True)
        self.live_en = label("", "liveEn", wrap=True)
        self.live_meta = label("", "faint")
        for w in (self.live_tr, self.live_en, self.live_meta):
            w.hide()
        feed.add(self.empty)
        feed.add(self.live_tr)
        feed.add(self.live_en)
        feed.add(self.live_meta)
        self.list_w = QWidget()
        _transparent(self.list_w)
        self.list_l = QVBoxLayout(self.list_w)
        self.list_l.setContentsMargins(0, 6, 4, 0)
        self.list_l.setSpacing(0)
        self.list_l.addStretch(1)
        feed.add(scroll_page(self.list_w), 1)
        self.game_link = button("Oyun: Otomatik ›", "link", lambda: self.window().go("translate"))
        self.zone_link = button("Okunan yer: Otomatik ›", "link", lambda: self.window().go("regions"))
        look = button("TV'deki görünüm ›", "link", lambda: self.window().go("look"))
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{T.BORDER};")
        feed.add(line)
        self.src_link = button("Görüntü: …", "link", lambda: self.window().go("tv"))
        self.eng_link = button("Çeviri: …", "link", lambda: self.window().go("translate"))
        feed.add(hbox(self.game_link, 18, self.zone_link, 18, look, 18, self.src_link, 18, self.eng_link, None,
                      spacing=0))
        bottom.addWidget(feed, 2)

        phone = Card(margins=20, spacing=8)
        self.qr = QrCode(132)
        self.qr.setData(ctl.server_url("kumanda"))
        phone.add(label("Telefon kumandası", "h3"))
        phone.add(label("Telefonun kamerasıyla okut: ekranı çevir, duraklat, son altyazılar. TV yoksa ikinci ekran "
                        "olur.", "muted", wrap=True))
        phone.add(hbox(None, self.qr, None))
        phone.add(label(ctl.server_url("kumanda").replace("http://", ""), "mono", wrap=True))
        phone.lay.addStretch(1)
        phone.setMaximumWidth(330)
        bottom.addWidget(phone, 1)
        feed.setMinimumHeight(360)
        root.addLayout(bottom, 1)
        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        page.addWidget(scroll_page(content))
        self.items: dict[int, object] = {}
        self._live_seq = None

        ctl.stateChanged.connect(self.on_state)
        ctl.historyChanged.connect(self.on_item)
        ctl.sourceStatus.connect(self.on_source)
        ctl.ps5Status.connect(self.on_ps5)
        ctl.tvStatus.connect(self.on_tv)
        ctl.enginesReady.connect(self.on_engines)
        ctl.spendChanged.connect(self.on_spend)
        ctl.gameAsk.connect(self._ask_game)
        self._spend_timer = QTimer(self)               # saatlik ortalama zamanla değişir
        self._spend_timer.timeout.connect(self.on_spend)
        self._spend_timer.start(30000)
        self._links = QTimer(self)
        self._links.timeout.connect(self._refresh_links)
        self._links.start(3000)
        self.on_spend()
        self.on_state(ctl.state)
        self.on_tv(*ctl.tv_state)
        self._ps_initial()
        if ctl.engine_info:
            self.on_engines(ctl.engine_info)
        self._refresh_links()

    # --------------------------------------------------------------- durum
    def _pause(self) -> None:
        r = self.ctl.command("duraklat")
        self.pause_btn.setText("Devam et" if r.get("duraklatildi") and self.ctl.pipe else "Duraklat")

    def _plugged(self, on: bool) -> None:
        if on and self.ctl.state == "hazir":
            self.ctl.toggle()
        elif not on and self.ctl.state == "calisiyor":
            self.ctl.toggle()
        running = self.ctl.state == "calisiyor"
        self.scene.setRunning(running)
        self.slide.setOn(running)
        self._caption()

    def _set_style(self, v: str, save: bool = True) -> None:
        self.stage.setCurrentIndex(1 if v == "dugme" else 0)
        if self.style_sw.value() != v:
            self.style_sw.blockSignals(True)
            self.style_sw.setValue(v)
            self.style_sw.blockSignals(False)
        look = getattr(self.window(), "pages", {}).get("look") if save else None
        if look is not None and look.view.value() != v:
            look.view.setValue(v)
        if save and v != self.ctl.cfg.gosterim.ana_ekran:
            cfg = self.ctl.edit_config()
            cfg.gosterim.ana_ekran = v
            self.ctl.apply_config(cfg)
        self._caption()

    def _caption(self) -> None:
        running = self.ctl.state == "calisiyor"
        if self.stage.currentIndex() == 1:
            t = "Kapatmak için düğmeyi sola kaydırın" if running else "Açmak için düğmeyi sağa kaydırın"
        else:
            t = "Durdurmak için fişi çekin" if running else "Çeviriyi başlatmak için fişi prize takın"
        if self.ctl.state == "hazirlaniyor":
            t = "Hazırlanıyor… birkaç saniye sonra başlatabilirsin"
        self.stage_cap.setText(t)

    def _set_where(self, v: str) -> None:
        cfg = self.ctl.edit_config()
        cfg.kaynak.oyun_yeri = v
        if v == "monitor" and cfg.kaynak.tur == "remoteplay":
            cfg.kaynak.tur = "pencere"
        elif v in ("tv", "ikisi") and cfg.kaynak.tur == "pencere" and cfg.ps5.anahtar:
            cfg.kaynak.tur = "remoteplay"
        self.ctl.apply_config(cfg)
        self.window().toast.show_text({"tv": "Türkçe yalnız TV'de görünecek", "monitor": "Türkçe bilgisayar ekranında "
                                       "görünecek", "ikisi": "Türkçe hem TV'de hem bilgisayarda görünecek"}[v])
        self._ps_initial()

    def _tv_reinstall(self) -> None:
        ip = self.ctl.cfg.tv.ip
        if not ip:
            self.window().go("tv")
            self.window().toast.show_text("Önce TV'nin adresini yaz ya da Ağda ara'ya bas")
            return
        self.ctl.tv_connect(ip, force_install=True)
        self.window().toast.show_text("TV uygulaması yeniden kuruluyor…")

    def _demo(self) -> None:
        if self.ctl.state == "calisiyor":
            self.window().toast.show_text("Önce çeviriyi durdur, sonra deneme modunu aç")
            return
        if self.ctl.start_demo():
            self.window().toast.show_text("Deneme modu: örnek altyazılar okunup çevriliyor. Durdurmak için Çeviriyi "
                                          "Durdur'a bas.")

    def _ask_game(self, titles: list) -> None:
        """'Hangi oyunu oynuyorsun?' (Nino / CouchSubs): oyun paketle tanınmadıysa çeviri başladıktan iki dk sonra."""
        from PySide6.QtWidgets import QInputDialog
        items = list(titles) + ["Listede yok"]
        name, ok = QInputDialog.getItem(self, "Hangi oyunu oynuyorsun?", "Oyunu seçersen çeviri ilk cümleden itibaren "
                                        "oyunun hazır paketinden gelir:", items, 0, False)
        if ok and name and name != "Listede yok":
            self.ctl.game_choice.choose(name)
            self._refresh_links()
        else:
            self.ctl.game_choice.dismiss()

    def _rp(self) -> bool:
        k = self.ctl.cfg.kaynak
        return k.tur == "remoteplay" or (k.tur == "pencere" and k.oyun_yeri == "tv")

    def on_state(self, s: str) -> None:
        rp = self.ctl.cfg.kaynak.tur == "remoteplay"
        texts = {
            "hazirlaniyor": ("Hazırlanıyor…", "Çeviri modelleri ve yazı okuyucu yükleniyor, birkaç saniye sürer.",
                             "MOTORLAR HAZIRLANIYOR"),
            "hazir": ("Çeviri kapalı.", "Oyunda altyazıları aç, sonra başlat." + (" PS5'e arka planda bağlanılır."
                                                                                   if rp else ""), "HAZIR"),
            "calisiyor": ("Çeviri açık.", "Oyundaki yazılar okunuyor ve Türkçesi TV'ye gidiyor.", "ÇEVİRİ ÇALIŞIYOR"),
            "hata": ("Bir sorun var", "Motorlar yüklenemedi. Çeviri ve Paketler sayfasından ayarları kontrol et.",
                     "HATA"),
        }
        t, h, sub = texts.get(s, (s, "", s))
        self.state_title.setText(t)
        self.state_hint.setText(h)
        self.sub.setText(sub)
        running = s == "calisiyor"
        self.scene.setRunning(running)
        self.slide.setOn(running)
        self.tv_prev.setRunning(running)
        self._caption()
        self.start.setObjectName("stopBig" if running else "primaryBig")
        self.start.setText("■  Çeviriyi Durdur" if running else "▶  Çeviriyi Başlat")
        self.start.style().unpolish(self.start)
        self.start.style().polish(self.start)
        self.start.setEnabled(s in ("hazir", "calisiyor"))
        self.fs_btn.setEnabled(running)
        self.pause_btn.setEnabled(running)
        if not running:
            self.pause_btn.setText("Duraklat")
        pc = {"hazirlaniyor": ("warn", "Hazırlanıyor"), "hazir": ("info", "Hazır"), "calisiyor": ("ok", "Çeviriyor"),
              "hata": ("bad", "Hata")}.get(s, ("off", s))
        self.c_pc.pill.set(*pc)
        self._pc_text()

    def _pc_text(self) -> None:
        info = self.ctl.engine_info or {}
        parts = ["Altyazıları okuyup çevirir."]
        if info:
            eng = info.get("kalite") or info.get("hizli") or "—"
            parts.append(f"Okuma: {info.get('ocr', '…')}\nÇeviri: {eng}")
        self.c_pc.status.setText("\n".join(parts))

    def on_item(self, it, updated: bool) -> None:  # noqa: ANN001
        if self.empty.isVisible():
            self.empty.hide()
            for w in (self.live_tr, self.live_en, self.live_meta):
                w.show()
        if updated and self._live_seq == it.seq:
            self._show_live(it)
        elif updated and it.seq in self.items:
            self.items[it.seq].update_item(it)
        elif not updated:
            prev = getattr(self, "_live_item", None)
            if prev is not None:
                w = _LiveRow(prev)
                self.items[prev.seq] = w
                self.list_l.insertWidget(0, w)
                while len(self.items) > 40:
                    old = min(self.items)
                    self.items.pop(old).deleteLater()
            self._show_live(it)
        if not updated:
            self.items.setdefault(it.seq, _NullRow())
        avg = self.ctl.avg_latency()
        if avg is not None:
            self.lat.setText(f"{avg:.0f}")
        if not updated:
            self.spark.push(it.latency_ms)

    def _show_live(self, it) -> None:  # noqa: ANN001
        self.scene.setText(it.text)
        self.tv_prev.setText(it.text, it.english)
        self._live_seq = it.seq
        self._live_item = it
        self.live_tr.setText(it.text)
        self.live_en.setText(it.english)
        q = "✓ " if it.quality >= 2 else ""
        self.live_meta.setText(f"{q}Okuma {it.ocr_ms:.0f} ms · Çeviri {it.mt_ms:.0f} ms · Gecikme {it.latency_ms:.0f} ms"
                               f" · {it.source}")

    def _refresh_links(self) -> None:
        try:
            g = self.ctl.game_choice.game
            name = (g.name if g else None) or "Otomatik"
        except Exception:  # noqa: BLE001
            name = "Otomatik"
        self.game_link.setText(f"Oyun: {name} ›")
        learned = False
        try:
            learned = bool(self.ctl.layout.get(self.ctl.layout_key()))
        except Exception:  # noqa: BLE001
            learned = False
        self.zone_link.setText(f"Okunan yer: {'Öğrenildi' if learned else 'Otomatik'} ›")
        src = {"remoteplay": "PS5 (ikinci hesap)", "pencere": "chiaki-ng penceresi", "capture": "Yakalama kartı",
               "video": "Video"}.get(self.ctl.cfg.kaynak.tur, self.ctl.cfg.kaynak.tur)
        self.src_link.setText(f"Görüntü: {'Deneme modu' if getattr(self.ctl, 'demo', False) else src} ›")
        eng = (self.ctl.engine_info or {}).get("kalite") or (
            "Ücretsiz" if (self.ctl.engine_info or {}).get("hizli") else self.ctl.cfg.ceviri.kalite)
        self.eng_link.setText(f"Çeviri: {str(eng).capitalize()} ›")

    def _on_update(self, rel: dict) -> None:
        size = rel.get("size", 0) / 1e9
        self.upd_title.setText(f"Yeni sürüm hazır: GTA6 Altyazı {rel['version']}" + (f"  ·  {size:.1f} GB" if size else ""))
        self.upd.show()

    def _update(self) -> None:
        self.upd_btn.setEnabled(False)
        self.upd_btn.setText("İndiriliyor...")
        self.ctl.install_update()

    def _on_update_progress(self, f: float) -> None:
        if f < 0:
            self.upd_btn.setEnabled(True)
            self.upd_btn.setText("Tekrar dene")
        elif f >= 1:
            self.upd_btn.setText("Kuruluyor, program yeniden açılacak...")
        else:
            self.upd_btn.setText(f"İndiriliyor %{int(f * 100)}")

    # --------------------------------------------------------------- PS5
    def _ps_action(self) -> None:
        if self._rp():
            self._open_ps5()
        else:
            self.ctl.launch_chiaki()

    def _open_ps5(self) -> None:
        from .ps5_dialog import Ps5Dialog
        Ps5Dialog(self.ctl, self).exec()
        self.ctl._check_source()
        self._ps_initial()

    def _ps_initial(self) -> None:
        """Açılışta ve eşleme sonrası: TV'de oynayan için chiaki'den hiç söz etme."""
        p = self.ctl.cfg.ps5
        if self.ctl.cfg.kaynak.tur == "remoteplay" and p.anahtar:
            state, msg = getattr(self.ctl, "rp_state", ("", ""))
            if state:
                self.on_ps5(state, msg)
            else:
                self.c_ps.set("ok", "Eşleşti", f"{p.ad or 'PS5'} · {p.ip}".strip(" ·"))
                self.c_ps.action.setText("PS5 ayarları ›")
        elif self._rp():
            self.c_ps.set("off", "Eşli değil", "Bir kez bağla: ikinci PSN hesabıyla giriş ve PS5'teki 8 haneli kod.")
            self.c_ps.action.setText("PS5'i bağla ›")

    def on_ps5(self, state: str, msg: str) -> None:
        if self.ctl.cfg.kaynak.tur != "remoteplay":
            return
        self.tv_play_btn.hide()
        p = self.ctl.cfg.ps5
        if state == "yok" or not p.anahtar:
            self.c_ps.set("off", "Eşli değil", "Bir kez bağla: ikinci PSN hesabıyla giriş ve PS5'teki 8 haneli kod.")
            self.c_ps.action.setText("PS5'i bağla ›")
            return
        pill = {"bagli": ("ok", "Bağlı"), "baglaniyor": ("warn", "Bağlanıyor"), "kopuk": ("bad", "Koptu"),
                "durdu": ("ok", "Eşleşti")}.get(state, ("ok", "Eşleşti"))
        self.c_ps.set(pill[0], pill[1], msg or f"{p.ad or 'PS5'} · {p.ip}".strip(" ·"))
        self.c_ps.action.setText("PS5 ayarları ›")

    def on_source(self, ok: bool, title: str) -> None:
        k = self.ctl.cfg.kaynak
        if k.tur == "remoteplay":
            return
        if k.tur != "pencere":
            self.c_ps.set("ok", "Hazır", f"Kaynak: {title}")
            self.c_ps.action.hide()
            return
        self.c_ps.action.show()
        if k.oyun_yeri == "tv":                        # TV'de oynayan: chiaki yok, PS5'e arka planda bağlan
            self._ps_initial()
            return
        self.tv_play_btn.setVisible(not ok)
        if ok:
            self.c_ps.set("ok", "Açık", f"Pencere bulundu: {title}")
            self.c_ps.action.setText("chiaki-ng açık")
            self.c_ps.action.setEnabled(False)
        else:
            self.c_ps.set("off", "Kapalı", "chiaki-ng penceresi açık değil. Aç ve PS5'e ikinci hesapla bağlan.")
            self.c_ps.action.setText("chiaki-ng'yi aç ›")
            self.c_ps.action.setEnabled(True)

    # --------------------------------------------------------------- TV, motorlar, harcama
    def on_tv(self, state: str, msg: str) -> None:
        brand = {"android": "Android TV", "lg": "LG webOS", "samsung": "Samsung Tizen"}.get(self.ctl.cfg.tv.marka, "TV")
        dot, pill = {"bagli": ("ok", "Bağlı"), "baglaniyor": ("warn", "Bağlanıyor"), "onay": ("info", "Onay bekliyor"),
                     "hata": ("bad", "Hata")}.get(state, ("off", "Bağlı değil"))
        if state == "yok" or (state == "" and not msg):
            msg = "Kurulmadı. Türkçe TV'de oyunun üstünde çıksın diye bağla." if not self.ctl.cfg.tv.ip else \
                f"{brand} · {self.ctl.cfg.tv.ip} · çeviri başlayınca bağlanır"
        self.c_tv.set(dot, pill, msg)
        self.c_tv.action.setText("TV ayarları ›" if state == "bagli" else "TV'yi bağla ›")

    def on_engines(self, info: dict) -> None:
        ok = bool(info.get("hizli") or info.get("kalite"))
        tip = [f"Yazı okuma: {info.get('ocr')}",
               f"Hızlı çeviri: {info['hizli']}" if info.get("hizli") else "Hızlı katman yok",
               f"Kalite: {info['kalite']}" if info.get("kalite") else "Kalite katmanı kapalı"]
        self.c_pc.setToolTip("\n".join(tip))
        if not ok:
            self.c_pc.pill.set("bad", "Çeviri yok")
        self._pc_text()
        self.stats.setText(f"Okuma: {info.get('ocr', '…')}  ·  Çeviri: "
                           f"{' + '.join(x for x in (info.get('hizli'), info.get('kalite')) if x) or 'yok'}  ·  "
                           f"Hazır paket: {info.get('paket', 0):,} satır".replace(",", "."))
        self.on_spend()

    def on_spend(self) -> None:
        from ..harcama import money, tracker
        claude = (self.ctl.engine_info.get("kalite") == "claude") or tracker.total > 0
        for w in (self.spend, self.spend_sub):
            w.setVisible(claude)
        if not claude:
            return
        rate = tracker.hourly()
        self.spend.setText(f"Claude: bu oturum {money(tracker.session)}"
                           + (f" · saatte ~{money(rate)}" if rate is not None else ""))
        self.spend_sub.setText(f"Bu ay {money(tracker.month())} · toplam {money(tracker.total)}")


class _NullRow:
    """Canlı satır (henüz listeye inmemiş) için yer tutucu; testler items'ta seq görmek ister."""

    def update_item(self, _it) -> None:  # noqa: ANN001
        pass

    def deleteLater(self) -> None:  # noqa: N802
        pass


# ============================================================================ Altyazı görünümü
class AppearancePage(QWidget):
    """TV'deki ve bilgisayar ekranındaki altyazının görünümü: canlı önizleme, renk, boyut, zemin, yer (GameTranslator /
    CouchSubs). Değişiklik anında kaydedilir ve TV'ye gider."""

    PRESETS = [
        ("klasik", "Klasik", "Yarı saydam kutu", {"background": 72, "textColor": "white", "bold": False,
                                                  "backgroundShape": "fit"}),
        ("sinema", "Sinema", "Film gibi sarı", {"background": 0, "textColor": "yellow", "bold": True,
                                                "backgroundShape": "fit"}),
        ("minimal", "Minimal", "Görüntüyü kapatmaz", {"background": 35, "textColor": "white", "bold": False,
                                                      "backgroundShape": "fit"}),
        ("cam", "Gün batımı cam", "Buzlu cam, yuvarlak", {"background": 95, "textColor": "white", "bold": True,
                                                          "backgroundShape": "fit"}),
        ("kontrast", "Yüksek kontrast", "En kolay okunan", {"background": 100, "textColor": "white", "bold": True,
                                                            "backgroundShape": "band"}),
        ("kenar", "Kenarlıklı", "Oyun yazısı gibi", {"background": 0, "textColor": "white", "bold": True,
                                                     "backgroundShape": "fit"}),
    ]
    PLACES = [("cover", "İngilizce altyazının üstünü örtsün"), ("above", "İngilizce altyazının üstünde"),
              ("below", "İngilizce altyazının altında"), ("fixed", "Sabit yerde (alttan yükseklik)")]

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "Altyazı görünümü", "TV'nin ve bilgisayar ekranının ayarları ayrıdır. Değiştirdiğin "
                          "anda kaydedilir; TV bağlıysa hemen orada da görürsün.", "translate")
        t = ctl.cfg.tv
        main = self._main_zone()
        view = SectionCard("Ana ekran", "Salon: fişi prize takınca çeviri başlar. Cam düğme: düğmeyi sağa kaydırın; canlı "
                           "TV yukarıda görünür.", "home", margins=16)
        self.view = ViewChoice(ctl.cfg.gosterim.ana_ekran)
        self.view.changed.connect(self._view)
        view.add(self.view)
        root.addWidget(view)
        self.target = Segmented([("tv", "TV"), ("pc", "Bilgisayar ekranı")], "tv")
        self.target.setMaximumWidth(380)
        self.target.changed.connect(self._target)
        root.addLayout(hbox(self.target, None))

        prev = SectionCard(margins=16)
        self.preview = SubtitlePreview()
        self.preview.setMinimumHeight(260)
        self.preview.setMaximumHeight(360)
        prev.add(hbox(label("CANLI ÖNİZLEME", "eyebrow"), None, label("1920 × 1080 (16:9)", "faint")))
        prev.add(self.preview)
        cols = QHBoxLayout()
        cols.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(prev)
        presets = SectionCard("Hazır stiller", "Birine tıkla, ayarlar ona göre değişir; sonra istediğin gibi oynayabilirsin.",
                              margins=16)
        pg_ = QGridLayout()
        pg_.setSpacing(10)
        self.style_cards: dict[str, StyleCard] = {}
        for i, (key, name, desc, st) in enumerate(self.PRESETS):
            card = StyleCard(name, desc, st)
            card.clicked.connect(lambda k=key: self._preset(k))
            self.style_cards[key] = card
            pg_.addWidget(card, i // 3, i % 3)
        presets.add(pg_)
        left.addWidget(presets)
        left.addStretch(1)
        cols.addLayout(left, 11)
        right = QVBoxLayout()
        right.setSpacing(16)
        cols.addLayout(right, 9)
        root.addLayout(cols)

        # --- TV ayarları
        self.tv_box = SectionCard("TV'de", "LG, Samsung ve Android TV uygulamasında.", "tv")
        self.colors = ColorDots(TEXT_COLORS, t.yazi_rengi)
        self.size = slider(28, 96, int(t.yazi_boyutu))
        self.scale = slider(80, 200, int((main.yazi_olcek if main else 1.3) * 100))
        self.bg = slider(0, 100, round((main.kutu_opaklik if main else 255) / 255 * 100))
        self.bottom = slider(0, 40, int(t.alttan))
        self.place = combo(self.PLACES, t.yerlesim)
        self.shape = combo([("fit", "Yazı kadar"), ("band", "Tam genişlik bant")], t.zemin_sekli)
        self.bold = QCheckBox("Kalın yazı", t.kalin)
        self.fit = QCheckBox("Boyutu oyunun altyazısına uydur", getattr(t, "uydur", True))
        self.tv_font = FontChoice(t.yazi_tipi)
        self.spk_color = QCheckBox("Konuşana göre renk (her karakterin adı ve satırı kendi renginde)", t.konusan_renk)
        self.stack = QCheckBox("Hızlı konuşmada önceki satırları üstte göster", t.onceki_satirlar)
        self.logo = QCheckBox("Sol alt köşede küçük GTA6 Altyazı logosu (yayın ve ekran görüntüsü için)",
                              getattr(t, "logo", False))
        self.tv_box.add(field("Yazı rengi", self.colors))
        self.size_row = slider_row("Yazı boyutu (sabit yerde)", self.size, lambda v: f"{v} px")
        self.tv_box.add(self.fit)
        self.tv_box.add(field("Yeri", self.place, "Çeviri, oyunun kendi altyazısının çıktığı yerde görünür."))
        self.tv_box.add(slider_row("Yazı boyutu (İngilizceye göre)", self.scale, lambda v: f"{v / 100:.2f}×"))
        self.tv_box.add(slider_row("Arka plan koyuluğu", self.bg, lambda v: f"%{v}"))
        self.tv_box.add(field("Arka plan alanı", self.shape, "Koyuluk %100'de oyundaki İngilizce yazı tamamen kapanır; "
                              "tam genişlik bant yanları da örter."))
        self.tv_box.add(self.size_row)
        self.tv_box.add(slider_row("Ekran konumu (alttan yükseklik)", self.bottom, lambda v: f"%{v}"))
        self.tv_box.add(field("Yazı tipi", self.tv_font))
        self.tv_box.add(self.bold)
        self.tv_box.add(self.stack)
        self.tv_box.add(self.spk_color)
        self.tv_box.add(self.logo)
        self.mode = Segmented([("otomatik", "Otomatik"), ("hdmi", "Uygulama içinde"), ("katman", "Katman")],
                              ctl.cfg.tv.mod)
        self.mode.setMaximumWidth(460)
        self.tv_box.add(field("Android TV görüntü modu", self.mode,
                              "Android TV uygulamasında görüntü siyah kalıyorsa ya da TV kendiliğinden PS5'in girişine "
                              "geçiyorsa Katman'ı seç: TV, PS5'i kendi HDMI girişinde gösterir, altyazı üstünde çıkar. "
                              "LG ve Samsung'da bu ayarın etkisi yok."))
        self.test_btn = button("TV'ye deneme gönder", "primary", ctl.tv_test)
        self.tv_box.add(hbox(self.test_btn, None))
        right.addWidget(self.tv_box)

        # --- bilgisayar ekranı ayarları
        g = ctl.cfg.gosterim
        self.pc_box = SectionCard("Bilgisayar ekranında", "Remote Play / chiaki penceresinin üstündeki katman ya da "
                                  "capture kart penceresi.", "monitor")
        self.pc_mode = combo([("overlay", "Oyun penceresinin üstüne katman (önerilen)"),
                              ("pencere", "Görüntüyü kendi penceresinde göster (capture kart)")], g.mod)
        self.font_name = QLineEdit(g.yazi_tipi)
        self.latency = QCheckBox("Sağ üstte gecikmeyi göster", g.gecikme_goster)
        self.pc_scale = slider(80, 200, self.scale.value())
        self.pc_bg = slider(0, 100, self.bg.value())
        self.pc_scale.valueChanged.connect(self.scale.setValue)
        self.scale.valueChanged.connect(self.pc_scale.setValue)
        self.pc_bg.valueChanged.connect(self.bg.setValue)
        self.bg.valueChanged.connect(self.pc_bg.setValue)
        self.pc_box.add(field("Gösterim", self.pc_mode))
        self.pc_box.add(field("Yazı tipi", self.font_name))
        self.pc_box.add(slider_row("Yazı boyutu", self.pc_scale, lambda v: f"{v / 100:.2f}×"))
        self.pc_box.add(slider_row("Arka plan koyuluğu", self.pc_bg, lambda v: f"%{v}"))
        self.pc_box.add(self.latency)
        right.addWidget(self.pc_box)
        right.addStretch(1)
        root.addStretch(1)

        self._save_timer = QTimer(self, singleShot=True, interval=350, timeout=self.save)
        for w in (self.size, self.scale, self.bg, self.bottom):
            w.valueChanged.connect(self._changed)
        for w in (self.place, self.shape, self.pc_mode):
            w.currentIndexChanged.connect(self._changed)
        self.tv_font.changed.connect(self._changed)
        for w in (self.bold, self.stack, self.latency, self.spk_color, self.fit, self.logo):
            w.toggled.connect(self._changed)
        self.colors.changed.connect(self._changed)
        self.mode.changed.connect(self._changed)
        self.font_name.editingFinished.connect(self._changed)
        self._target("tv")
        self._preview()

    def _main_zone(self):  # noqa: ANN202
        return next((b for b in self.ctl.cfg.bolgeler if b.ad == "altyazi"), None)

    def _view(self, v: str) -> None:
        """Ana ekran görünümü: ana ekranın sağ üstündeki seçimle aynı ayar."""
        home = self.window().pages.get("home") if hasattr(self.window(), "pages") else None
        if home is not None:
            home._set_style(v)
        else:
            cfg = self.ctl.edit_config()
            cfg.gosterim.ana_ekran = v
            self.ctl.apply_config(cfg)

    def _preset(self, key: str) -> None:
        st = next(p[3] for p in self.PRESETS if p[0] == key)
        for w in (self.bg, self.bold, self.shape):
            w.blockSignals(True)
        self.bg.setValue(st["background"])
        self.bold.setChecked(st["bold"])
        self.shape.setCurrentIndex(max(0, self.shape.findData(st["backgroundShape"])))
        for w in (self.bg, self.bold, self.shape):
            w.blockSignals(False)
        self.colors.setValue(st["textColor"])
        self.bold.update()
        self._changed()

    def _mark_preset(self) -> None:
        cur = {"background": self.bg.value(), "textColor": self.colors.current, "bold": self.bold.isChecked(),
               "backgroundShape": self.shape.currentData()}
        for key, card in self.style_cards.items():
            card.setChecked(next(p[3] for p in self.PRESETS if p[0] == key) == cur)

    def _target(self, v: str) -> None:
        self.tv_box.setVisible(v == "tv")
        self.pc_box.setVisible(v == "pc")

    def _changed(self, *_a) -> None:  # noqa: ANN002
        self._preview()
        self._save_timer.start()

    def _preview(self) -> None:
        place = self.place.currentData()
        fixed_size = place == "fixed" or not self.fit.isChecked()
        self.size_row.itemAt(1).widget().setEnabled(fixed_size)
        self.scale.setEnabled(self.fit.isChecked())
        self.bottom.setEnabled(place == "fixed")
        self.preview.set_style(placement=place, fontSize=self.size.value(), background=self.bg.value(),
                               bold=self.bold.isChecked(), textColor=self.colors.current,
                               bottomPercent=self.bottom.value(), backgroundShape=self.shape.currentData(),
                               lineScale=self.scale.value() / 100 if self.fit.isChecked() else 0,
                               font=self.tv_font.value())
        if not self.fit.isChecked() and place != "fixed":
            self.preview.set_style(placement="fixed" if place == "cover" else place)
        self._mark_preset()

    def save(self) -> None:
        cfg = self.ctl.edit_config()
        t = cfg.tv
        t.yazi_rengi = self.colors.current
        t.yazi_boyutu = self.size.value()
        t.alttan = self.bottom.value()
        t.yerlesim = self.place.currentData()
        t.zemin_sekli = self.shape.currentData()
        t.kalin = self.bold.isChecked()
        t.onceki_satirlar = self.stack.isChecked()
        t.yazi_tipi = self.tv_font.value()
        t.konusan_renk = self.spk_color.isChecked()
        t.logo = self.logo.isChecked()
        t.uydur = self.fit.isChecked()
        t.mod = self.mode.value() or t.mod
        main = next((b for b in cfg.bolgeler if b.ad == "altyazi"), None)
        if main is not None:
            main.yazi_olcek = self.scale.value() / 100
            main.kutu_opaklik = round(self.bg.value() / 100 * 255)
        cfg.gosterim.mod = self.pc_mode.currentData()
        cfg.gosterim.yazi_tipi = self.font_name.text().strip() or "Segoe UI Semibold"
        cfg.gosterim.gecikme_goster = self.latency.isChecked()
        self.ctl.apply_config(cfg)


# ============================================================================ Okuma alanı
class RegionsPage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        self.zones: list[BolgeCfg] = []
        _transparent(self)
        root = page_shell(self, "Okuma alanı", "Çoğu oyunda Otomatik yeterli: program altyazının yerini kendisi bulur "
                          "ve öğrenir. Bulamazsa hazır bir yer seç ya da kutuyu fareyle köşelerinden boyutlandır, "
                          "ortasından tutup taşı.", "regions")
        gta = SectionCard(accent=True, margins=16, spacing=6)
        gta.add(hbox(vbox(hbox(label("Tek tıkla GTA 6 için en iyi okuma", "h3"), Pill("ÖNERİLEN", "ok"), None),
                          label("Altyazının yeri kendiliğinden bulunur; alttaki görev yazısı, sol üstteki ipucu kutusu, "
                                "sağ üstteki bildirimler ve telefon mesajları da çevrilir.", "faint", wrap=True),
                          spacing=4), 16, button("GTA 6 için ayarla", "primary", self._gta6), spacing=0))
        root.addWidget(gta)
        self.extra = SectionCard("Ekrandaki başka yazıları da çevir", "Açık olan alanlar okunur. Boyut: Türkçenin o "
                                 "alanda İngilizceye göre büyüklüğü.", margins=16, spacing=8)
        self.extra_rows: dict[str, tuple] = {}
        names = {"altyazi": "Altyazı ve alttaki görev yazısı", "yardim": "İpucu kutusu (sol üst)",
                 "bildirim": "Bildirim ve görev (sağ üst)", "telefon": "Telefon mesajları (sağ)"}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        for i, z in enumerate(ctl.cfg.bolgeler):
            tg = QCheckBox(names.get(z.ad, z.ad), getattr(z, "aktif", True))
            sz = slider(80, 200, int(z.yazi_olcek * 100))
            sz.setFixedWidth(160)
            val = label(f"{z.yazi_olcek:.2f}×", "faint")
            sz.valueChanged.connect(lambda v, lb=val: lb.setText(f"{v / 100:.2f}×"))
            tg.toggled.connect(lambda _on: self._extra_changed())
            sz.sliderReleased.connect(self._extra_changed)
            self.extra_rows[z.ad] = (tg, sz)
            grid.addWidget(tg, i // 2, (i % 2) * 3)
            grid.addWidget(sz, i // 2, (i % 2) * 3 + 1)
            grid.addWidget(val, i // 2, (i % 2) * 3 + 2)
        self.extra.add(grid)
        others = [z for z in ctl.cfg.bolgeler if z.ad != "altyazi"]
        self.extra_bg = slider(0, 100, round((others[0].kutu_opaklik if others else 255) / 255 * 100))
        self.extra_bg.sliderReleased.connect(self._extra_changed)
        self.extra.add(slider_row("Ek alanlarda kutu zemini (İngilizceyi örten kutunun koyuluğu)", self.extra_bg,
                                  lambda v: f"%{v}"))
        root.addWidget(self.extra)
        self.chips = Chips([("__oto__", "Otomatik (önerilen)")] + [(k, k.split(" (")[0]) for k in PRESETS])
        self.chips.picked.connect(self._apply_preset_name)
        root.addWidget(self.chips)
        body = QHBoxLayout()
        body.setSpacing(16)
        left = Card(margins=14)
        self.canvas = RegionCanvas()
        self.canvas.setMinimumHeight(430)
        self.canvas.selected.connect(self.select)
        self.canvas.changed.connect(self._dirty)
        self.mask_cb = QCheckBox("Algılanan yazıyı kırmızı göster", True)
        self.mask_cb.toggled.connect(self._mask)
        left.add(hbox(Pill("Canlı görüntü", "ok"), None,
                      button("Görüntü al", "primary", ctl.grab_frame, "PS5'ten (ya da kaynaktan) bir kare al"),
                      button("Resim aç", None, self._open_image), spacing=10))
        left.add(self.canvas, 1)
        left.add(hbox(self.mask_cb, None, label("Kutuyu köşelerinden ya da kenarlarından çekerek boyutlandır.",
                                                 "faint")))
        # Son okunan ve çevrilen (GameTranslator)
        last = Card(inner=True, margins=12, spacing=4)
        self.last_en = label("Okunan yazı burada görünür", None, wrap=True)
        self.last_tr = label("Çevirisi burada görünür", None, wrap=True)
        self.last_tr.setStyleSheet(f"color:{T.A2}; font-weight: 700;")
        last.add(label("Son okunan ve çevrilen", "h3"))
        last.add(hbox(vbox(label("Oyunda (İngilizce)", "faint"), self.last_en, spacing=2), 20,
                      vbox(label("TV'de (Türkçe)", "faint"), self.last_tr, spacing=2), spacing=0))
        left.add(last)
        # Üst / Alt / Sol / Sağ kaydırıcıları (seçili bölge)
        self.edges = {k: slider(0, 100, 0) for k in ("ust", "alt", "sol", "sag")}
        eg = QGridLayout()
        eg.setHorizontalSpacing(24)
        eg.setVerticalSpacing(8)
        for i, (k, title) in enumerate((("ust", "Üst"), ("alt", "Alt"), ("sol", "Sol"), ("sag", "Sağ"))):
            eg.addLayout(slider_row(title, self.edges[k], lambda v: f"%{v}"), i // 2, i % 2)
            self.edges[k].valueChanged.connect(lambda _v, kk=k: self._edge(kk))
        self.center = QCheckBox("Ortada tut (sol ve sağ birlikte değişir)", True)
        left.add(eg)
        left.add(self.center)
        body.addWidget(left, 3)
        ctl.historyChanged.connect(self._on_read)
        self.canvas.changed.connect(self._edges_from_zone)

        right = Card(margins=16, spacing=12)
        right.setFixedWidth(330)
        self.list = QListWidget()
        self.list.setFixedHeight(130)
        self.list.currentRowChanged.connect(self.select)
        right.add(label("Bölgeler", "h2"))
        right.add(self.list)
        self.preset = QComboBox()
        self.preset.addItem("Hazır konum seç...")
        for k in PRESETS:
            self.preset.addItem(k)
        self.preset.activated.connect(self._apply_preset)
        right.add(hbox(button("+ Ekle", None, self._add), button("Sil", "danger", self._remove), None))
        right.add(self.preset)
        self.name = QLineEdit()
        self.name.editingFinished.connect(self._edit)
        self.kind = combo([("altyazi", "Diyalog altyazısı"), ("arayuz", "Arayüz / bildirim")], "altyazi")
        self.align = combo([("orta", "Ortalı"), ("sol", "Sola yaslı"), ("sag", "Sağa yaslı")], "orta")
        self.scale = slider(80, 200, 130)
        self.scale_l = label("", "faint")
        self.opacity = slider(0, 255, 255)
        self.color = QCheckBox("Renkli kelimeleri de oku")
        self.color.setToolTip("Sarı, mavi vurgulu sözcükler")
        for w in (self.kind, self.align):
            w.currentIndexChanged.connect(self._edit)
        for w in (self.scale, self.opacity):
            w.valueChanged.connect(self._edit)
        self.color.toggled.connect(self._edit)
        right.add(field("Ad", self.name))
        right.add(field("Tür", self.kind, "Diyalog: konuşma dili. Arayüz: kısa ve emir kipinde çeviri."))
        right.add(field("Hizalama", self.align))
        right.add(vbox(hbox(label("Türkçe yazı boyutu", "h3"), None, self.scale_l), self.scale, spacing=6))
        right.add(field("İngilizceyi kapatan kutu", self.opacity))
        right.add(self.color)
        right.lay.addStretch(1)
        self.save_btn = button("Kaydet", "primary", self.save)
        right.add(self.save_btn)
        body.addWidget(right)
        root.addLayout(body, 1)
        ctl.frameGrabbed.connect(self.on_frame)
        self.load()

    def _gta6(self) -> None:
        """GTA 6'nın bilinen alanları (programla gelen varsayılanlar); altyazının yeri yine kendiliğinden öğrenilir."""
        from .. import config as config_mod, paths
        cfg = self.ctl.edit_config()
        cfg.bolgeler = config_mod.load(paths.default_config()).bolgeler
        self.ctl.apply_config(cfg)
        self.load()
        for z in cfg.bolgeler:
            if z.ad in self.extra_rows:
                tg, sz = self.extra_rows[z.ad]
                for w in (tg, sz):
                    w.blockSignals(True)
                tg.setChecked(True)
                sz.setValue(int(z.yazi_olcek * 100))
                for w in (tg, sz):
                    w.blockSignals(False)
        self.window().toast.show_text("GTA 6 için en iyi okuma ayarlandı")

    def _extra_changed(self) -> None:
        cfg = self.ctl.edit_config()
        for z in cfg.bolgeler:
            if z.ad in self.extra_rows:
                tg, sz = self.extra_rows[z.ad]
                z.aktif = tg.isChecked()
                z.yazi_olcek = sz.value() / 100
            if z.ad != "altyazi":
                z.kutu_opaklik = round(self.extra_bg.value() / 100 * 255)
        self.ctl.apply_config(cfg)
        self.load()

    def load(self) -> None:
        import copy
        self.zones = copy.deepcopy(self.ctl.cfg.bolgeler)
        self.canvas.set_zones(self.zones)
        self._fill_list()
        self.select(0)

    def _fill_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for z in self.zones:
            self.list.addItem(QListWidgetItem(f"{z.ad}  ·  {'diyalog' if z.tur == 'altyazi' else 'arayüz'}"))
        self.list.blockSignals(False)

    def current(self) -> BolgeCfg | None:
        i = self.canvas.sel
        return self.zones[i] if 0 <= i < len(self.zones) else None

    def select(self, i: int) -> None:
        if not (0 <= i < len(self.zones)):
            return
        self.canvas.sel = i
        self.canvas.update()
        self.list.blockSignals(True)
        self.list.setCurrentRow(i)
        self.list.blockSignals(False)
        z = self.zones[i]
        for w in (self.name, self.kind, self.align, self.scale, self.opacity, self.color):
            w.blockSignals(True)
        self.name.setText(z.ad)
        self.kind.setCurrentIndex(max(0, self.kind.findData(z.tur)))
        self.align.setCurrentIndex(max(0, self.align.findData(z.hizalama)))
        self.scale.setValue(int(z.yazi_olcek * 100))
        self.opacity.setValue(z.kutu_opaklik)
        self.color.setChecked(z.renkli)
        for w in (self.name, self.kind, self.align, self.scale, self.opacity, self.color):
            w.blockSignals(False)
        self.scale_l.setText(f"{z.yazi_olcek:.2f}×")
        if hasattr(self, "edges"):
            self._edges_from_zone()
        self.chips.setValue(next((k for k, v in PRESETS.items()
                                  if [round(a, 2) for a in v[0]] == [round(float(a), 2) for a in z.alan]), None))

    def _edit(self, *_a) -> None:  # noqa: ANN002
        z = self.current()
        if not z:
            return
        z.ad = self.name.text().strip() or z.ad
        z.tur = self.kind.currentData()
        z.hizalama = self.align.currentData()
        z.capa = "alt" if z.alan[1] > 0.5 else "ust"
        z.yazi_olcek = self.scale.value() / 100
        z.kutu_opaklik = self.opacity.value()
        z.renkli = self.color.isChecked()
        self.scale_l.setText(f"{z.yazi_olcek:.2f}×")
        self._fill_list()
        self.list.setCurrentRow(self.canvas.sel)
        self.canvas.refresh_mask()
        self._dirty()

    def _on_read(self, it, _updated: bool) -> None:  # noqa: ANN001
        self.last_en.setText(it.english)
        self.last_tr.setText(it.text)

    def _edges_from_zone(self) -> None:
        z = self.current()
        if not z:
            return
        vals = {"sol": z.alan[0], "ust": z.alan[1], "sag": z.alan[2], "alt": z.alan[3]}
        for k, w in self.edges.items():
            w.blockSignals(True)
            w.setValue(round(vals[k] * 100))
            w.blockSignals(False)

    def _edge(self, k: str) -> None:
        z = self.current()
        if not z:
            return
        v = self.edges[k].value() / 100
        x0, y0, x1, y1 = [float(a) for a in z.alan]
        if k == "ust":
            y0 = min(v, y1 - 0.03)
        elif k == "alt":
            y1 = max(v, y0 + 0.03)
        elif k == "sol":
            x0 = min(v, x1 - 0.05)
            if self.center.isChecked():
                x1 = max(1 - x0, x0 + 0.05)
        else:
            x1 = max(v, x0 + 0.05)
            if self.center.isChecked():
                x0 = min(1 - x1, x1 - 0.05)
        z.alan = [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]
        self._edges_from_zone()
        self.canvas.update()
        self.canvas.refresh_mask()
        self._dirty()

    def _apply_preset_name(self, name: str) -> None:
        if name == "__oto__":                     # öğrenileni unut; yer yeniden kendiliğinden öğrenilir
            try:
                self.ctl.layout.forget(self.ctl.layout_key())
            except Exception:  # noqa: BLE001
                pass
            self.window().toast.show_text("Otomatik: altyazının yeri oynarken kendiliğinden bulunur ve öğrenilir")
            return
        if not self.current():
            return
        alan, tur, hiz, capa = PRESETS[name]
        z = self.current()
        z.alan, z.tur, z.hizalama, z.capa = list(alan), tur, hiz, capa
        self.select(self.canvas.sel)
        self.canvas.refresh_mask()
        self._fill_list()
        self._dirty()

    def _apply_preset(self, idx: int) -> None:
        if idx <= 0 or not self.current():
            return
        self._apply_preset_name(self.preset.itemText(idx))
        self.preset.setCurrentIndex(0)

    def _add(self) -> None:
        self.zones.append(BolgeCfg(ad=f"bolge{len(self.zones) + 1}", alan=[0.3, 0.4, 0.7, 0.55], tur="arayuz"))
        self.canvas.set_zones(self.zones)
        self._fill_list()
        self.select(len(self.zones) - 1)
        self._dirty()

    def _remove(self) -> None:
        if len(self.zones) <= 1:
            return
        self.zones.pop(self.canvas.sel)
        self.canvas.sel = 0
        self.canvas.set_zones(self.zones)
        self._fill_list()
        self.select(0)
        self._dirty()

    def _mask(self, on: bool) -> None:
        self.canvas.show_mask = on
        self.canvas.refresh_mask()

    def _dirty(self) -> None:
        self.save_btn.setText("Kaydet •")

    def _open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ekran görüntüsü aç", "", "Resimler (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            import cv2
            import numpy as np
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.on_frame(img)

    def on_frame(self, frame) -> None:  # noqa: ANN001
        if frame is not None:
            self.canvas.set_frame(frame)

    def save(self) -> None:
        cfg = self.ctl.edit_config()
        cfg.bolgeler = [z for z in self.zones]
        self.ctl.apply_config(cfg)
        self.save_btn.setText("Kaydedildi ✓")
        QTimer.singleShot(1500, lambda: self.save_btn.setText("Kaydet"))


# ============================================================================ Bağlantı (PS5, TV, kaynak, ikinci ekran)
class _ConnRow(QFrame):
    """Bağlantılar listesinin satırı: [ikon] Ad / ● durum   [Ayarla] (GameTranslator)."""

    def __init__(self, icon: str, title: str, slot):  # noqa: ANN001
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(14)
        lay.addWidget(IconTile(icon, 40, glow=False))
        self.title = label(title, "h3")
        self.pill = Pill("", "off")
        self.pill.setStyleSheet("background: transparent; border: 0; padding: 0;")
        lay.addLayout(vbox(self.title, self.pill, spacing=2), 1)
        self.btn = button("Ayarla", None, slot)
        lay.addWidget(self.btn)

    def set(self, state: str, text: str) -> None:
        self.pill.set(state, text)


class TvPage(QWidget):
    _fwText = Signal(str)                      # arka plan iş parçacığından güvenlik duvarı durumu
    _fwDone = Signal()

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "Bağlantı", "PS5, TV ve görüntü kaynağı. Oyun TV'de HDMI'dan gecikmesiz oynanır; "
                          "bilgisayar PS5'e arka planda bağlanıp altyazıyı okur ve Türkçesini TV'ye gönderir.", "swap")
        cfg = ctl.cfg

        # --- bağlantılar özeti
        conns = SectionCard("Bağlantılar", margins=16, spacing=4)
        self.r_ps5 = _ConnRow("ps", "PS5", self._open_ps5)
        self.r_tv = _ConnRow("tv", "TV", lambda: self.ip.setFocus())
        conns.add(self.r_ps5)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{T.BORDER};")
        conns.add(sep)
        conns.add(self.r_tv)
        root.addWidget(conns)

        # --- görüntü kaynağı
        src = SectionCard("Görüntü kaynağı", "Oyun görüntüsünün nereden okunacağı. TV'de oynuyorsan PS5 (ikinci hesap) "
                          "seç: chiaki-ng ya da başka program gerekmez.", "ps")
        self.src_group = RadioGroup(on_change=lambda _v: self._src_vis())
        self.src_cards = {}
        for value, title, desc in (
                ("remoteplay", "PS5 (ikinci hesap)", "Bilgisayar PS5'e arka planda bağlanır. Kumandan TV'den kopmaz."),
                ("pencere", "chiaki-ng / Remote Play penceresi", "Oyunu bilgisayar ekranında oynarken."),
                ("capture", "Yakalama kartı", "Elgato ya da USB capture kart."),
                ("video", "Video dosyası", "Deneme için kayıtlı bir oyun videosu.")):
            card = self.src_group.add(value, RadioCard(title, desc))
            self.src_cards[value] = card
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, card in enumerate(self.src_cards.values()):
            grid.addWidget(card, i // 2, i % 2)
        src.add(grid)
        self.where = combo([("tv", "TV'de oynuyorum (Türkçe yalnız TV'de)"),
                            ("ikisi", "TV'de ve bilgisayarda"), ("monitor", "Bilgisayar ekranında")],
                           cfg.kaynak.oyun_yeri)
        self.ps5_auto = QCheckBox("PS5 açılınca çeviri kendiliğinden başlasın", cfg.ps5.acilinca_baslat)
        src.add(hbox(field("Oyunu nerede oynuyorsun", self.where), 16,
                     vbox(None, self.ps5_auto, spacing=0), None, spacing=0))
        self.win_name = QLineEdit(cfg.kaynak.pencere_adi)
        self.chiaki = QLineEdit(cfg.kaynak.chiaki_yolu)
        self.chiaki.setPlaceholderText(ctl.chiaki_path() or "chiaki-ng bulunamadı")
        self.win_box = QWidget()
        self.win_box.setLayout(hbox(field("Pencere başlığında geçen", self.win_name,
                                          "chiaki-ng için \"chiaki\", resmi uygulama için \"PS Remote Play\"."),
                                    field("chiaki-ng programı", hbox(self.chiaki, button("Gözat", None, self._browse),
                                                                     button("İndir", "ghost",
                                                                            lambda: webbrowser.open(CHIAKI_DOWNLOAD)))),
                                    spacing=16))
        src.add(self.win_box)
        # --- capture kart (Elgato, AVerMedia, USB HDMI): aygıt seçimi, çözünürlük, ses, önizleme
        k = cfg.kaynak
        self.cap_idx = QComboBox()
        self.cap_idx.addItem(f"Aygıt {k.capture_cihaz}", k.capture_cihaz)
        self.cap_find = button("Aygıtları ara", None, self._find_capture)
        self.cap_res = combo([("1920x1080x60", "1080p · 60 kare (önerilen)"), ("1920x1080x30", "1080p · 30 kare"),
                              ("1280x720x60", "720p · 60 kare (eski kartlar)"), ("3840x2160x30", "4K · 30 kare")],
                             f"{k.capture_genislik}x{k.capture_yukseklik}x{k.capture_fps}")
        self.cap_sound = QCheckBox("Capture kartın sesini hoparlöre aktar (bilgisayarda oynarken)", k.capture_ses)
        self.cap_audio = QComboBox()
        self.cap_audio.addItem("Kendiliğinden bul (Elgato, AVerMedia, USB Video…)", "")
        if k.capture_ses_cihaz:
            self.cap_audio.addItem(k.capture_ses_cihaz, k.capture_ses_cihaz)
            self.cap_audio.setCurrentIndex(1)
        self.cap_prev = QLabel("Önizleme için Aygıtları ara'ya, sonra Önizle'ye bas.")
        self.cap_prev.setObjectName("faint")
        self.cap_prev.setAlignment(Qt.AlignCenter)
        self.cap_prev.setMinimumHeight(140)
        self.cap_prev.setStyleSheet(f"background:{T.SURFACE2}; border:1px solid {T.BORDER}; border-radius:12px;")
        self.cap_box = QWidget()
        cl = QVBoxLayout(self.cap_box)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        how = label("Bağlantı: PS5 → capture kartın HDMI IN girişi · kartın HDMI OUT'u → TV (görüntü TV'ye gecikmesiz "
                    "geçer) · kartın USB'si → bilgisayar. Oyunu TV'de oynuyorsan Türkçe TV uygulamasında çıkar; "
                    "bilgisayarda oynuyorsan görüntü ve Türkçe bu programın penceresinde birlikte görünür.", "faint",
                    wrap=True)
        cl.addWidget(how)
        cl.addLayout(hbox(field("Capture kart", hbox(self.cap_idx, self.cap_find, button("Önizle", None,
                                                                                         self._preview_capture),
                                                    spacing=8)), 16, field("Görüntü", self.cap_res), spacing=0))
        cl.addLayout(hbox(self.cap_sound, None))
        cl.addLayout(hbox(field("Ses girişi", hbox(self.cap_audio, button("Ses girişlerini ara", None,
                                                                         self._find_audio), spacing=8)), None))
        cl.addWidget(self.cap_prev)
        self.video = QLineEdit(cfg.kaynak.dosya)
        self.video_box = QWidget()
        self.video_box.setLayout(hbox(field("Video dosyası", self.video), spacing=0))
        src.add(self.cap_box)
        src.add(self.video_box)
        src.add(hbox(None, button("Kaydet", "primary", self._save_source)))
        root.addWidget(src)

        demo = SectionCard("Deneme modu", "Programın tamamını örnek görüntüyle dene: konsol, hesap ya da TV gerekmez. "
                           "Örnek altyazılar okunur, çevrilir; bilgisayarda kendi penceresinde, TV bağlıysa TV'de de "
                           "görünür.", "play")
        demo.add(hbox(button("▷  Deneme modunu başlat", "primary", lambda: self.window().pages["home"]._demo()), None))
        root.addWidget(demo)

        # --- TV kurulumu
        steps = SectionCard("TV", "Türkçe altyazı TV'de oyunun üstünde görünür. Önce TV'de bir kerelik hazırlık, sonra "
                            "Bağlan.", "tv")
        from .. import rehber
        self.brand = combo(rehber.TV_BRANDS, cfg.tv.marka)
        self.brand.currentIndexChanged.connect(self._brand_changed)
        steps.add(hbox(label("TV markası", "h3"), self.brand, None, button("Resimli anlat", None, self._open_guide),
                       spacing=14))
        self.howto = label("", "muted", wrap=True)
        self.howto.setTextFormat(Qt.RichText)
        steps.add(self.howto)
        self.ip = QLineEdit(cfg.tv.ip)
        self.ip.setPlaceholderText("TV'nin IP adresi, ör. 192.168.1.40")
        self.scan_btn = button("Ağda ara", None, self._scan)
        self.found = QComboBox()
        self.found.hide()
        self.found.currentIndexChanged.connect(lambda i: self.ip.setText(self.found.itemData(i) or self.ip.text()))
        steps.add(hbox(self.ip, self.scan_btn, self.found, spacing=10))
        self.mode = combo([("otomatik", "Otomatik (önerilen)"), ("katman", "Oyunun üstüne katman"),
                           ("hdmi", "Yedek mod: HDMI uygulama içinde")], cfg.tv.mod)
        self.auto = QCheckBox("Çeviri başlayınca TV'yi kendiliğinden bağla", cfg.tv.otomatik)
        self.mode_box = field("Mod", self.mode)
        self.lg_pass = QLineEdit(cfg.tv.lg_parola)
        self.lg_pass.setPlaceholderText("Developer Mode ekranındaki parola (ör. A1B2C3)")
        self.lg_box = QWidget()
        self.lg_box.setLayout(field("LG parola (passphrase)", self.lg_pass,
                                    "Developer Mode uygulamasında Key Server açıkken ekranda görünür."))
        self.ss_profile = QLineEdit(cfg.tv.samsung_profil)
        self.ss_tizen = QLineEdit(cfg.tv.tizen_yolu)
        self.ss_tizen.setPlaceholderText("Boş bırak: Tizen Studio gerekmez")
        self.ss_box = QWidget()
        self.ss_box.setLayout(hbox(field("Tizen Studio klasörü (gelişmiş, isteğe bağlı)", self.ss_tizen),
                                   field("Sertifika profili (yalnız Tizen Studio ile)", self.ss_profile),
                                   spacing=14))
        mode_w = QWidget()
        mode_w.setLayout(self.mode_box)
        self.mode_w = mode_w
        steps.add(hbox(mode_w, self.lg_box, self.ss_box, None, vbox(None, self.auto, spacing=0), spacing=16))
        self.connect_btn = button("Bağlan, kur ve başlat", "primary", self._connect)
        self.test_btn = button("Deneme altyazısı gönder", None, ctl.tv_test)
        steps.add(hbox(self.connect_btn, self.test_btn, None))
        self.status = label("", "muted", wrap=True)
        steps.add(self.status)
        pair = Card(inner=True, margins=14)
        pair.add(label("Gelişmiş: yalnız TV'de USB hata ayıklama yoksa (kablosuz eşleştirme)", "h3"))
        pair.add(label("TV'de Kablosuz hata ayıklama › Eşleştirme koduyla cihaz eşleştir. Açılan küçük penceredeki "
                       "adres:port'u (ana ekrandaki değil, port farklıdır) ve 6 haneli kodu yaz; pencere açıkken "
                       "Eşleştir'e bas.", "faint", wrap=True))
        self.pair_addr = QLineEdit()
        self.pair_addr.setPlaceholderText("192.168.1.40:37123")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("123456")
        self.pair_code.setFixedWidth(110)
        pair.add(hbox(self.pair_addr, self.pair_code, button("Eşleştir", None, self._pair), spacing=10))
        steps.add(pair)
        self.pair_card = pair
        root.addWidget(steps)

        # --- ikinci ekran
        url = ctl.server_url("ekran")
        second = SectionCard("TV'm desteklenmiyor: ikinci ekran", "Çeviriyi bir telefonda ya da tablette büyük yazıyla "
                             "göster: cihaz bu bilgisayarla aynı Wi-Fi'deyken kameradan QR kodu okut, cihazı TV'nin önüne "
                             "koy. Kurulum gerekmez, internete çıkılmaz.", "phone")
        qr = QrCode(150)
        qr.setData(url)
        url_l = label(url, "mono", wrap=True)
        second.add(hbox(vbox(url_l, hbox(button("Kopyala", None, lambda: self._copy(url)),
                                         button("Burada aç", None, lambda: webbrowser.open(url)), None, spacing=8),
                             label("Sayfa beyaz mı kalıyor? Adresi QR okuyucu uygulamasının içinde değil, Chrome ya da "
                                   "Safari'de aç; cihaz misafir Wi-Fi'ye bağlı olmasın.", "faint", wrap=True),
                             None, spacing=10), 16, qr, spacing=0))
        root.addWidget(second)

        # --- güvenlik duvarı
        fw = SectionCard("Bağlantı izni (güvenlik duvarı)", "TV ya da telefon bu bilgisayara bağlanamıyorsa çoğu zaman "
                         "sebep Windows güvenlik duvarıdır. Düğme yalnız ev ağından (Özel ağ) gelen bağlantılara izin "
                         "verir; ağ 'Ortak' görünüyorsa onu da 'Özel' yapar. Windows bir kez yönetici izni ister.",
                         "check")
        self.fw_state = label("", "faint", wrap=True)
        self.fw_btn = button("İzin ver", "primary", self._firewall)
        fw.add(hbox(self.fw_btn, button("Durumu yenile", "ghost", self._fw_refresh), None, spacing=10))
        fw.add(self.fw_state)
        root.addWidget(fw)
        root.addStretch(1)

        self.src_group.set(cfg.kaynak.tur)
        self._src_vis()
        ctl.tvStatus.connect(self.on_status)
        ctl.tvFound.connect(self.on_found)
        ctl.ps5Status.connect(lambda *_a: self._ps5_row())
        self.on_status(*ctl.tv_state)
        self._ps5_row()
        self._brand_changed()
        self._fwText.connect(self.fw_state.setText)
        self._fwDone.connect(self._fw_finished)
        self._fw_refresh()

    EXTRA = {
        "android": "",
        "lg": "<i>LG ve Samsung başka uygulamanın üstüne çizmeye izin vermez: PS5'in HDMI görüntüsü bizim TV "
              "uygulamasının içinde açılır ve altyazı üstüne çizilir.</i>",
        "samsung": "<i>Gelişmiş: Tizen Studio'yla kurmak istersen klasörünü ve sertifika profilini aşağıya yaz.</i>",
    }
    GUIDE_KEYS = {"android": "google-tv", "lg": "lg", "samsung": "samsung"}

    # --------------------------------------------------------------- kaynak, PS5
    def _src_vis(self) -> None:
        v = self.src_group.value()
        self.win_box.setVisible(v == "pencere")
        self.cap_box.setVisible(v == "capture")
        self.video_box.setVisible(v == "video")
        self.ps5_auto.setVisible(v == "remoteplay")

    def _ps5_row(self) -> None:
        p = self.ctl.cfg.ps5
        if p.anahtar:
            state, msg = getattr(self.ctl, "rp_state", ("", ""))
            dot = {"bagli": "ok", "baglaniyor": "warn", "kopuk": "bad"}.get(state, "ok")
            self.r_ps5.set(dot, msg or f"Eşleşti ({p.ad or 'PS5'} · {p.ip})")
        else:
            self.r_ps5.set("off", "Eşli değil: ikinci PSN hesabıyla giriş ve 8 haneli kod")

    def _open_ps5(self) -> None:
        from .ps5_dialog import Ps5Dialog
        Ps5Dialog(self.ctl, self).exec()
        self.sync_source()
        self.ctl._check_source()
        self._ps5_row()

    def sync_source(self) -> None:
        """Ayarlar başka yerden değiştiyse (PS5 eşlendi) seçimleri güncelle; eski seçim Kaydet'le geri yazılmasın."""
        self.src_group.set(self.ctl.cfg.kaynak.tur)
        i = self.where.findData(self.ctl.cfg.kaynak.oyun_yeri)
        if i >= 0:
            self.where.setCurrentIndex(i)
        self._src_vis()

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        self.sync_source()
        super().showEvent(e)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "chiaki-ng programını seç",
                                              "/Applications" if sys.platform == "darwin" else "",
                                              "Program (*.app *.exe);;Tümü (*)")
        if path:
            self.chiaki.setText(path)

    def _save_source(self) -> None:
        cfg = self.ctl.edit_config()
        cfg.kaynak.tur = self.src_group.value() or cfg.kaynak.tur
        cfg.kaynak.oyun_yeri = self.where.currentData()
        cfg.ps5.acilinca_baslat = self.ps5_auto.isChecked()
        cfg.kaynak.pencere_adi = self.win_name.text().strip() or "chiaki"
        cfg.kaynak.chiaki_yolu = self.chiaki.text().strip()
        cfg.kaynak.capture_cihaz = int(self.cap_idx.currentData() or 0)
        w, h, fps = (int(x) for x in (self.cap_res.currentData() or "1920x1080x60").split("x"))
        cfg.kaynak.capture_genislik, cfg.kaynak.capture_yukseklik, cfg.kaynak.capture_fps = w, h, fps
        cfg.kaynak.capture_ses = self.cap_sound.isChecked()
        cfg.kaynak.capture_ses_cihaz = self.cap_audio.currentData() or ""
        if cfg.kaynak.tur == "capture" and cfg.gosterim.mod != "pencere" and cfg.kaynak.oyun_yeri != "tv":
            cfg.gosterim.mod = "pencere"          # capture kartta katmanın altında oyun penceresi yok
        cfg.kaynak.dosya = self.video.text().strip()
        self.ctl.apply_config(cfg)
        self.ctl._check_source()
        self.window().toast.show_text("Görüntü kaynağı kaydedildi")

    def _copy(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.window().toast.show_text("Adres kopyalandı")

    # --------------------------------------------------------------- capture kart
    def _find_capture(self) -> None:
        """Aygıtları arka planda arar (her biri kısa süre açılır); sonuç gelince listeyi doldurur."""
        import threading
        from PySide6.QtCore import QMetaObject
        self.cap_find.setEnabled(False)
        self.cap_find.setText("Aranıyor…")

        def work() -> None:
            from ..capture import list_capture_devices
            try:
                self._cap_found = list_capture_devices()
            except Exception:  # noqa: BLE001
                self._cap_found = []
            QMetaObject.invokeMethod(self, "_capture_listed", Qt.QueuedConnection)

        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def _capture_listed(self) -> None:
        found = getattr(self, "_cap_found", [])
        cur = int(self.cap_idx.currentData() or 0)
        self.cap_idx.clear()
        for d in found:
            tag = " · capture kart" if d["capture"] else ""
            self.cap_idx.addItem(f"{d['name']} ({d['width']}×{d['height']}){tag}", d["index"])
        if not found:
            self.cap_idx.addItem("Aygıt bulunamadı (kart takılı mı, başka program kullanıyor mu?)", cur)
        best = next((i for i, d in enumerate(found) if d["capture"]), None)
        keep = next((i for i, d in enumerate(found) if d["index"] == cur), None)
        if keep is not None and (found[keep]["capture"] or best is None):
            self.cap_idx.setCurrentIndex(keep)          # kayıtlı aygıt hâlâ yerinde
        else:
            self.cap_idx.setCurrentIndex(best or 0)     # adı capture karta benzeyen ilk aygıt
        self.cap_find.setEnabled(True)
        self.cap_find.setText("Aygıtları ara")

    def _preview_capture(self) -> None:
        from PySide6.QtGui import QImage, QPixmap
        from ..capture import grab_preview
        w, h, _fps = (int(x) for x in (self.cap_res.currentData() or "1920x1080x60").split("x"))
        frame = grab_preview(int(self.cap_idx.currentData() or 0), w, h)
        if frame is None:
            self.cap_prev.setText("Kare alınamadı: kart takılı mı, PS5 açık mı? Çeviri sürüyorsa önce durdur.")
            return
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy()
        self.cap_prev.setPixmap(QPixmap.fromImage(img).scaledToHeight(220, Qt.SmoothTransformation))
        self.cap_prev.setMinimumHeight(224)

    def _find_audio(self) -> None:
        try:
            from ..audio import list_inputs
            inputs = list_inputs()
        except Exception as e:  # noqa: BLE001
            self.window().toast.show_text(f"Ses girişleri okunamadı: {e}")
            return
        cur = self.cap_audio.currentData() or ""
        self.cap_audio.clear()
        self.cap_audio.addItem("Kendiliğinden bul (Elgato, AVerMedia, USB Video…)", "")
        for _i, name in inputs:
            self.cap_audio.addItem(name, name)
        i = self.cap_audio.findData(cur)
        self.cap_audio.setCurrentIndex(max(0, i))

    # --------------------------------------------------------------- TV
    def _open_guide(self) -> None:
        win = self.window()
        win.go("guide")
        page = win.pages.get("guide")
        key = self.GUIDE_KEYS[self.brand.currentData()]
        if page is not None:
            idx = next((i for i, g in enumerate(page.guides) if g["key"] == key), 0)
            page.show_guide(idx)

    def _brand_changed(self, *_a) -> None:  # noqa: ANN002
        from .. import rehber
        from ..tv import local_ip
        b = self.brand.currentData()
        text = rehber.brief_html(rehber.TV_STEPS[b])
        if b == "samsung":
            try:
                ip = local_ip()
            except OSError:
                ip = "ağ bağlantısı yok"
            text = f"Bu bilgisayarın IP'si (Host PC IP): <b>{ip}</b><br>" + text
        if self.EXTRA[b]:
            text += "<br>" + self.EXTRA[b]
        self.howto.setText(text)
        self.mode_w.setVisible(b == "android")
        self.pair_card.setVisible(b == "android")
        self.lg_box.setVisible(b == "lg")
        self.ss_box.setVisible(b == "samsung")

    def _save_common(self) -> None:
        cfg = self.ctl.edit_config()
        cfg.tv.ip = self.ip.text().strip()
        cfg.tv.marka = self.brand.currentData()
        cfg.tv.lg_parola = self.lg_pass.text().strip()
        cfg.tv.samsung_profil = self.ss_profile.text().strip() or "gta6"
        cfg.tv.tizen_yolu = self.ss_tizen.text().strip()
        cfg.tv.mod = self.mode.currentData()
        cfg.tv.otomatik = self.auto.isChecked()
        self.ctl.apply_config(cfg)

    def _connect(self) -> None:
        if not self.ip.text().strip():
            self.status.setText("Önce TV'nin IP adresini yaz ya da \"Ağda ara\"ya bas.")
            return
        self._save_common()
        self.ctl.tv_connect(self.ip.text().strip(), force_install=True)

    def _scan(self) -> None:
        self._save_common()                    # tarama seçili markanın portuna göre yapılır
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Aranıyor...")
        self.ctl.tv_scan()

    def on_found(self, found: list) -> None:
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Ağda ara")
        self.found.clear()
        for host, kind in found:
            self.found.addItem(f"{host} ({kind})", host)
        self.found.setVisible(bool(found))
        if found:
            self.ip.setText(found[0][0])
            self.status.setText(f"{len(found)} cihaz bulundu. \"Bağlan, kur ve başlat\"a bas.")
        else:
            self.status.setText("TV bulunamadı. TV açık mı, USB hata ayıklama açık mı? Yeni Google TV'lerde "
                                "Kablosuz hata ayıklama ile eşleştir.")

    def _pair(self) -> None:
        if self.pair_addr.text().strip() and self.pair_code.text().strip():
            self.ctl.tv_pair(self.pair_addr.text().strip(), self.pair_code.text().strip())

    def _firewall(self) -> None:
        self.fw_btn.setEnabled(False)
        self._fwText.emit("Windows yönetici izni soruyor: açılan pencerede 'Evet' de...")
        self.ctl.firewall_allow(done=lambda msg: (self._fwText.emit(msg), self._fwDone.emit()))

    def _fw_finished(self) -> None:
        self.fw_btn.setEnabled(True)
        QTimer.singleShot(500, self._fw_refresh)

    def _fw_refresh(self) -> None:
        import threading

        def run() -> None:
            st = self.ctl.firewall_status()
            text = {"tamam": "✓ İzin verilmiş.",
                    "eksik": "İzin yok: TV bağlanamayabilir. \"İzin ver\"e bas.",
                    "ortak": "Bu bilgisayarın ağı 'Ortak' görünüyor; TV bağlanamaz. \"İzin ver\"e bas: ev ağını "
                             "'Özel' yapıp izni de ekler.",
                    "bilinmiyor": "Durum okunamadı. TV bağlanmıyorsa \"İzin ver\"e bas."}[st]
            self._fwText.emit(text)
        threading.Thread(target=run, daemon=True).start()

    def on_status(self, state: str, msg: str) -> None:
        color = {"bagli": T.OK, "hata": T.BAD, "onay": T.INFO, "baglaniyor": T.WARN}.get(state, T.MUTED)
        if msg:
            self.status.setText(f"<span style='color:{color}'>●</span> {msg}")
        self.connect_btn.setEnabled(state not in ("baglaniyor", "onay"))
        brand = {"android": "Android TV", "lg": "LG webOS", "samsung": "Samsung Tizen"}.get(self.ctl.cfg.tv.marka, "TV")
        dot, text = {"bagli": ("ok", "Bağlı"), "baglaniyor": ("warn", "Bağlanıyor"), "onay": ("info", "Onay bekliyor"),
                     "hata": ("bad", "Hata")}.get(state, ("warn" if self.ctl.cfg.tv.ip else "off", "Bağlantı bekleniyor"
                                                          if self.ctl.cfg.tv.ip else "Kurulmadı"))
        self.r_tv.set(dot, f"{brand} ({text})")


# ============================================================================ Çeviri ve paketler
_ABBR_SKIP = {"of", "the", "and", "+", "-", "–"}


def _abbr(title: str) -> str:
    words = [w for w in title.replace(":", " ").split() if w.lower() not in _ABBR_SKIP]
    if not words:
        return "?"
    out = "".join(w[0] for w in words if w[0].isalnum())[:3].upper()
    return out or title[:3].upper()


class _PackTile(QFrame):
    """Oyun paketi kartı: kısaltma rozeti, ad, satır sayısı (CouchSubs)."""

    def __init__(self, title: str, count: int, extra: str = ""):
        super().__init__()
        self.setObjectName("radioCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        badge = label(_abbr(title), "h3")
        badge.setFixedSize(46, 46)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background:{T.SURFACE3}; border-radius: 12px; color:{T.A2}; font-size: 9.5pt;")
        lay.addWidget(badge)
        lay.addLayout(vbox(label(title, "h3"), label(f"{count:,} satır".replace(",", ".") + extra, "faint"), spacing=2),
                      1)


class TranslationPage(QWidget):
    ENGINES = [
        ("yok", "Ücretsiz (bu bilgisayarda)", "Kurulacak bir şey yok. İnternetsiz, kotasız; çeviri bu bilgisayarda yapılır."),
        ("gemini", "Google Gemini", "Daha doğal çeviri; argo ve espriyi iyi anlar. Ücretsiz bir Google anahtarı yeter."),
        ("claude", "Claude", "En iyi kalite; hikâye bağlamını ve karakterlerin üslubunu en iyi tutturan. Ücretli, kendi "
                             "anahtarın."),
        ("deepl", "DeepL", "Ünlü çeviri motoru; ücretsiz planda ayda 500 bin karakter."),
        ("yerelai", "Yerel yapay zekâ (Ollama / LM Studio)", "Kendi bilgisayarında çalışan model; ücretsiz ve internetsiz."),
    ]

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        c = ctl.cfg.ceviri
        _transparent(self)
        root = page_shell(self, "Çeviri ve paketler", "Hazır oyun paketinde olan satır anında gelir. Olmayan satırları "
                          "seçtiğin çeviri motoru çevirir; her çeviri önbelleğe yazılır, aynı yazı tekrar çıkınca anında "
                          "gelir.", "translate")

        # --- oyun paketleri
        packs = SectionCard("Oyun paketleri", "Bazı oyunlar için hazır Türkçe çeviriler. Pakette bulunan satır, çeviri "
                            "motoruna gitmeden hemen görünür (0 ms).", "check", accent=True)
        self.packs_pill = Pill("", "ok")
        self.packs_on = QCheckBox("Aktif", getattr(c, "paket_kullan", True))
        self.packs_on.toggled.connect(lambda _on: self.save())
        packs.add_right(self.packs_on)
        packs.add_right(self.packs_pill)
        self.game_pick = QComboBox()
        self.game_pick.addItem("Otomatik (oyun ilk birkaç cümleden anlaşılır)", "")
        self.game_pick.activated.connect(self._pick_game)
        packs.add(hbox(label("Oynadığın oyun", "h3"), self.game_pick, None, spacing=12))
        packs.add(label("Otomatik'te oyun ilk birkaç cümleden anlaşılır. Oyunu seçersen çeviri ilk cümleden itibaren "
                        "paketten gelir.", "faint", wrap=True))
        self.cache_l = label("", "faint")
        self.pack_grid_w = QWidget()
        _transparent(self.pack_grid_w)
        self.pack_grid = QGridLayout(self.pack_grid_w)
        self.pack_grid.setContentsMargins(0, 0, 0, 0)
        self.pack_grid.setSpacing(10)
        packs.add(self.pack_grid_w)
        self.packs_l = label("", "muted", wrap=True)
        packs.add(self.packs_l)
        from ..packs import CATALOG
        self.pack_combo = QComboBox()
        for pid, title in CATALOG:
            self.pack_combo.addItem(title, pid)
        self.pack_dl = button("Hazır paketi indir", "primary", self._download_pack)
        packs.add(hbox(self.pack_combo, self.pack_dl, button("Listeyi yenile", "ghost", ctl.load_pack_catalog), None,
                       button("Paket yükle (.json, .gz)", None, self._add_pack), spacing=10))
        packs.add(hbox(self.cache_l, None, button("Önbelleği paket olarak kaydet", "ghost", self._export_pack),
                       button("Klasörü aç", "ghost", self._open_data), spacing=8))
        packs.add(label("Paketler bu projenin GitHub sayfasından iner; her 6 saatte bir CouchSubs (GTA 6 dahil) ve "
                        "GameTranslator'dan güncellenir. GTA 6 paketi kurulumla birlikte de gelir.", "faint", wrap=True))
        ctl.packCatalog.connect(self._on_catalog)
        ctl.load_pack_catalog()
        root.addWidget(packs)

        # --- oyun metni: GTA 6'nın İngilizce satırlarıyla okuma düzeltme (kullanıcı kaynağından indirir)
        script = SectionCard("GTA 6 oyun metni", "Oyundaki İngilizce satırların tamamı (yaklaşık 460 bin). Okunan satırda "
                             "bir iki harf hatası varsa gerçek satırla düzeltilir: hazır paketin Türkçesi bulunur, yapay "
                             "zekâya hatasız İngilizce gider.", "translate", margins=16)
        self.script_on = QCheckBox("Açık", getattr(c, "oyun_metni", True))
        self.script_on.toggled.connect(lambda on: (self.save(), ctl.engine and (
            setattr(ctl.engine.cfg, "oyun_metni", on), ctl.engine.load_script())))
        script.add_right(self.script_on)
        self.script_l = label("", "muted", wrap=True)
        self.script_dl = button("İndir (~40 MB)", "primary", self._script_download)
        self.script_rm = button("Sil", "ghost", self._script_remove)
        script.add(hbox(self.script_l, None, self.script_dl, self.script_rm, spacing=8))
        script.add(label("Kaynak: github.com/psviethoa/gta6-text-en (Xbox 1.0.2.1 metin dökümü, CyberLeek). Program bu "
                         "metni dağıtmaz; İndir'e basınca doğrudan kaynağından iner ve yalnız bu bilgisayarda durur.",
                         "faint", wrap=True))
        root.addWidget(script)
        self._script_status()

        # --- motor seçimi
        root.addLayout(vbox(label("Çeviri motoru", "h1"),
                            label("Pakette olmayan satırlar için. Herkes kendi anahtarını kullanır; anahtar yalnız bu "
                                  "bilgisayarda saklanır.", "muted", wrap=True), spacing=2))
        self.qual_group = RadioGroup(on_change=lambda _v: self._vis())
        self.cards: dict[str, RadioCard] = {}
        self.more = Collapsible("Diğer çeviri motorları")
        for value, title, desc in self.ENGINES:
            card = self.qual_group.add(value, RadioCard(title, desc))
            self.cards[value] = card
            (self.more.add if value in ("deepl", "yerelai") else root.addWidget)(card)
        root.addWidget(self.more)
        import webbrowser as _wb
        # Gemini
        self.gem = QLineEdit(c.gemini_anahtar)
        self.gem.setEchoMode(QLineEdit.Password)
        self.gem.setPlaceholderText("Gemini API anahtarı")
        self.key_rows: dict[str, tuple] = {}
        self.cards["gemini"].add(hbox(self.gem, button("Kaydet ve Dene", "primary", self._save_try), spacing=8))
        self.cards["gemini"].add(self._key_row("gemini", self.gem))
        self.gem_model = combo([("gemini-2.5-flash", "Hızlı ve ucuz (önerilen)"),
                                ("gemini-2.5-pro", "En iyi kalite (daha yavaş, ücretsiz kotası az)")], c.gemini_model)
        self.cards["gemini"].add(hbox(label("Model", "h3"), self.gem_model, None, spacing=12))
        self.cards["gemini"].add(label("Altyazı metni Google'a gönderilir; ücretsiz anahtarda Google bu metni ürünlerini "
                                       "geliştirmek için kullanabilir. Yalnızca oyunun altyazıları gönderilir. Ücretsiz "
                                       "anahtarın dakika başına bir sınırı var; sınır dolunca o satır ücretsiz çeviriyle "
                                       "çevrilir.", "faint", wrap=True))
        self.cards["gemini"].add(hbox(button("Ücretsiz Gemini anahtarı al ›", "link",
                                             lambda: _wb.open(self._key_url("gemini"))), None))
        # Claude
        self.key = QLineEdit(c.claude_anahtar)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-...  (console.anthropic.com)")
        self.model = combo([("claude-opus-5-5", "Claude Opus 5.5 (en iyi kalite)"),
                            ("claude-haiku-5-5", "Claude Haiku 5.5 (daha hızlı ve ucuz)")], c.claude_model)
        self.fastmode = QCheckBox("Hızlı mod (Opus 5.5: ~2.5 kat hızlı, 2 kat fiyat)", c.claude_hizli_mod)
        self.cards["claude"].add(hbox(self.key, button("Kaydet ve Dene", "primary", self._save_try), spacing=8))
        self.cards["claude"].add(self._key_row("claude", self.key))
        self.cards["claude"].add(hbox(self.model, 12, self.fastmode, None, spacing=0))
        self.cards["claude"].add(hbox(button("Claude anahtarı al ›", "link", lambda: _wb.open(self._key_url("claude"))),
                                      None))
        # DeepL
        self.deepl = QLineEdit(c.deepl_anahtar)
        self.deepl.setEchoMode(QLineEdit.Password)
        self.deepl.setPlaceholderText("DeepL anahtarı (ücretsiz planda sonu :fx)")
        self.cards["deepl"].add(hbox(self.deepl, button("Kaydet ve Dene", "primary", self._save_try), spacing=8))
        self.cards["deepl"].add(self._key_row("deepl", self.deepl))
        self.cards["deepl"].add(hbox(button("Ücretsiz DeepL anahtarı al ›", "link",
                                            lambda: _wb.open(self._key_url("deepl"))), None))
        # Yerel yapay zekâ
        self.lai_url = QLineEdit(c.yerelai_adres)
        self.lai_url.setPlaceholderText("http://localhost:11434/v1")
        self.lai_model = QLineEdit(c.yerelai_model)
        self.lai_model.setPlaceholderText("qwen2.5:7b")
        self.cards["yerelai"].add(hbox(field("Sunucu adresi", self.lai_url), field("Model", self.lai_model), spacing=10))
        self.cards["yerelai"].add(hbox(button("Ollama", None, lambda: self._lai_preset("ollama")),
                                       button("LM Studio", None, lambda: self._lai_preset("lmstudio")),
                                       button("Ollama'yı indir", "ghost", lambda: _wb.open("https://ollama.com/download")),
                                       None, button("Kaydet ve Dene", "primary", self._save_try), spacing=8))
        self.cards["yerelai"].add(label("Ollama'yı kurup komut satırında <b>ollama pull qwen2.5:7b</b> yaz. Ekran kartı "
                                        "olan bilgisayarda bir satır genelde 1-2 saniyede gelir.", "faint", wrap=True))
        self.qual_group.set(c.kalite if c.kalite in self.cards else "yok")
        self.key_btn = button("Anahtar al", None, lambda: _wb.open(self._key_url()))   # eski ad (kullanılmıyor)
        self.key_btn.hide()

        # --- altyazı seçenekleri (CouchSubs Oyun paketleri sayfasındaki anahtarlar)
        opts = SectionCard("Altyazı", "", "translate")
        self.spk_show = QCheckBox("Konuşan adını göster: karakterin adı çevirinin başında kalır (LUCIA: …); adın "
                                  "kendisi hiç çevrilmez", getattr(c, "konusan_goster", True))
        self.ask_game = QCheckBox("Oynanan oyunu sor: oyun paketle tanınmazsa çeviri başladıktan iki dakika sonra bir "
                                  "kez sorulur", getattr(c, "oyun_sor", True))
        self.scene_cb = QCheckBox("Ekran yazılarını kendiliğinden çevir: telefon, harita görev kartı ve gelen mesajlar",
                                  c.ekran_yazilari)
        for w in (self.spk_show, self.ask_game, self.scene_cb):
            opts.add(w)
        root.addWidget(opts)

        # --- dene
        test = SectionCard("Dene", "Bir cümle yaz, seçili motorla nasıl çevrildiğini gör.", "play")
        self.test_in = QLineEdit("You think you can just walk in here and take what's mine, man?")
        test.add(hbox(self.test_in, button("Çevir", "primary", self._test)))
        self.test_out = label("", "muted", wrap=True)
        test.add(self.test_out)
        root.addWidget(test)

        # --- gelişmiş
        adv = Collapsible("Gelişmiş")
        self.fast = combo([("yerel", "Yerel model (internetsiz)"), ("google", "Google Çeviri (anahtarsız)"),
                           ("yok", "Kapalı")], c.hizli)
        self.wait = QSpinBox()
        self.wait.setRange(0, 1500)
        self.wait.setSingleStep(50)
        self.wait.setSuffix(" ms")
        self.wait.setValue(c.kalite_bekleme_ms)
        adv.add(hbox(field("İlk (hızlı) çeviri", self.fast, "Yerel model ekranda ~20-50 ms'de bir çeviri gösterir; "
                                                           "yapay zekâ gelince güncellenir."),
                     field("Kalite öncelikli bekleme", self.wait, "Yapay zekânın çevirisi bu süre içinde gelirse yerel "
                                                                  "çeviri hiç gösterilmez. 0 = her zaman önce yerel."),
                     spacing=20))
        self.slang = QCheckBox("Argo düzeltme: \"gonna, ain't, homie\" gibi ifadeleri yerel modele düzgün İngilizce ver",
                               c.argo_duzelt)
        o = ctl.cfg.ocr
        self.ocr_engine = combo([("otomatik", "Otomatik (Mac'te Apple'ın yazı tanıması, değilse PP-OCR)"),
                                 ("vision", "Apple yazı tanıma (yalnız Mac, Neural Engine)"),
                                 ("ppocr", "PP-OCR (her bilgisayarda; ekran kartında hızlanır)")], o.motor)
        self.ocr_gpu = QCheckBox("Yazıyı okurken ekran kartını kullan (varsa)", o.gpu)
        self.sik = QCheckBox("Değişmeyen altyazı alanını daha sık oku: alan değişmemiş görünse de saniyede bir yeniden "
                             "okunur (ilk okuma bozuksa düzelir; biraz daha işlemci kullanır)", getattr(o, "sik_oku", False))
        self.mt_device = combo([("auto", "Otomatik (NVIDIA ekran kartı varsa onda)"), ("cuda", "Ekran kartı (NVIDIA)"),
                                ("cpu", "İşlemci")], c.yerel_cihaz)
        self.mt_threads = QSpinBox()
        self.mt_threads.setRange(0, 32)
        self.mt_threads.setSpecialValueText("Otomatik")
        self.mt_threads.setValue(getattr(c, "yerel_is_parcacigi", 0))
        self.phone_where = Segmented([("yan", "Telefonun yanında, mesaj panelinde (önerilen)"),
                                      ("ust", "Balonların üstünde")], getattr(c, "telefon_yeri", "yan"))
        self.phone_where.setMaximumWidth(620)
        adv.add(self.slang)
        adv.add(hbox(field("Yazı tanıma", self.ocr_engine), field("Ücretsiz çeviri aygıtı", self.mt_device),
                     field("İşlemci çekirdekleri", self.mt_threads), spacing=16))
        adv.add(self.ocr_gpu)
        adv.add(self.sik)
        self.wait_broken = slider(0, 15, round(getattr(o, "bozuk_bekleme_ms", 0) / 100))
        self.wait_partial = slider(0, 15, round(getattr(o, "yarim_bekleme_ms", 0) / 100))
        adv.add(label("Bu beklemeler yalnız kötü okunan satırları geciktirir. 0'da beklemeden gösterilir, daha iyi okuma "
                      "gelince yerinde düzeltilir (önerilen).", "faint", wrap=True))
        adv.add(hbox(slider_row("Bozuk okunan satır için bekleme", self.wait_broken,
                                lambda v: f"{v / 10:.1f} sn".replace(".", ",")),
                     slider_row("Yarım okunan satır için bekleme", self.wait_partial,
                                lambda v: f"{v / 10:.1f} sn".replace(".", ",")), spacing=24))
        adv.add(field("Telefon mesajlarının Türkçesi", self.phone_where,
                      "Yanında: telefonun yanında, oyundaki sırayla, her mesaj kendi balonunda (Nino'daki gibi). "
                      "Üstünde: her mesajın Türkçesi kendi balonunun tam üstünde."))
        adv.add(label("Sözlük", "h3"))
        adv.add(label("Her satıra bir terim: <b>İngilizce = Türkçe</b>. İsimleri olduğu gibi bırakmak için iki tarafa "
                      "aynısını yaz (ör. Vice City = Vice City).", "faint", wrap=True))
        self.gloss = QPlainTextEdit("\n".join(f"{k} = {v}" for k, v in c.sozluk.items()))
        self.gloss.setFixedHeight(110)
        adv.add(self.gloss)
        root.addWidget(adv)
        root.addLayout(hbox(None, button("Kaydet", "primary", self.save)))
        root.addStretch(1)
        self._results: list[str] = []
        ctl.testResult.connect(self.on_test)
        ctl.packProgress.connect(self._pack_progress)
        ctl.enginesReady.connect(lambda i: (self.cache_l.setText(f"{i.get('onbellek', 0)} çeviri önbellekte"),
                                            self._refresh_packs(), self._engine_badge(i)))
        if ctl.engine_info:
            self.cache_l.setText(f"{ctl.engine_info.get('onbellek', 0)} çeviri önbellekte")
            self._engine_badge(ctl.engine_info)
        self._refresh_packs()
        self._vis()

    # eski arayüzle uyum: qual.currentData()
    @property
    def qual(self):  # noqa: ANN201
        page = self

        class _Q:
            def currentData(self):  # noqa: ANN202, N802
                return page.qual_group.value()

            def findData(self, v):  # noqa: ANN001, ANN202, N802
                return list(page.cards).index(v) if v in page.cards else -1
        return _Q()

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        """Sayfa her açıldığında anahtar alanlarını güncel ayardan doldur (sihirbazda girilen anahtar burada boş
        görünüp 'Kaydet'le silinmesin)."""
        c = self.ctl.cfg.ceviri
        for w, val in ((self.key, c.claude_anahtar), (self.gem, c.gemini_anahtar), (self.deepl, c.deepl_anahtar)):
            if w.text().strip() != val and not w.hasFocus():
                w.setText(val)
        if c.kalite in self.cards and self.qual_group.value() != c.kalite:
            self.qual_group.set(c.kalite)
        super().showEvent(e)

    def _engine_badge(self, info: dict) -> None:
        k = info.get("kalite")
        for v, card in self.cards.items():
            card.title_l.setText(dict((a, b) for a, b, _ in self.ENGINES)[v] + ("   ● Aktif" if v == (k or "yok")
                                                                                 else ""))

    def _vis(self) -> None:
        if self.qual_group.value() in ("deepl", "yerelai"):
            self.more.setOpen(True)
        self._key_states()

    def _key_row(self, kind: str, edit: QLineEdit) -> QHBoxLayout:
        ok = label("", "h3")
        test = button("Dene", None, self._test)
        rm = button("Anahtarı sil", None, lambda: self._remove_key(edit))
        self.key_rows[kind] = (ok, test, rm, edit)
        edit.textChanged.connect(lambda _t: self._key_states())
        return hbox(ok, None, test, rm, spacing=8)

    def _key_states(self) -> None:
        for kind, (ok, test, rm, edit) in getattr(self, "key_rows", {}).items():
            has = bool(edit.text().strip())
            ok.setText(f"<span style='color:{T.OK}'>✓ Anahtar kayıtlı</span>" if has else
                       f"<span style='color:{T.MUTED}'>Anahtar yok</span>")
            test.setVisible(has)
            rm.setVisible(has)

    def _remove_key(self, edit: QLineEdit) -> None:
        edit.clear()
        self.save()

    def _key_url(self, kind: str | None = None) -> str:
        from .. import rehber
        return {"claude": rehber.CLAUDE_KEYS, "gemini": rehber.GEMINI_KEYS,
                "deepl": rehber.DEEPL_SIGNUP}.get(kind or self.qual_group.value(), rehber.GEMINI_KEYS)

    def _lai_preset(self, kind: str) -> None:
        self.lai_url.setText("http://localhost:11434/v1" if kind == "ollama" else "http://localhost:1234/v1")
        if kind == "ollama" and not self.lai_model.text().strip():
            self.lai_model.setText("qwen2.5:7b")

    def _save_try(self) -> None:
        self.save()
        QTimer.singleShot(1500, self._test)

    def _test(self) -> None:
        self._results = []
        self.test_out.setText("Çevriliyor...")
        self.ctl.test_translation(self.test_in.text())

    def on_test(self, r) -> None:  # noqa: ANN001
        self._results.append(f"<b>{r.text}</b> <span style='color:{T.FAINT}'>· {r.source} · {r.ms:.0f} ms</span>")
        self.test_out.setText("<br>".join(self._results))
        try:
            self.window().toast.show_text(f"Çeviri: {r.text}"[:90])
        except Exception:  # noqa: BLE001
            pass

    def _open_data(self) -> None:
        from .. import paths
        open_path(str(paths.data_dir()))

    def _pick_game(self, _i: int) -> None:
        name = self.game_pick.currentData()
        if name:
            self.ctl.game_choice.choose(name)
            self.window().toast.show_text(f"Oyun: {name}. Çeviri ilk cümleden itibaren paketten gelir.")
        else:
            self.ctl.game_choice.automatic()
            self.window().toast.show_text("Oyun kendiliğinden anlaşılacak")

    def _refresh_packs(self) -> None:
        ps = self.ctl.pack_list()
        cur = self.game_pick.currentData()
        self.game_pick.blockSignals(True)
        while self.game_pick.count() > 1:
            self.game_pick.removeItem(1)
        for p_ in sorted(ps, key=lambda p_: p_.title):
            self.game_pick.addItem(p_.title, p_.title)
        i = self.game_pick.findData(cur)
        self.game_pick.setCurrentIndex(max(0, i))
        self.game_pick.blockSignals(False)
        while self.pack_grid.count():
            it = self.pack_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, p in enumerate(sorted(ps, key=lambda p: p.title)):
            self.pack_grid.addWidget(_PackTile(p.title, p.count), i // 2, i % 2)
        total = sum(p.count for p in ps)
        self.packs_pill.set("ok" if ps else "off", f"{len(ps)} oyun · {total:,} satır".replace(",", ".") if ps
                            else "Paket yok")
        self.packs_l.setText("" if ps else "Yüklü paket yok. Aşağıdan hazır paketi indir ya da kendi paketini yükle.")
        self.packs_l.setVisible(not ps)

    def _on_catalog(self, cat: list) -> None:
        # Önceki CouchSubs girdilerini kaldır, yenilerini en üste koy (GTA 6 en başta)
        for i in reversed(range(self.pack_combo.count())):
            if str(self.pack_combo.itemData(i)).startswith("cs:"):
                self.pack_combo.removeItem(i)
        cat = sorted(cat, key=lambda p: (0 if "6" in p["id"] or "vi" in p["id"].split("-") else 1, p["title"]))
        for k, p in enumerate(cat):
            n = f"{p['entries']:,}".replace(",", ".")
            extra = " · ek satırlar" if p.get("auto") else ""
            src = p.get("source") or "CouchSubs"
            self.pack_combo.insertItem(k, f"{p['title']}{extra} · {src} ({n} satır)", f"cs:{p['id']}")
        if cat:
            self.pack_combo.setCurrentIndex(0)
            if any(p.get("own") for p in cat):   # kendi listemiz geldiyse aynı oyunun eski kaynak girdisini gizle
                for i in reversed(range(self.pack_combo.count())):
                    if not str(self.pack_combo.itemData(i)).startswith("cs:"):
                        self.pack_combo.removeItem(i)

    def _download_pack(self) -> None:
        self.pack_dl.setEnabled(False)
        self.pack_dl.setText("İndiriliyor...")
        self.ctl.download_pack(self.pack_combo.currentData())

    def _pack_progress(self, _pid: str, f: float) -> None:
        if 0 <= f < 1:
            self.pack_dl.setText(f"İndiriliyor %{int(f * 100)}")
            return
        self.pack_dl.setEnabled(True)
        self.pack_dl.setText("Hazır paketi indir")
        self._refresh_packs()

    def _add_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Çeviri paketi seç", "", "Paket (*.json *.gz);;Tümü (*)")
        if not path:
            return
        try:
            msg = self.ctl.import_pack(path)
        except Exception as e:  # noqa: BLE001
            msg = f"Paket okunamadı: {e}"
        self.window().toast.show_text(msg)
        self._refresh_packs()

    # --------------------------------------------------------------- oyun metni
    def _script_status(self, text: str = "") -> None:
        from ..oyun_metni import default_path
        p = default_path()
        eng = self.ctl.engine
        if text:
            self.script_l.setText(text)
        elif p.exists():
            n = eng.script.count if eng is not None and getattr(eng, "script", None) is not None else None
            self.script_l.setText(f"İndirildi · {n:,} satır".replace(",", ".") if n else
                                  f"İndirildi ({p.stat().st_size // 1_000_000} MB)")
        else:
            self.script_l.setText("İndirilmedi. İndirince okuma hataları kendiliğinden düzelir.")
        self.script_dl.setVisible(not p.exists())
        self.script_rm.setVisible(p.exists())

    def _script_download(self) -> None:
        import threading
        from PySide6.QtCore import QMetaObject, Q_ARG
        self.script_dl.setEnabled(False)

        def say(msg: str) -> None:
            QMetaObject.invokeMethod(self, "_script_progress", Qt.QueuedConnection, Q_ARG(str, msg))

        def work() -> None:
            from ..oyun_metni import build, default_path
            try:
                n = build(default_path(), progress=say)
                if self.ctl.engine is not None:
                    self.ctl.engine.load_script()
                say(f"bitti:{n}")
            except Exception as e:  # noqa: BLE001
                say(f"hata:{e}")

        threading.Thread(target=work, daemon=True, name="oyun-metni").start()

    @Slot(str)
    def _script_progress(self, msg: str) -> None:
        if msg.startswith("bitti:"):
            self.script_dl.setEnabled(True)
            self._script_status()
            self.window().toast.show_text("Oyun metni hazır: okuma hataları artık düzeliyor")
        elif msg.startswith("hata:"):
            self.script_dl.setEnabled(True)
            self._script_status(f"İndirilemedi: {msg[5:]}")
        else:
            self._script_status(msg)

    def _script_remove(self) -> None:
        from ..oyun_metni import default_path
        if self.ctl.engine is not None:
            self.ctl.engine.script = None
        try:
            default_path().unlink()
        except OSError:
            pass
        self._script_status()

    def _export_pack(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Önbelleği paket olarak kaydet", "gta6-altyazi-paket.json.gz",
                                              "Paket (*.json.gz *.json)")
        if path:
            n = self.ctl.export_pack(path)
            self.window().toast.show_text(f"{n} çeviri pakete yazıldı")

    def save(self) -> None:
        cfg = self.ctl.edit_config()
        c = cfg.ceviri
        c.hizli = self.fast.currentData()
        c.argo_duzelt = self.slang.isChecked()
        c.ekran_yazilari = self.scene_cb.isChecked()
        c.konusan_goster = self.spk_show.isChecked()
        c.paket_kullan = self.packs_on.isChecked()
        c.oyun_metni = self.script_on.isChecked()
        c.gemini_model = self.gem_model.currentData()
        c.yerel_cihaz = self.mt_device.currentData()
        c.yerel_is_parcacigi = self.mt_threads.value()
        cfg.ocr.motor = self.ocr_engine.currentData()
        cfg.ocr.gpu = self.ocr_gpu.isChecked()
        cfg.ocr.sik_oku = self.sik.isChecked()
        cfg.ocr.bozuk_bekleme_ms = self.wait_broken.value() * 100
        cfg.ocr.yarim_bekleme_ms = self.wait_partial.value() * 100
        c.oyun_sor = self.ask_game.isChecked()
        c.telefon_yeri = self.phone_where.value() or "yan"
        c.kalite_bekleme_ms = self.wait.value()
        c.kalite = self.qual_group.value() or "yok"
        c.claude_anahtar = self.key.text().strip()
        c.claude_model = self.model.currentData()
        c.claude_hizli_mod = self.fastmode.isChecked() and c.claude_model == "claude-opus-5-5"
        c.gemini_anahtar = self.gem.text().strip()
        c.deepl_anahtar = self.deepl.text().strip()
        c.yerelai_adres = self.lai_url.text().strip() or "http://localhost:11434/v1"
        c.yerelai_model = self.lai_model.text().strip() or "qwen2.5:7b"
        gl = {}
        for line in self.gloss.toPlainText().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip():
                    gl[k.strip()] = v.strip()
        c.sozluk = gl
        self.ctl.apply_config(cfg, explicit_keys=True)     # anahtar alanlarını kullanıcı kendisi düzenledi
        self.window().toast.show_text("Çeviri ayarları kaydedildi, motorlar yeniden hazırlanıyor")


# ============================================================================ Geçmiş
class HistoryPage(QWidget):
    COLS = ["Saat", "Bölge", "İngilizce", "Türkçe", "Motor", "ms"]

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "Altyazı geçmişi", "Bu oturumda çevrilen bütün yazılar. Kaliteli çeviri gelince satır "
                          "kendiliğinden güncellenir.", "history", scroll=False)
        last = SectionCard(margins=16, spacing=6)
        self.last_state = Pill("Beklemede", "off")
        last.add(hbox(label("Son altyazı", "h3"), None, self.last_state))
        self.last = label("Oynarken son altyazı burada görünür.", "muted", wrap=True)
        last.add(self.last)
        root.addWidget(last)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara...")
        self.search.textChanged.connect(self._filter)
        root.addLayout(hbox(self.search, button("Temizle", None, self._clear), button("TXT", None, self._export),
                            button("JSON", None, self._export_json), spacing=8))
        card = Card(margins=0)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        for i, mode in enumerate([QHeaderView.ResizeToContents, QHeaderView.ResizeToContents, QHeaderView.Stretch,
                                  QHeaderView.Stretch, QHeaderView.ResizeToContents, QHeaderView.ResizeToContents]):
            hh.setSectionResizeMode(i, mode)
        card.add(self.table)
        root.addWidget(card, 1)
        self.rows: dict[int, int] = {}
        ctl.historyChanged.connect(self.on_item)
        ctl.stateChanged.connect(lambda s: self.last_state.set("ok", "Çeviriyor") if s == "calisiyor"
                                 else self.last_state.set("off", "Beklemede"))

    def on_item(self, it, updated: bool) -> None:  # noqa: ANN001
        self.last.setText(f"<b>{it.text}</b><br><span style='color:{T.FAINT}'>{it.english}</span>")
        vals = [time.strftime("%H:%M:%S"), "ekran" if it.zone.startswith("tam") else it.zone, it.english, it.text,
                it.source, f"{it.latency_ms:.0f}"]
        if updated and it.seq in self.rows:
            row_i = self.table.rowCount() - 1 - self.rows[it.seq]
            for c in (3, 4, 5):
                self.table.setItem(row_i, c, QTableWidgetItem(vals[c]))
            return
        self.table.insertRow(0)
        for c, v in enumerate(vals):
            self.table.setItem(0, c, QTableWidgetItem(v))
        self.rows[it.seq] = self.table.rowCount() - 1
        self.table.resizeRowToContents(0)
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        t = text.lower()
        for r in range(self.table.rowCount()):
            hit = not t or any(t in (self.table.item(r, c).text().lower() if self.table.item(r, c) else "")
                               for c in (2, 3))
            self.table.setRowHidden(r, not hit)

    def _clear(self) -> None:
        self.table.setRowCount(0)
        self.rows.clear()

    def _rows(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount() - 1, -1, -1):
            cells = [self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(len(self.COLS))]
            out.append(dict(zip(("saat", "bolge", "ingilizce", "turkce", "motor", "ms"), cells)))
        return out

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", "gta6-ceviriler.txt", "Metin (*.txt)")
        if path:
            lines = [f"[{r['saat']}] {r['ingilizce']}\n    → {r['turkce']}" for r in self._rows()]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", "gta6-ceviriler.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._rows(), f, ensure_ascii=False, indent=1)


# ============================================================================ Ses, kısayollar ve diğer
class SettingsPage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        cfg = ctl.cfg
        _transparent(self)
        root = page_shell(self, "Ses ve kısayollar", "Türkçe dublaj, kısayol tuşları, kendiliğinden çalışma ve "
                          "güncellemeler.", "settings")

        voice = SectionCard("Türkçe dublaj", "Çeviriyi doğal Türkçe sesle okur (Ahmet / Emel); konuşanın adına göre kadın "
                            "ya da erkek ses. Oyunun ses ayarlarından konuşma (diyalog) sesini kıs; müzik ve efektler "
                            "kalsın.", "phone")
        self.speak = QCheckBox("Çeviriyi Türkçe seslendir", cfg.gosterim.seslendir)
        self.speak_rate = QSlider(Qt.Horizontal)
        self.speak_rate.setRange(-50, 50)
        self.speak_rate.setValue(cfg.gosterim.ses_hizi)
        voice.add(self.speak)
        voice.add(slider_row("Konuşma hızı", self.speak_rate, lambda v: f"{v:+d} %"))
        root.addWidget(voice)

        keys = SectionCard("Kısayollar", "Her işin iki kısayolu var; böylece sayı tuş takımı olmayan klavyelerde de "
                           "çalışır. Örnek: ctrl+shift+9, alt+f10, num9. Boş bırakılan kısayol kapalıdır. Telefon "
                           "kumandasında da aynı düğmeler var.", "bolt")
        k = cfg.kisayol
        self.keys: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        for attr, title in (("tam_ekran", "Ekranı çevir"), ("duraklat", "Altyazıyı duraklat / sürdür"),
                            ("baslat", "Çeviriyi başlat / durdur"), ("seslendir", "Türkçe seslendirmeyi aç / kapat"),
                            ("tv_deneme", "TV'ye deneme altyazısı gönder")):
            pair = []
            for a in (attr, attr + "2"):
                e = QLineEdit(getattr(k, a, ""))
                e.setObjectName("kbd")
                e.setAlignment(Qt.AlignCenter)
                e.setFixedWidth(170)
                pair.append(e)
            self.keys[attr] = (pair[0], pair[1])
            keys.add(hbox(label(title, "h3"), None, pair[0], pair[1], spacing=10))
        self.k_fs, self.k_pause = self.keys["tam_ekran"][0], self.keys["duraklat"][0]   # eski adlar
        self.fs_time = QSpinBox()
        self.fs_time.setRange(5, 120)
        self.fs_time.setValue(k.tam_ekran_sure)
        self.fs_time.setSuffix(" sn")
        self.fs_time.setFixedWidth(170)
        keys.add(hbox(label("Ekran çevirisi ekranda kalma süresi", "h3"), None, self.fs_time))
        self.fs_vision = QCheckBox("Ekranı çevirirken Claude görsel okuma kullan (menü, telefon ve süslü yazılarda daha "
                                   "doğru; 2-4 sn sürer, Claude anahtarı gerekir)", k.tam_ekran_gorsel)
        keys.add(self.fs_vision)
        keys.add(hbox(button("Varsayılanlara dön", None, self._keys_default), None))
        root.addWidget(keys)

        auto = SectionCard("TV günleri: kendiliğinden çalışma", "Kasa başka odadayken her şey kendiliğinden olsun: sen "
                           "TV'de PS5'i açarsın, çeviri başlar ve TV'ye altyazı gider. PS5'i kapatınca hepsi durur.",
                           "swap")
        o = cfg.otomatik
        self.a_boot = QCheckBox("Bilgisayar açılınca GTA6 Altyazı da açılsın (simge durumunda)", o.windows_ile_baslat)
        self.a_src = QCheckBox("chiaki bağlanınca çeviri kendiliğinden başlasın, kapanınca dursun", o.chiaki_gorunce_baslat)
        self.a_ps5 = QCheckBox("PS5 açılınca chiaki kendiliğinden bağlansın", o.ps5_acilinca_baglan)
        self.a_fs = QCheckBox("Otomatik bağlanınca chiaki tam ekran açılsın", o.chiaki_tam_ekran)
        auto.add(self.a_boot)
        self.chiaki_auto = QWidget()
        self.chiaki_auto.setLayout(vbox(self.a_src, self.a_ps5, self.a_fs, spacing=8))
        auto.add(self.chiaki_auto)
        self.ps5_name = QLineEdit(o.ps5_adi)
        self.ps5_name.setPlaceholderText("PS5 adı (ör. PS5-123)")
        self.ps5_ip = QLineEdit(o.ps5_ip)
        self.ps5_ip.setPlaceholderText("PS5 IP adresi")
        self.ps5_btn = button("PS5'i bul", None, self._find_ps5)
        self.ps5_find = QWidget()
        self.ps5_find.setLayout(vbox(hbox(self.ps5_name, self.ps5_ip, self.ps5_btn, spacing=10),
                                     label("PS5'in adı chiaki'de kayıtlı adla aynı olmalı. \"PS5'i bul\" PS5 açıkken ya "
                                           "da dinlenme modundayken ağdan bulur.", "faint", wrap=True), spacing=6))
        auto.add(self.ps5_find)
        root.addWidget(auto)

        upd = SectionCard("Güncellemeler", "Kurulumu yeniden yapmana gerek yok: paketler sessizce güncellenir, uygulama "
                          "Güncelle düğmesiyle kendini yeniler. Ayarların, anahtarların ve paketlerin korunur.", "check")
        self.u_pack = QCheckBox("Hazır paketlerin (GTA 6 dahil) yenisini açılışta kendiliğinden indir", o.paket_guncelle)
        self.u_app = QCheckBox("Yeni sürüm çıkınca ana ekranda haber ver (tek tıkla güncellenir)", o.surum_denetle)
        upd.add(self.u_pack)
        upd.add(self.u_app)
        root.addWidget(upd)
        ctl.ps5Found.connect(self._on_ps5)
        root.addLayout(hbox(button("Kurulumu baştan yap", None, lambda: self.window().open_wizard()), None,
                            button("Kaydet", "primary", self.save), spacing=10))
        root.addStretch(1)

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        rp = self.ctl.cfg.kaynak.tur == "remoteplay"         # TV'de oynayana chiaki seçeneklerini gösterme
        self.chiaki_auto.setVisible(not rp)
        self.ps5_find.setVisible(not rp)
        super().showEvent(e)

    def _keys_default(self) -> None:
        from ..config import KisayolCfg
        d = KisayolCfg()
        for attr, (a, b) in self.keys.items():
            a.setText(getattr(d, attr))
            b.setText(getattr(d, attr + "2"))

    def _find_ps5(self) -> None:
        self.ps5_btn.setEnabled(False)
        self.ps5_btn.setText("Aranıyor...")
        self.ctl.find_ps5()

    def _on_ps5(self, consoles: list) -> None:
        self.ps5_btn.setEnabled(True)
        self.ps5_btn.setText("PS5'i bul")
        if not consoles:
            self.window().toast.show_text("PS5 bulunamadı. Açık ya da dinlenme modunda ve aynı ağda mı?")
            return
        c = consoles[0]
        self.ps5_name.setText(c.name)
        self.ps5_ip.setText(c.ip)
        self.window().toast.show_text(f"PS5 bulundu: {c.name} ({c.ip}) · {'açık' if c.awake else 'dinlenme modunda'}")

    def save(self) -> None:
        cfg = self.ctl.edit_config()
        cfg.gosterim.seslendir = self.speak.isChecked()
        cfg.gosterim.ses_hizi = self.speak_rate.value()
        for attr, (a, b) in self.keys.items():
            setattr(cfg.kisayol, attr, a.text().strip().lower())
            setattr(cfg.kisayol, attr + "2", b.text().strip().lower())
        cfg.kisayol.tam_ekran_sure = self.fs_time.value()
        cfg.kisayol.tam_ekran_gorsel = self.fs_vision.isChecked()
        o = cfg.otomatik
        o.windows_ile_baslat = self.a_boot.isChecked()
        o.chiaki_gorunce_baslat = self.a_src.isChecked()
        o.ps5_acilinca_baglan = self.a_ps5.isChecked()
        o.chiaki_tam_ekran = self.a_fs.isChecked()
        o.paket_guncelle = self.u_pack.isChecked()
        o.surum_denetle = self.u_app.isChecked()
        o.ps5_adi = self.ps5_name.text().strip()
        o.ps5_ip = self.ps5_ip.text().strip()
        self.ctl.apply_config(cfg)
        self.window().toast.show_text("Ayarlar kaydedildi")


# ============================================================================ Rehber
class GuidePage(QWidget):
    """Bütün süreçlerin resimli, adım adım anlatımı (içerik: altyazi/rehber.py; README'deki rehberle aynı)."""

    def __init__(self, ctl: AppController):
        super().__init__()
        from PySide6.QtWidgets import QButtonGroup, QPushButton

        from .. import rehber
        from .guide import Guide

        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "Rehber", "Kurulumdan oynamaya, her şeyin resimli anlatımı. Soldan konuyu seç, adımları "
                          "sırayla izle.", "guide", scroll=False)
        body = QHBoxLayout()
        body.setSpacing(16)
        side = QVBoxLayout()
        side.setSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.guides = rehber.GUIDES
        for i, g in enumerate(self.guides):
            b = QPushButton()
            b.setCheckable(True)
            t1, t2 = label(g["title"], "h3"), label(g["summary"], "faint", wrap=True)
            for t in (t1, t2):
                t.setAttribute(Qt.WA_TransparentForMouseEvents)
                t.setStyleSheet("background: transparent;")
            inner = vbox(t1, t2, spacing=2)
            inner.setContentsMargins(14, 10, 14, 10)
            b.setLayout(inner)
            b.setMinimumHeight(76)
            b.setStyleSheet(
                f"QPushButton {{ text-align: left; border-radius: 14px; background: {T.CARD_BG};"
                f" border: 1px solid {T.CARD_LINE}; }} QPushButton:hover {{ border-color: {T.BORDER_HI}; }}"
                f"QPushButton:checked {{ background: {T.SURFACE2}; border: 1.5px solid {T.A1}; }}")
            b.clicked.connect(lambda _=False, k=i: self.show_guide(k))
            self.group.addButton(b, i)
            side.addWidget(b)
        side.addStretch(1)
        side_w = QWidget()
        _transparent(side_w)
        side_w.setLayout(side)
        side_w.setFixedWidth(330)
        side_scroll = scroll_page(side_w)
        side_scroll.setFixedWidth(346)
        body.addWidget(side_scroll)
        card = Card()
        self.heading = label("", "h2")
        card.add(self.heading)
        self.guide = Guide(nav=True)
        self.guide.setMinimumHeight(540)
        card.add(self.guide)
        body.addWidget(card, 1)
        root.addLayout(body, 1)
        self.show_guide(0)

    def show_guide(self, i: int) -> None:
        g = self.guides[i]
        self.group.button(i).setChecked(True)
        self.heading.setText(g["title"])
        self.guide.index = 0
        self.guide.set_steps(g["steps"])

    def open_key(self, key: str) -> None:
        for i, g in enumerate(self.guides):
            if g["key"] == key:
                self.show_guide(i)
                return


# ============================================================================ Sistem sağlığı
class HealthPage(QWidget):
    """Nino'nun Sistem sağlığı sayfası: ağ, PS5 bağlantısı ve görüntüsü, çeviri hızı, TV; cihaz bilgileri."""

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "Sistem sağlığı", "Takılma ya da gecikme varsa sebebini ve ne yapacağını burada gör. "
                          "Birkaç saniyede bir yenilenir.", "bolt")
        self.card = SectionCard(margins=18, spacing=0)
        self.rows: dict[str, HealthRow] = {}
        root.addWidget(self.card)
        info = SectionCard("Cihaz bilgileri", "Sorun bildirdiğinde eklenir; ne kullandığını sormadan görürüz. Ad, seri "
                           "numarası ya da adres içermez.", margins=18)
        self.info_grid = QGridLayout()
        self.info_grid.setHorizontalSpacing(30)
        self.info_grid.setVerticalSpacing(8)
        info.add(self.info_grid)
        info.add(hbox(button("Cihaz bilgilerini kopyala", None, self._copy),
                      button("Sorun bildir", "primary", self._report), None, spacing=10))
        root.addWidget(info)
        self.log = Collapsible("Ayrıntılar (son kayıtlar)")
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(220)
        self.log.add(self.log_text)
        root.addWidget(self.log)
        root.addStretch(1)
        self._kind = None
        self._timer = QTimer(self, interval=3000, timeout=self.refresh)

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        super().showEvent(e)
        self.refresh()
        self._timer.start()

    def hideEvent(self, e) -> None:  # noqa: ANN001, N802
        self._timer.stop()
        super().hideEvent(e)

    def refresh(self) -> None:
        from .. import saglik
        if self._kind is None:
            self._kind = saglik.network_kind()
        rows = saglik.checks(self.ctl, self._kind)
        for i, r in enumerate(rows):
            w = self.rows.get(r["key"])
            if w is None:
                if self.rows:
                    sep = QFrame()
                    sep.setFixedHeight(1)
                    sep.setStyleSheet(f"background:{T.BORDER};")
                    self.card.add(sep)
                w = HealthRow()
                self.rows[r["key"]] = w
                self.card.add(w)
            w.set(r)
        while self.info_grid.count():
            it = self.info_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, (k, v) in enumerate(saglik.device_info(self.ctl)):
            self.info_grid.addWidget(label(k, "muted"), i, 0)
            self.info_grid.addWidget(label(v, None), i, 1)
        self.info_grid.setColumnStretch(1, 1)
        if self.log.body.isVisible():
            self.log_text.setPlainText(_log_tail())

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        from .. import saglik
        QApplication.clipboard().setText(saglik.info_text(self.ctl))
        self.window().toast.show_text("Cihaz bilgileri kopyalandı")

    def _report(self) -> None:
        from .. import saglik
        webbrowser.open(saglik.issue_url(self.ctl))


def _log_tail(n: int = 80) -> str:
    try:
        from .. import paths
        p = paths.data("altyazi.log")
        if not p.exists():
            logs = sorted(paths.data_dir().glob("*.log"), key=lambda q: q.stat().st_mtime)
            p = logs[-1] if logs else p
        return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except Exception as e:  # noqa: BLE001
        return f"Kayıt okunamadı: {e}"


# ============================================================================ OBS katmanı
class ObsPage(QWidget):
    """Yayın yapanlar için (CouchSubs / Nino OBS katmanı): tarayıcı kaynağı adresi ve yayın penceresi."""

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "OBS katmanı", "Yayın yapıyorsan Türkçe altyazı hem senin ekranında hem yayında oyunun "
                          "üstünde görünür.", "play")
        port = ctl.cfg.sunucu.port
        local = f"http://localhost:{port}/obs"
        lan = ctl.server_url("obs")
        src = SectionCard("Tarayıcı kaynağı", "Capture card ile yayın mı yapıyorsun? OBS'te bu adresle bir Tarayıcı "
                          "kaynağı ekle (genişlik 1920, yükseklik 1080). Katman yalnız çeviri çalışırken altyazı gösterir.",
                          margins=18)
        for url, hint in ((local, ""), (lan, "OBS başka bir bilgisayardaysa ya da yayın programın localhost'u kabul "
                                            "etmiyorsa (ör. TikTok LIVE Studio) bu bilgisayarın ağ adresiyle bunu kullan:")):
            if hint:
                src.add(label(hint, "faint", wrap=True))
            box = QLineEdit(url)
            box.setReadOnly(True)
            box.setObjectName("mono")
            src.add(hbox(box, button("Kopyala", None, lambda _=False, u=url: self._copy(u)), spacing=8))
        root.addWidget(src)
        win = SectionCard("Yayın penceresi", "Saydam tarayıcı kaynağı olmayan yayın programları (TikTok LIVE Studio, "
                          "Streamlabs ve diğerleri) için: yayın penceresini aç, programda Pencere yakalama ile ekle "
                          "(pencerenin adı GTA6 Altyazı Yayın) ve zeminini Chroma key filtresiyle sil.", margins=18)
        self.bg = Segmented([("#00ff00", "Yeşil"), ("#000000", "Siyah"), ("#ff00ff", "Mor")], "#00ff00")
        self.bg.setFixedWidth(320)
        win.add(hbox(label("Arka plan", "h3"), self.bg, None, spacing=12))
        win.add(hbox(button("Yayın penceresini aç", "primary", lambda: ctl.open_stream_window(self.bg.value())), None))
        win.add(label("Yayın boyunca pencereyi açık ve önü kapalı olmadan tut. Çeviri sürerken altyazılar, yalnız TV'de "
                      "gösterilseler bile bu pencerede görünür.", "faint", wrap=True))
        root.addWidget(win)
        root.addStretch(1)

    def _copy(self, url: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(url)
        self.window().toast.show_text("Adres kopyalandı")


# ============================================================================ Hakkında
class AboutPage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        _transparent(self)
        root = page_shell(self, "Hakkında", f"GTA6 Altyazı {__version__}", None)
        card = SectionCard(margins=28, spacing=10)
        logo = Logo(1.4)
        card.add(hbox(None, logo, None))
        for text, obj in ((f"Sürüm {__version__}", "muted"), ("GNU AGPL-3.0 lisansıyla ücretsiz ve açık kaynak.", "h3")):
            lb = label(text, obj)
            lb.setAlignment(Qt.AlignCenter)
            card.add(lb)
        credit = label("Sinan Yorulmaz'ın <a href='https://github.com/yorulmazsinan/couchsubs'>CouchSubs</a> projesinden, "
                       "<a href='https://gitlab.com/sefflex/GameTranslator'>GameTranslator</a>'dan ve Nino Game "
                       "Translator'dan alınan kodları içerir. Uzaktan Oynatma bağlantısı "
                       "<a href='https://github.com/streetpea/chiaki-ng'>chiaki-ng</a> (AGPL-3.0) ile; çeviri modeli "
                       "OPUS-MT, Helsinki Üniversitesi (CC BY 4.0). Geliştiricilerine teşekkürler.", "muted", wrap=True)
        credit.setOpenExternalLinks(True)
        credit.setAlignment(Qt.AlignCenter)
        card.add(credit)
        src = label("<a href='https://github.com/CH4P4R/gta6-altyazi'>Kaynak kodu: github.com/CH4P4R/gta6-altyazi</a>",
                    "muted")
        src.setOpenExternalLinks(True)
        src.setAlignment(Qt.AlignCenter)
        card.add(src)
        note = label("GTA6 Altyazı, Rockstar Games ya da Sony Interactive Entertainment ile bağlantılı değildir. "
                     "PlayStation ve PS5, Sony Interactive Entertainment Inc.'in ticari markalarıdır.", "faint", wrap=True)
        note.setAlignment(Qt.AlignCenter)
        card.add(note)
        card.add(8)
        card.add(hbox(None, button("Kurulumu baştan yap", None, lambda: self.window().open_wizard()),
                      button("Sorun bildir", None, self._report),
                      button("Kayıt ve ayar klasörü", None, self._open_data), None, spacing=10))
        self.theme = Segmented([("koyu", "Koyu"), ("acik", "Açık")], ctl.cfg.gosterim.tema)
        self.theme.setFixedWidth(240)
        self.theme.changed.connect(self._theme)
        card.add(hbox(None, label("Görünüm", "h3"), self.theme, None, spacing=12))
        card.add(hbox(None, button("OBS katmanını kopyala", "ghost", self._copy_obs),
                      button("Ayarları sıfırla", "danger", self._reset), None, spacing=10))
        card.setMaximumWidth(760)
        root.addLayout(hbox(None, card, None))
        root.addStretch(1)

    def _open_data(self) -> None:
        from .. import paths
        open_path(str(paths.data_dir()))

    def _copy_obs(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(f"http://localhost:{self.ctl.cfg.sunucu.port}/obs")
        self.window().toast.show_text("OBS adresi kopyalandı")

    def _report(self) -> None:
        from .. import saglik
        webbrowser.open(saglik.issue_url(self.ctl))

    def _theme(self, v: str) -> None:
        cfg = self.ctl.edit_config()
        cfg.gosterim.tema = v
        self.ctl.apply_config(cfg)
        self.window().toast.show_text("Görünüm programı yeniden açınca değişir")

    def _reset(self) -> None:
        """Ayarları varsayılana döndür; anahtarlar, PS5 eşlemesi ve TV adresi korunur (yeniden kurmak zor olanlar)."""
        from PySide6.QtWidgets import QMessageBox

        from .. import config as config_mod
        if QMessageBox.question(self, "Ayarları sıfırla", "Görünüm, okuma alanları, kısayollar ve diğer ayarlar "
                                "varsayılana dönsün mü? Anahtarların, PS5 eşlemen ve TV adresin korunur.") \
                != QMessageBox.Yes:
            return
        old = self.ctl.cfg
        new = config_mod.Config()
        new.ceviri.claude_anahtar = old.ceviri.claude_anahtar
        new.ceviri.gemini_anahtar = old.ceviri.gemini_anahtar
        new.ceviri.deepl_anahtar = old.ceviri.deepl_anahtar
        new.ceviri.yerelai_anahtar = old.ceviri.yerelai_anahtar
        new.ceviri.kalite = old.ceviri.kalite
        new.ps5 = old.ps5
        new.tv.ip, new.tv.marka, new.tv.lg_parola = old.tv.ip, old.tv.marka, old.tv.lg_parola
        new.kaynak.tur, new.kaynak.oyun_yeri = old.kaynak.tur, old.kaynak.oyun_yeri
        new.gocler = list(old.gocler)
        self.ctl.apply_config(new)
        self.window().toast.show_text("Ayarlar sıfırlandı; yeni görünüm için programı yeniden aç")


def _card_add_int(self, w, stretch: int = 0):  # noqa: ANN001, ANN202
    if isinstance(w, int):
        self.lay.addSpacing(w)
        return w
    return SectionCard._orig_add(self, w, stretch)


SectionCard._orig_add = SectionCard.add
SectionCard.add = _card_add_int


# ============================================================================ Pencere
class MainWindow(QMainWindow):
    # (anahtar, ad, ikon, grup başlığı)
    PAGES = [("home", "Ana ekran", "home", None),
             ("look", "Altyazı görünümü", "translate", "AYARLAR"), ("regions", "Okuma alanı", "regions", None),
             ("translate", "Çeviri ve paketler", "bolt", None), ("tv", "Bağlantı", "tv", None),
             ("settings", "Ses ve kısayollar", "settings", None), ("history", "Altyazı geçmişi", "history", None),
             ("obs", "OBS katmanı", "play", None),
             ("health", "Sistem sağlığı", "bolt", "YARDIM"), ("guide", "Rehber", "guide", None),
             ("about", "Hakkında", "check", None)]

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle("GTA6 Altyazı")
        self.setWindowIcon(app_icon())
        self.resize(1320, 860)
        self.setMinimumSize(1100, 720)
        central = Backdrop()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(244)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 20, 16, 18)
        sl.setSpacing(3)
        sl.addWidget(Logo())
        sl.addSpacing(16)
        self.nav: dict[str, NavButton] = {}
        self.stack = QStackedWidget()
        _transparent(self.stack)
        factories = {"home": HomePage, "look": AppearancePage, "regions": RegionsPage, "tv": TvPage,
                     "translate": TranslationPage, "history": HistoryPage, "guide": GuidePage,
                     "settings": SettingsPage, "about": AboutPage, "health": HealthPage, "obs": ObsPage}
        self.pages: dict[str, QWidget] = {}
        for key, text, icon, group in self.PAGES:
            if group:
                sl.addWidget(label(group, "sideHeader"))
            b = NavButton(text, icon)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            sl.addWidget(b)
            self.nav[key] = b
            page = factories[key](ctl)
            self.pages[key] = page
            self.stack.addWidget(page)
        sl.addStretch(1)
        self.foot = label("", "faint", wrap=True)
        sl.addWidget(self.foot)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.toast = Toast(central)
        self.fab = HelpFab(central)
        self.fab.clicked.connect(self._ask)
        self.go("home")
        ctl.notice.connect(lambda m: self.toast.show_text(m))
        ctl.stateChanged.connect(self._foot)
        ctl.enginesReady.connect(lambda _i: self._foot(ctl.state))
        ctl.tvStatus.connect(lambda *_a: self._foot(ctl.state))
        ctl.ps5Status.connect(lambda *_a: self._foot(ctl.state))
        self._foot(ctl.state)

    def resizeEvent(self, e) -> None:  # noqa: ANN001, N802
        super().resizeEvent(e)
        self.fab.place()

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        super().showEvent(e)
        self.fab.place()

    def _ask(self) -> None:
        from .yardim import AskDialog
        if getattr(self, "_ask_dlg", None) is None:
            self._ask_dlg = AskDialog(self.ctl, self)
        self._ask_dlg.show()
        self._ask_dlg.raise_()

    def go(self, key: str) -> None:
        for k, b in self.nav.items():
            b.setChecked(k == key)
        self.stack.setCurrentWidget(self.pages[key])

    def _foot(self, state: str) -> None:
        """Nino'nun alt durum çubuğu gibi: PS5 · TV · çeviri · sürüm."""
        dot = {"calisiyor": T.OK, "hazir": T.INFO, "hazirlaniyor": T.WARN, "hata": T.BAD}.get(state, T.MUTED)
        name = {"calisiyor": "Çeviri açık", "hazir": "Hazır", "hazirlaniyor": "Hazırlanıyor", "hata": "Hata"}.get(state,
                                                                                                                  state)
        tv = self.ctl.tv_state[0]
        tvc = T.OK if tv == "bagli" else (T.WARN if tv in ("baglaniyor", "onay") else T.FAINT)
        ps = getattr(self.ctl, "rp_state", ("", ""))[0]
        psc = T.OK if ps == "bagli" else (T.WARN if ps == "baglaniyor" else
                                          (T.INFO if self.ctl.cfg.ps5.anahtar else T.FAINT))
        info = self.ctl.engine_info or {}
        eng = info.get("kalite") or info.get("hizli") or "…"
        self.foot.setText(f"<span style='color:{dot}'>●</span> {name}<br>"
                          f"<span style='color:{psc}'>●</span> PS5 &nbsp; <span style='color:{tvc}'>●</span> TV"
                          f" &nbsp;·&nbsp; Çeviri: {eng}<br>v{__version__}")

    def open_wizard(self) -> None:
        from .wizard import Wizard
        Wizard(self.ctl, self).exec()

    def closeEvent(self, e) -> None:  # noqa: ANN001, N802
        self.ctl.shutdown()
        super().closeEvent(e)
        # Ana pencere kapanınca program kesin kapansın. Çeviri sürerken katman penceresi de açık olduğundan Qt "son
        # pencere kapandı" demiyor, program penceresiz açık kalıp port 8787'yi tutuyordu (Windows denemesinde görüldü).
        from PySide6.QtWidgets import QApplication
        QApplication.quit()


def app_icon() -> QIcon:
    """Pencere / görev çubuğu simgesi (tools/marka_gorsel.py): küçük boyutlarda yazısız, büyükte yazılı sürüm."""
    from PySide6.QtGui import QPixmap
    from .widgets import marka_image
    icon = QIcon()
    small, big = marka_image("simge_yazisiz.png"), marka_image("simge.png")
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        src = big if size >= 128 and not big.isNull() else small
        if not src.isNull():
            icon.addPixmap(QPixmap.fromImage(src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
    return icon
