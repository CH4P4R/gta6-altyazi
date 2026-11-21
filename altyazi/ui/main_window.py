"""Ana pencere ve sayfalar."""

from __future__ import annotations

import sys

import time
import webbrowser

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit, QSlider,
                               QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import __version__
from ..app import CHIAKI_DOWNLOAD, AppController, open_path
from ..config import BolgeCfg
from . import theme as T
from .region_editor import PRESETS, RegionCanvas
from .widgets import (Card, FeedItem, Logo, NavButton, QrCode, Sparkline, StartButton, StatusCard, Toast, button,
                      hbox, label, scroll_page, vbox)


def page_header(title: str, subtitle: str) -> QVBoxLayout:
    return vbox(label(title, "h1"), label(subtitle, "muted", wrap=True), spacing=4)


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


# ============================================================================ Ana ekran
class HomePage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(18)
        self.sub = label("Motorlar hazırlanıyor...", "muted")
        root.addLayout(vbox(label("Ana ekran", "h1"), self.sub, spacing=4))

        # --- güncelleme kartı (yeni sürüm varsa görünür)
        self.upd = Card(margins=14)
        self.upd.setStyleSheet(f"#card {{ border: 2px solid {T.A1}; }}")
        self.upd_title = label("", "h3")
        self.upd_text = label("Tek tıkla indirilir ve kurulur; ayarların, anahtarların ve paketlerin korunur. "
                              "Program kapanıp yeni sürümle yeniden açılır.", "muted", wrap=True)
        self.upd_btn = button("Güncelle", "primary", self._update)
        self.upd.add(hbox(vbox(self.upd_title, self.upd_text, spacing=2), None, self.upd_btn, spacing=14))
        self.upd.hide()
        root.addWidget(self.upd)
        ctl.updateAvailable.connect(self._on_update)
        ctl.updateProgress.connect(self._on_update_progress)

        # --- kahraman kartı
        hero = Card(margins=22)
        self.start = StartButton()
        self.start.clicked.connect(ctl.toggle)
        self.state_title = label("Hazırlanıyor", "stateTitle")
        self.state_hint = label("Çeviri modelleri ve OCR yükleniyor.", "muted", wrap=True)
        keys = ctl.cfg.kisayol
        self.keys_hint = label(f"Kısayollar: {keys.tam_ekran.upper()} ekranı çevir · {keys.duraklat.upper()} duraklat",
                               "faint")
        left = vbox(self.state_title, self.state_hint, 6, self.keys_hint, None, spacing=4)
        self.lat = label("—", "big")
        self.lat_sub = label("ortalama gecikme", "faint")
        self.spark = Sparkline()
        self.spark.setFixedWidth(210)
        # Claude harcama sayacı (kalite katmanı Claude ise görünür)
        self.spend = label("", "muted")
        self.spend_sub = label("", "faint")
        tip = ("Claude'un her yanıtta bildirdiği token sayısı × Anthropic liste fiyatı. Önbellekten ve hazır paketten\n"
               "gelen çeviriler ücretsizdir. Kesin fatura: console.anthropic.com › Billing.")
        self.spend.setToolTip(tip)
        self.spend_sub.setToolTip(tip)
        self.spend_box = vbox(8, self.spend, self.spend_sub, spacing=0)
        right = vbox(hbox(self.lat, label("ms", "muted"), None, spacing=4), self.lat_sub, self.spark,
                     self.spend_box, spacing=2)
        hero.add(hbox(self.start, 18, left, None, right, spacing=10))
        root.addWidget(hero)

        # --- durum kartları
        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_ps = StatusCard("ps", "PS5", "chiaki-ng'yi aç", self._ps_action)
        self.tv_play_btn = button("TV'de oynuyorum (chiaki'siz)", None, self._open_ps5,
                                  "Oyunu TV'de oynarsın; bilgisayar PS5'e arka planda ikinci hesapla bağlanır")
        self.c_ps.add(self.tv_play_btn)
        self.c_tv = StatusCard("tv", "Televizyon", "TV'yi bağla", lambda: self.window().go("tv"))
        self.c_eng = StatusCard("bolt", "Çeviri motoru")
        phone = Card(margins=16, spacing=6)
        self.qr = QrCode(96)
        self.qr.setData(ctl.server_url("kumanda"))
        phone_text = vbox(hbox(label("Telefon kumandası", "h3"), None),
                          label("Telefonla okut: ekranı çevir, duraklat ve son altyazılar.", "muted", wrap=True),
                          label(ctl.server_url("kumanda").replace("http://", ""), "faint", wrap=True), None, spacing=4)
        phone.add(hbox(phone_text, self.qr, spacing=12))
        for i, w in enumerate((self.c_ps, self.c_tv, self.c_eng, phone)):
            grid.addWidget(w, 0, i)
            grid.setColumnStretch(i, 1)
        root.addLayout(grid)

        # --- canlı akış
        feed = Card(margins=18, spacing=10)
        self.fs_btn = button("Ekranı çevir", None, lambda: ctl.command("tam_ekran"),
                             "Telefon, menü, harita gibi ekrandaki tüm yazıları çevir")
        self.pause_btn = button("Duraklat", None, self._pause)
        feed.add(hbox(label("Canlı çeviriler", "h2"), None, self.fs_btn, self.pause_btn, spacing=8))
        self.empty = label("Çeviri başlayınca oyundaki yazılar burada İngilizce → Türkçe olarak akacak.", "muted",
                           wrap=True)
        self.list_w = QWidget()
        self.list_l = QVBoxLayout(self.list_w)
        self.list_l.setContentsMargins(0, 0, 4, 0)
        self.list_l.setSpacing(8)
        self.list_l.addWidget(self.empty)
        self.list_l.addStretch(1)
        feed.add(scroll_page(self.list_w), 1)
        root.addWidget(feed, 1)
        self.items: dict[int, FeedItem] = {}

        ctl.stateChanged.connect(self.on_state)
        ctl.historyChanged.connect(self.on_item)
        ctl.sourceStatus.connect(self.on_source)
        ctl.ps5Status.connect(self.on_ps5)
        ctl.tvStatus.connect(self.on_tv)
        ctl.enginesReady.connect(self.on_engines)
        ctl.spendChanged.connect(self.on_spend)
        self._spend_timer = QTimer(self)               # saatlik ortalama zamanla değişir
        self._spend_timer.timeout.connect(self.on_spend)
        self._spend_timer.start(30000)
        self.on_spend()
        self.on_state(ctl.state)
        self.on_tv(*ctl.tv_state)
        if ctl.engine_info:
            self.on_engines(ctl.engine_info)

    def _pause(self) -> None:
        r = self.ctl.command("duraklat")
        self.pause_btn.setText("Devam et" if r.get("duraklatildi") and self.ctl.pipe else "Duraklat")

    def on_state(self, s: str) -> None:
        texts = {
            "hazirlaniyor": ("Hazırlanıyor", "Çeviri modelleri ve OCR yükleniyor, birkaç saniye sürer.", "Motorlar hazırlanıyor..."),
            "hazir": ("Çeviriyi başlat", "Başlat'a bas; PS5'e arka planda bağlanılır." if
                      self.ctl.cfg.kaynak.tur == "remoteplay" else
                      "chiaki-ng'de PS5'e bağlandıysan başlat düğmesine bas.", "Hazır"),
            "calisiyor": ("Çeviri açık", "Oyundaki yazılar okunuyor ve çevriliyor. Durdurmak için tekrar bas.",
                          "Çeviri çalışıyor"),
            "hata": ("Bir sorun var", "Motorlar yüklenemedi. Çeviri sayfasından ayarları kontrol et.", "Hata"),
        }
        t, h, sub = texts.get(s, (s, "", s))
        self.state_title.setText(t)
        self.state_hint.setText(h)
        self.sub.setText(sub)
        self.start.setRunning(s == "calisiyor")
        self.start.setEnabledLook(s in ("hazir", "calisiyor"))
        self.fs_btn.setEnabled(s == "calisiyor")
        self.pause_btn.setEnabled(s == "calisiyor")
        if s != "calisiyor":
            self.pause_btn.setText("Duraklat")

    def on_item(self, it, updated: bool) -> None:  # noqa: ANN001
        if self.empty.isVisible():
            self.empty.hide()
        if updated and it.seq in self.items:
            self.items[it.seq].update_item(it)
        else:
            w = FeedItem(it)
            self.items[it.seq] = w
            self.list_l.insertWidget(0, w)
            while len(self.items) > 40:
                old = min(self.items)
                self.items.pop(old).deleteLater()
        avg = self.ctl.avg_latency()
        if avg is not None:
            self.lat.setText(f"{avg:.0f}")
        if not updated:
            self.spark.push(it.latency_ms)

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

    def _ps_action(self) -> None:
        if self.ctl.cfg.kaynak.tur == "remoteplay":
            self._open_ps5()
        else:
            self.ctl.launch_chiaki()

    def _open_ps5(self) -> None:
        from .ps5_dialog import Ps5Dialog
        Ps5Dialog(self.ctl, self).exec()
        self.ctl._check_source()

    def on_ps5(self, state: str, msg: str) -> None:
        if self.ctl.cfg.kaynak.tur != "remoteplay":
            return
        self.tv_play_btn.hide()
        self.c_ps.action.show()
        self.c_ps.action.setEnabled(True)
        if state == "yok":
            self.c_ps.set("off", "PS5 eşli değil. Bir kez bağla: ikinci PSN hesabıyla giriş ve PS5'teki 8 haneli kod.")
            self.c_ps.action.setText("PS5'i bağla")
            return
        self.c_ps.set({"bagli": "ok", "baglaniyor": "warn", "kopuk": "bad"}.get(state, "off"), msg)
        self.c_ps.action.setText("PS5 ayarları")

    def on_source(self, ok: bool, title: str) -> None:
        if self.ctl.cfg.kaynak.tur == "remoteplay":
            return
        self.tv_play_btn.setVisible(self.ctl.cfg.kaynak.tur == "pencere" and not ok)
        if self.ctl.cfg.kaynak.tur != "pencere":
            self.c_ps.set("ok", f"Kaynak: {title}")
            self.c_ps.action.hide()
            return
        self.c_ps.action.show()
        if ok:
            self.c_ps.set("ok", f"Pencere bulundu: {title}")
            self.c_ps.action.setText("chiaki-ng açık")
            self.c_ps.action.setEnabled(False)
        else:
            self.c_ps.set("off", "chiaki-ng penceresi açık değil. Aç ve PS5'e ikinci hesapla bağlan.")
            self.c_ps.action.setText("chiaki-ng'yi aç")
            self.c_ps.action.setEnabled(True)

    def on_tv(self, state: str, msg: str) -> None:
        dot = {"bagli": "ok", "baglaniyor": "warn", "onay": "info", "hata": "bad"}.get(state, "off")
        if state == "yok" or (state == "" and not msg):
            msg = "Kurulmadı. TV'de de Türkçe görmek için bağla." if not self.ctl.cfg.tv.ip else \
                f"{self.ctl.cfg.tv.ip} · çeviri başlayınca bağlanır"
        self.c_tv.set(dot, msg)
        self.c_tv.action.setText("TV ayarları" if state == "bagli" else "TV'yi bağla")

    def on_engines(self, info: dict) -> None:
        parts = [f"OCR: {info.get('ocr')}"]
        parts.append(f"Hızlı: {info['hizli']}" if info.get("hizli") else "Hızlı katman yok")
        parts.append(f"Kalite: {info['kalite']}" if info.get("kalite") else "Kalite katmanı kapalı")
        ok = bool(info.get("hizli") or info.get("kalite"))
        self.c_eng.set("ok" if ok else "bad", "\n".join(parts))
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


# ============================================================================ Alanlar
class RegionsPage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        self.zones: list[BolgeCfg] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)
        root.addLayout(page_header("Okuma alanları", "Uygulama sadece bu kutuların içindeki yazıları okur. Kutuları "
                                   "fareyle taşı ve köşelerinden boyutlandır. Kırmızı noktalar, uygulamanın "
                                   "\"yazı\" saydığı pikselleri gösterir."))
        body = QHBoxLayout()
        body.setSpacing(16)
        left = Card(margins=14)
        self.canvas = RegionCanvas()
        self.canvas.selected.connect(self.select)
        self.canvas.changed.connect(self._dirty)
        self.mask_cb = QCheckBox("Algılanan yazıyı kırmızı göster")
        self.mask_cb.setChecked(True)
        self.mask_cb.toggled.connect(self._mask)
        left.add(self.canvas, 1)
        left.add(hbox(button("Görüntü al", "primary", ctl.grab_frame, "chiaki penceresinden (ya da kaynaktan) bir kare al"),
                      button("Resim aç", None, self._open_image), self.mask_cb, None, spacing=10))
        body.addWidget(left, 3)

        right = Card(margins=16, spacing=12)
        right.setFixedWidth(330)
        self.list = QListWidget()
        self.list.setFixedHeight(120)
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
        self.color = QCheckBox("Renkli kelimeleri de oku (sarı, mavi vurgular)")
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

    def _apply_preset(self, idx: int) -> None:
        if idx <= 0 or not self.current():
            return
        alan, tur, hiz, capa = PRESETS[self.preset.itemText(idx)]
        z = self.current()
        z.alan, z.tur, z.hizalama, z.capa = list(alan), tur, hiz, capa
        self.preset.setCurrentIndex(0)
        self.select(self.canvas.sel)
        self.canvas.refresh_mask()
        self._fill_list()
        self._dirty()

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


# ============================================================================ TV
class TvPage(QWidget):
    _fwText = Signal(str)                      # arka plan iş parçacığından güvenlik duvarı durumu
    _fwDone = Signal()

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        content = QWidget()
        content.setObjectName("page")
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)
        root.addLayout(page_header("Televizyon", "Türkçe altyazı TV'de oyunun üstünde görünür. Sen HDMI'dan "
                                   "gecikmesiz oynarsın, bilgisayar arka planda okur ve TV'ye gönderir."))
        steps = Card()
        from .. import rehber
        self.brand = combo(rehber.TV_BRANDS, ctl.cfg.tv.marka)
        self.brand.currentIndexChanged.connect(self._brand_changed)
        steps.add(hbox(label("TV markası", "h2"), self.brand, None, spacing=14))
        steps.add(hbox(label("1 · TV'de bir kerelik hazırlık", "h2"), None,
                       button("Resimli anlat", None, self._open_guide), spacing=10))
        self.howto = label("", "muted", wrap=True)
        self.howto.setTextFormat(Qt.RichText)
        steps.add(self.howto)
        root.addWidget(steps)

        conn = Card()
        conn.add(label("2 · Bağlan ve kur", "h2"))
        self.ip = QLineEdit(ctl.cfg.tv.ip)
        self.ip.setPlaceholderText("TV'nin IP adresi, ör. 192.168.1.40")
        self.scan_btn = button("Ağda ara", None, self._scan)
        self.found = QComboBox()
        self.found.hide()
        self.found.currentIndexChanged.connect(lambda i: self.ip.setText(self.found.itemData(i) or self.ip.text()))
        conn.add(hbox(self.ip, self.scan_btn, self.found, spacing=10))
        self.mode = combo([("otomatik", "Otomatik (önerilen)"), ("katman", "Oyunun üstüne katman"),
                           ("hdmi", "Yedek mod: HDMI uygulama içinde")], ctl.cfg.tv.mod)
        self.auto = QCheckBox("Çeviri başlayınca TV'yi kendiliğinden bağla")
        self.auto.setChecked(ctl.cfg.tv.otomatik)
        self.mode_box = field("Mod", self.mode)
        self.lg_pass = QLineEdit(ctl.cfg.tv.lg_parola)
        self.lg_pass.setPlaceholderText("Developer Mode ekranındaki parola (ör. A1B2C3)")
        self.lg_box = QWidget()
        self.lg_box.setLayout(field("LG parola (passphrase)", self.lg_pass,
                                    "Developer Mode uygulamasında Key Server açıkken ekranda görünür."))
        self.ss_profile = QLineEdit(ctl.cfg.tv.samsung_profil)
        self.ss_tizen = QLineEdit(ctl.cfg.tv.tizen_yolu)
        self.ss_tizen.setPlaceholderText("Boş bırak: Tizen Studio gerekmez")
        self.ss_box = QWidget()
        self.ss_box.setLayout(hbox(field("Tizen Studio klasörü (gelişmiş, isteğe bağlı)", self.ss_tizen),
                                   field("Sertifika profili (yalnız Tizen Studio ile)", self.ss_profile),
                                   spacing=14))
        mode_w = QWidget()
        mode_w.setLayout(self.mode_box)
        self.mode_w = mode_w
        conn.add(hbox(mode_w, self.lg_box, self.ss_box, None, self.auto, spacing=16))
        self.connect_btn = button("Bağlan, kur ve başlat", "primary", self._connect)
        self.test_btn = button("Deneme altyazısı gönder", None, ctl.tv_test)
        conn.add(hbox(self.connect_btn, self.test_btn, None))
        self.status = label("", "muted", wrap=True)
        conn.add(self.status)
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
        conn.add(pair)
        self.pair_card = pair
        root.addWidget(conn)

        fw = Card()
        fw.add(label("3 · Bağlantı izni (Windows güvenlik duvarı)", "h2"))
        fw.add(label("TV bu bilgisayara bağlanamıyorsa çoğu zaman sebep Windows güvenlik duvarıdır. Aşağıdaki düğme "
                     "yalnız ev ağından (Özel ağ) gelen bağlantılara izin verir; ağ 'Ortak' görünüyorsa onu da 'Özel' "
                     "yapar. Windows bir kez yönetici izni ister. "
                     "TV yazının yerini kendisi ayarlar; altyazı yeri yanlışsa TV'de kumandanın Yeşil tuşu panelini açar.",
                     "muted", wrap=True))
        self.fw_state = label("", "faint", wrap=True)
        self.fw_btn = button("İzin ver", "primary", self._firewall)
        fw.add(hbox(self.fw_btn, button("Durumu yenile", "ghost", self._fw_refresh),
                    None, spacing=10))
        fw.add(self.fw_state)
        root.addWidget(fw)
        root.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll_page(content))
        ctl.tvStatus.connect(self.on_status)
        ctl.tvFound.connect(self.on_found)
        self.on_status(*ctl.tv_state)
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


# ============================================================================ Çeviri
class TranslationPage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        c = ctl.cfg.ceviri
        content = QWidget()
        content.setObjectName("page")
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)
        root.addLayout(page_header("Çeviri", "İki katman: yerel model ekran kartında anında çevirir, yapay zeka "
                                   "birkaç yüz milisaniye sonra daha doğal haliyle günceller. Her çeviri "
                                   "önbelleğe yazılır; aynı yazı tekrar çıkınca anında gelir."))
        row = QHBoxLayout()
        row.setSpacing(16)
        fast = Card()
        fast.add(label("Hızlı katman", "h2"))
        self.fast = combo([("yerel", "Yerel model (GPU, internetsiz)"), ("google", "Google Çeviri (anahtarsız)"),
                           ("yok", "Kapalı")], c.hizli)
        fast.add(self.fast)
        fast.add(label("Yerel model ekranda ~20-50 ms'de bir çeviri gösterir.", "faint", wrap=True))
        self.slang = QCheckBox("Argo düzeltme: \"gonna, ain't, homie\" gibi ifadeleri yerel modele düzgün İngilizce ver")
        self.slang.setChecked(c.argo_duzelt)
        fast.add(self.slang)
        self.scene_cb = QCheckBox("Oyundaki telefonu, harita görev kartını ve gelen mesajları kendiliğinden çevir "
                                  "(Türkçesi TV'de yanlarında çıkar)")
        self.scene_cb.setChecked(c.ekran_yazilari)
        fast.add(self.scene_cb)
        self.wait = QSpinBox()
        self.wait.setRange(0, 1500)
        self.wait.setSingleStep(50)
        self.wait.setSuffix(" ms")
        self.wait.setValue(c.kalite_bekleme_ms)
        fast.add(field("Kalite öncelikli bekleme", self.wait,
                       "Yapay zekanın çevirisi bu süre içinde gelirse yerel çeviri hiç gösterilmez; gelmezse önce yerel "
                       "çeviri çıkar, sonra güncellenir. 0 = her zaman önce yerel."))
        fast.lay.addStretch(1)
        row.addWidget(fast, 1)
        q = Card()
        q.add(label("Kalite katmanı (yapay zeka)", "h2"))
        self.qual = combo([("claude", "Claude · en iyi kalite (ücretli, kendi anahtarın)"),
                           ("gemini", "Google Gemini · ücretsiz anahtar"),
                           ("deepl", "DeepL · ücretsiz plan (ayda 500 bin karakter)"),
                           ("yerelai", "Yerel yapay zekâ · Ollama / LM Studio (ücretsiz, internetsiz)"),
                           ("yok", "Kapalı (yalnız yerel model)")], c.kalite)
        q.add(self.qual)
        q.add(label("Herkes kendi anahtarını kullanır; kimse başkasının çevirisini ödemez. Anahtar yalnız bu "
                    "bilgisayarda saklanır.", "faint", wrap=True))
        self.key = QLineEdit(c.claude_anahtar)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-...  (console.anthropic.com)")
        self.model = combo([("claude-opus-5-5", "Claude Opus 5.5 (en iyi kalite)"),
                            ("claude-haiku-5-5", "Claude Haiku 5.5 (daha hızlı ve ucuz)")], c.claude_model)
        self.fastmode = QCheckBox("Hızlı mod (Opus 5.5: ~2.5 kat hızlı, 2 kat fiyat)")
        self.fastmode.setChecked(c.claude_hizli_mod)
        self.gem = QLineEdit(c.gemini_anahtar)
        self.gem.setEchoMode(QLineEdit.Password)
        self.gem.setPlaceholderText("Gemini anahtarı (aistudio.google.com)")
        self.deepl = QLineEdit(c.deepl_anahtar)
        self.deepl.setEchoMode(QLineEdit.Password)
        self.deepl.setPlaceholderText("DeepL anahtarı (ücretsiz planda sonu :fx)")
        self.lai_url = QLineEdit(c.yerelai_adres)
        self.lai_url.setPlaceholderText("http://localhost:11434/v1")
        self.lai_model = QLineEdit(c.yerelai_model)
        self.lai_model.setPlaceholderText("qwen2.5:7b")
        self.claude_box = vbox(field("Claude API anahtarı", self.key), self.model, self.fastmode, spacing=8)
        q.add(self.claude_box)
        import webbrowser as _wb
        self.key_btn = button("Anahtar al", None, lambda: _wb.open(self._key_url()))
        q.add(hbox(self.gem, self.deepl, self.key_btn, spacing=8))
        self.lai_box = QWidget()
        self.lai_box.setLayout(vbox(hbox(field("Sunucu adresi", self.lai_url), field("Model", self.lai_model),
                                         spacing=10),
                                    hbox(button("Ollama", None, lambda: self._lai_preset("ollama")),
                                         button("LM Studio", None, lambda: self._lai_preset("lmstudio")),
                                         button("Ollama'yı indir", "ghost", lambda: _wb.open("https://ollama.com/download")),
                                         None, spacing=8),
                                    label("Ollama'yı kurup komut satırında <b>ollama pull qwen2.5:7b</b> yaz. Ekran kartı "
                                          "olan bilgisayarda bir satır genelde 1-2 saniyede gelir.", "faint", wrap=True),
                                    spacing=8))
        q.add(self.lai_box)
        self.qual.currentIndexChanged.connect(self._vis)
        row.addWidget(q, 1)
        root.addLayout(row)

        test = Card()
        test.add(label("Dene", "h2"))
        self.test_in = QLineEdit("You think you can just walk in here and take what's mine, man?")
        test.add(hbox(self.test_in, button("Çevir", "primary", self._test)))
        self.test_out = label("", "muted", wrap=True)
        test.add(self.test_out)
        root.addWidget(test)

        gl = Card()
        gl.add(label("Sözlük", "h2"))
        gl.add(label("Her satıra bir terim: <b>İngilizce = Türkçe</b>. Yapay zeka bunlara uyar. İsimleri olduğu gibi "
                     "bırakmak için iki tarafa aynısını yaz (ör. Vice City = Vice City).", "muted", wrap=True))
        self.gloss = QPlainTextEdit("\n".join(f"{k} = {v}" for k, v in c.sozluk.items()))
        self.gloss.setFixedHeight(110)
        gl.add(self.gloss)
        root.addWidget(gl)

        cache = Card()
        self.cache_l = label("", "muted")
        cache.add(hbox(vbox(label("Önbellek ve çeviri paketleri", "h2"), self.cache_l), None,
                       button("Klasörü aç", None, self._open_data)))
        cache.add(label("Hazır çeviri paketi varsa pakette olan satırlar anında ve ücretsiz gelir, yapay zekaya sorulmaz. "
                        "GameTranslator/topluluk paket biçimi (.json ya da .json.gz) desteklenir; paket dosyasını kendin "
                        "edinip buradan ekle. Kendi önbelleğini de paket olarak arkadaşlarına verebilirsin.",
                        "faint", wrap=True))
        self.packs_l = label("", "muted", wrap=True)
        cache.add(self.packs_l)
        from ..packs import CATALOG
        self.pack_combo = QComboBox()
        for pid, title in CATALOG:
            self.pack_combo.addItem(title, pid)
        self.pack_dl = button("Hazır paketi indir", "primary", self._download_pack)
        cache.add(hbox(self.pack_combo, self.pack_dl, button("Listeyi yenile", "ghost", ctl.load_pack_catalog), None,
                       spacing=10))
        cache.add(label("Paketler bu projenin GitHub sayfasından iner; her 6 saatte bir CouchSubs (GTA 6 dahil) ve "
                        "GameTranslator'dan güncellenir. GTA 6 paketi kurulumla birlikte de gelir.", "faint", wrap=True))
        ctl.packCatalog.connect(self._on_catalog)
        ctl.load_pack_catalog()
        cache.add(hbox(button("Paket ekle", None, self._add_pack),
                       button("Önbelleği paket olarak kaydet", None, self._export_pack), None, spacing=10))
        root.addWidget(cache)
        root.addLayout(hbox(None, button("Kaydet", "primary", self.save)))
        root.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll_page(content))
        self._results: list[str] = []
        ctl.testResult.connect(self.on_test)
        ctl.packProgress.connect(self._pack_progress)
        ctl.enginesReady.connect(lambda i: (self.cache_l.setText(f"{i.get('onbellek', 0)} çeviri kayıtlı"),
                                            self._refresh_packs()))
        if ctl.engine_info:
            self.cache_l.setText(f"{ctl.engine_info.get('onbellek', 0)} çeviri kayıtlı")
        self._vis()

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        """Sayfa her açıldığında anahtar alanlarını güncel ayardan doldur (sihirbazda girilen anahtar burada boş
        görünüp 'Kaydet'le silinmesin)."""
        c = self.ctl.cfg.ceviri
        for w, val in ((self.key, c.claude_anahtar), (self.gem, c.gemini_anahtar), (self.deepl, c.deepl_anahtar)):
            if w.text().strip() != val and not w.hasFocus():
                w.setText(val)
        i = self.qual.findData(c.kalite)
        if i >= 0 and self.qual.currentIndex() != i:
            self.qual.setCurrentIndex(i)
        super().showEvent(e)

    def _vis(self) -> None:
        k = self.qual.currentData()
        for w in (self.key, self.model, self.fastmode):
            w.setVisible(k == "claude")
        self.claude_box.itemAt(0).layout().itemAt(0).widget().setVisible(k == "claude")
        self.gem.setVisible(k == "gemini")
        self.deepl.setVisible(k == "deepl")
        self.key_btn.setVisible(k in ("claude", "gemini", "deepl"))
        self.lai_box.setVisible(k == "yerelai")

    def _key_url(self) -> str:
        from .. import rehber
        return {"claude": rehber.CLAUDE_KEYS, "gemini": rehber.GEMINI_KEYS,
                "deepl": rehber.DEEPL_SIGNUP}.get(self.qual.currentData(), rehber.CLAUDE_KEYS)

    def _lai_preset(self, kind: str) -> None:
        self.lai_url.setText("http://localhost:11434/v1" if kind == "ollama" else "http://localhost:1234/v1")
        if kind == "ollama" and not self.lai_model.text().strip():
            self.lai_model.setText("qwen2.5:7b")

    def _test(self) -> None:
        self._results = []
        self.test_out.setText("Çevriliyor...")
        self.ctl.test_translation(self.test_in.text())

    def on_test(self, r) -> None:  # noqa: ANN001
        self._results.append(f"<b>{r.text}</b> <span style='color:{T.FAINT}'>· {r.source} · {r.ms:.0f} ms</span>")
        self.test_out.setText("<br>".join(self._results))

    def _open_data(self) -> None:
        from .. import paths
        open_path(str(paths.data_dir()))

    def _refresh_packs(self) -> None:
        ps = self.ctl.pack_list()
        self.packs_l.setText("Yüklü paketler: " + ", ".join(f"<b>{p.title}</b> ({p.count:,} satır)".replace(",", ".")
                                                             for p in ps) if ps else "Yüklü paket yok.")

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
        c.kalite_bekleme_ms = self.wait.value()
        c.kalite = self.qual.currentData()
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
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)
        root.addLayout(page_header("Geçmiş", "Bu oturumda çevrilen tüm yazılar. Kaliteli çeviri gelince satır "
                                   "kendiliğinden güncellenir."))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara...")
        self.search.textChanged.connect(self._filter)
        root.addLayout(hbox(self.search, button("Metin olarak kaydet", None, self._export)))
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

    def on_item(self, it, updated: bool) -> None:  # noqa: ANN001
        vals = [time.strftime("%H:%M:%S"), "ekran" if it.zone.startswith("tam") else it.zone, it.english, it.text,
                it.source, f"{it.latency_ms:.0f}"]
        if updated and it.seq in self.rows:
            row = self.table.rowCount() - 1 - self.rows[it.seq]
            for c in (3, 4, 5):
                self.table.setItem(row, c, QTableWidgetItem(vals[c]))
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

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", "gta6-ceviriler.txt", "Metin (*.txt)")
        if path:
            lines = []
            for r in range(self.table.rowCount() - 1, -1, -1):
                lines.append(f"[{self.table.item(r, 0).text()}] {self.table.item(r, 2).text()}\n"
                             f"    → {self.table.item(r, 3).text()}")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))


# ============================================================================ Ayarlar
class SettingsPage(QWidget):
    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        cfg = ctl.cfg
        content = QWidget()
        content.setObjectName("page")
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)
        root.addLayout(page_header("Ayarlar", "Görüntü kaynağı, ekran, kısayollar ve diğerleri."))

        src = Card()
        src.add(label("Görüntü kaynağı", "h2"))
        self.src = combo([("remoteplay", "PS5'e arka planda bağlan (TV'de oynarken; chiaki gerekmez)"),
                          ("pencere", "chiaki-ng / Remote Play penceresi"), ("capture", "Capture kart"),
                          ("video", "Video dosyası (test)")], cfg.kaynak.tur)
        self.where = combo([("tv", "TV'de oynuyorum (Türkçe yalnız TV'de)"),
                            ("ikisi", "TV'de ve bilgisayarda"), ("monitor", "Bilgisayar ekranında")],
                           cfg.kaynak.oyun_yeri)
        self.ps5_auto = QCheckBox("PS5 açılınca çeviri kendiliğinden başlasın (PS5'e arka planda bağlanırken)")
        self.ps5_auto.setChecked(cfg.ps5.acilinca_baslat)
        self.win_name = QLineEdit(cfg.kaynak.pencere_adi)
        self.chiaki = QLineEdit(cfg.kaynak.chiaki_yolu)
        self.chiaki.setPlaceholderText(ctl.chiaki_path() or "chiaki-ng bulunamadı")
        self.cap_idx = QSpinBox()
        self.cap_idx.setRange(0, 9)
        self.cap_idx.setValue(cfg.kaynak.capture_cihaz)
        self.video = QLineEdit(cfg.kaynak.dosya)
        src.add(field("Kaynak", self.src))
        src.add(field("Oyunu nerede oynuyorsun", hbox(self.where, button("PS5'i bağla", None, self._open_ps5),
                                                      spacing=10),
                      "TV'de oynarken bilgisayar PS5'e ikinci PSN hesabıyla arka planda bağlanıp yalnız altyazıyı okur."))
        src.add(self.ps5_auto)
        src.add(field("Pencere başlığında geçen", self.win_name, "chiaki-ng için \"chiaki\", resmi uygulama için "
                                                                  "\"PS Remote Play\", Veyra için \"Veyra\"."))
        src.add(field("chiaki-ng programı", hbox(self.chiaki, button("Gözat", None, self._browse),
                                                 button("İndir", "ghost", lambda: webbrowser.open(CHIAKI_DOWNLOAD)))))
        src.add(hbox(field("Capture kart numarası", self.cap_idx), field("Video dosyası", self.video), spacing=16))
        root.addWidget(src)

        disp = Card()
        disp.add(label("Ekran", "h2"))
        self.mode = combo([("overlay", "chiaki penceresinin üstüne katman (önerilen)"),
                           ("pencere", "Görüntüyü kendi penceresinde göster (capture kart)")], cfg.gosterim.mod)
        self.latency = QCheckBox("Sağ üstte gecikmeyi göster")
        self.latency.setChecked(cfg.gosterim.gecikme_goster)
        self.font_name = QLineEdit(cfg.gosterim.yazi_tipi)
        disp.add(field("Gösterim", self.mode))
        disp.add(hbox(field("Yazı tipi", self.font_name), self.latency, spacing=16))
        root.addWidget(disp)

        keys = Card()
        keys.add(label("Kısayollar", "h2"))
        self.k_fs = QLineEdit(cfg.kisayol.tam_ekran)
        self.k_pause = QLineEdit(cfg.kisayol.duraklat)
        self.fs_time = QSpinBox()
        self.fs_time.setRange(5, 120)
        self.fs_time.setValue(cfg.kisayol.tam_ekran_sure)
        self.fs_time.setSuffix(" sn")
        keys.add(hbox(field("Ekranı çevir", self.k_fs), field("Duraklat", self.k_pause),
                      field("Ekran çevirisi kalma süresi", self.fs_time), spacing=16))
        keys.add(label("Örnek: ctrl+shift+9, alt+f10, num9. TV'den oynarken aynı düğmeler telefon kumandasında da var.",
                       "faint", wrap=True))
        self.fs_vision = QCheckBox("Ekranı çevirirken Claude görsel okuma kullan (menü, telefon ve süslü yazılarda daha "
                                   "doğru; 2-4 sn sürer, Claude anahtarı gerekir)")
        self.fs_vision.setChecked(cfg.kisayol.tam_ekran_gorsel)
        keys.add(self.fs_vision)
        root.addWidget(keys)

        auto = Card()
        o = cfg.otomatik
        auto.add(label("TV günleri: kendiliğinden çalışma", "h2"))
        auto.add(label("Kasa başka odadayken her şey kendiliğinden olsun: sen TV'de PS5'i açarsın, kasa chiaki'yi "
                       "bağlar, çeviri başlar ve TV'ye altyazı gider. PS5'i kapatınca hepsi durur.", "muted", wrap=True))
        self.a_boot = QCheckBox("Bilgisayar açılınca GTA6 Altyazı da açılsın (simge durumunda)")
        self.a_boot.setChecked(o.windows_ile_baslat)
        self.a_src = QCheckBox("chiaki bağlanınca çeviri kendiliğinden başlasın, kapanınca dursun")
        self.a_src.setChecked(o.chiaki_gorunce_baslat)
        self.a_ps5 = QCheckBox("PS5 açılınca chiaki kendiliğinden bağlansın")
        self.a_ps5.setChecked(o.ps5_acilinca_baglan)
        self.a_fs = QCheckBox("Otomatik bağlanınca chiaki tam ekran açılsın")
        self.a_fs.setChecked(o.chiaki_tam_ekran)
        for w in (self.a_boot, self.a_src, self.a_ps5, self.a_fs):
            auto.add(w)
        self.ps5_name = QLineEdit(o.ps5_adi)
        self.ps5_name.setPlaceholderText("PS5 adı (ör. PS5-123)")
        self.ps5_ip = QLineEdit(o.ps5_ip)
        self.ps5_ip.setPlaceholderText("PS5 IP adresi")
        self.ps5_btn = button("PS5'i bul", None, self._find_ps5)
        auto.add(hbox(self.ps5_name, self.ps5_ip, self.ps5_btn, spacing=10))
        auto.add(label("PS5'in adı chiaki'de kayıtlı adla aynı olmalı. \"PS5'i bul\" PS5 açıkken ya da dinlenme "
                       "modundayken ağdan bulur. Telefon kumandasında da Başlat/Durdur ve PS5'e bağlan düğmeleri var.",
                       "faint", wrap=True))
        root.addWidget(auto)
        upd = Card()
        upd.add(label("Güncellemeler", "h2"))
        self.u_pack = QCheckBox("Hazır paketlerin (GTA 6 dahil) yenisini açılışta kendiliğinden indir")
        self.u_pack.setChecked(o.paket_guncelle)
        self.u_app = QCheckBox("Yeni sürüm çıkınca ana ekranda haber ver (tek tıkla güncellenir)")
        self.u_app.setChecked(o.surum_denetle)
        upd.add(self.u_pack)
        upd.add(self.u_app)
        upd.add(label("Kurulumu yeniden yapmana gerek yok: paketler sessizce güncellenir, uygulama Güncelle düğmesiyle "
                      "kendini yeniler. Ayarların, anahtarların ve paketlerin korunur.", "faint", wrap=True))
        root.addWidget(upd)
        ctl.ps5Found.connect(self._on_ps5)

        other = Card()
        other.add(label("Diğer", "h2"))
        other.add(hbox(button("Kurulum sihirbazını aç", None, lambda: self.window().open_wizard()),
                       button("Kayıt ve ayar klasörü", None, self._open_data),
                       button("OBS katmanını kopyala", None, self._copy_obs), None, spacing=10))
        other.add(label(f"GTA6 Altyazı {__version__} · OBS tarayıcı kaynağı: http://localhost:{cfg.sunucu.port}/obs "
                        "(1920×1080)", "faint", wrap=True))
        credit = label("GNU AGPL-3.0 ile lisanslıdır. Sinan Yorulmaz'ın <a href='https://github.com/yorulmazsinan/couchsubs'>"
                       "CouchSubs</a> projesinden ve <a href='https://gitlab.com/sefflex/GameTranslator'>GameTranslator</a>"
                       "'dan alınan kodları içerir. Kaynak kodu: <a href='https://github.com/CH4P4R/gta6-altyazi'>"
                       "github.com/CH4P4R/gta6-altyazi</a>", "faint", wrap=True)
        credit.setOpenExternalLinks(True)
        other.add(credit)
        root.addWidget(other)
        root.addLayout(hbox(None, button("Kaydet", "primary", self.save)))
        root.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll_page(content))

    def _open_ps5(self) -> None:
        from .ps5_dialog import Ps5Dialog
        Ps5Dialog(self.ctl, self).exec()
        self._sync_source()
        self.ctl._check_source()

    def _sync_source(self) -> None:
        """Ayarlar başka yerden değiştiyse (PS5 eşlendi) seçimleri güncelle; eski seçim Kaydet'le geri yazılmasın."""
        for w, value in ((self.src, self.ctl.cfg.kaynak.tur), (self.where, self.ctl.cfg.kaynak.oyun_yeri)):
            i = w.findData(value)
            if i >= 0:
                w.setCurrentIndex(i)

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        self._sync_source()
        super().showEvent(e)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "chiaki-ng programını seç", "/Applications" if sys.platform == "darwin" else "",
                                                  "Program (*.app *.exe);;Tümü (*)")
        if path:
            self.chiaki.setText(path)

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

    def _open_data(self) -> None:
        from .. import paths
        open_path(str(paths.data_dir()))

    def _copy_obs(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(f"http://localhost:{self.ctl.cfg.sunucu.port}/obs")
        self.window().toast.show_text("OBS adresi kopyalandı")

    def save(self) -> None:
        cfg = self.ctl.edit_config()
        cfg.kaynak.tur = self.src.currentData()
        cfg.kaynak.oyun_yeri = self.where.currentData()
        cfg.ps5.acilinca_baslat = self.ps5_auto.isChecked()
        cfg.kaynak.pencere_adi = self.win_name.text().strip() or "chiaki"
        cfg.kaynak.chiaki_yolu = self.chiaki.text().strip()
        cfg.kaynak.capture_cihaz = self.cap_idx.value()
        cfg.kaynak.dosya = self.video.text().strip()
        cfg.gosterim.mod = self.mode.currentData()
        cfg.gosterim.gecikme_goster = self.latency.isChecked()
        cfg.gosterim.yazi_tipi = self.font_name.text().strip() or "Segoe UI Semibold"
        cfg.kisayol.tam_ekran = self.k_fs.text().strip()
        cfg.kisayol.duraklat = self.k_pause.text().strip()
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


# ============================================================================ Pencere
# ============================================================================ Rehber
class GuidePage(QWidget):
    """Bütün süreçlerin resimli, adım adım anlatımı (içerik: altyazi/rehber.py; README'deki rehberle aynı)."""

    def __init__(self, ctl: AppController):
        super().__init__()
        from PySide6.QtWidgets import QButtonGroup, QPushButton

        from .. import rehber
        from .guide import Guide

        self.ctl = ctl
        content = QWidget()
        content.setObjectName("page")
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)
        root.addLayout(page_header("Rehber", "Kurulumdan yayına, her şeyin resimli anlatımı. Soldan konuyu seç, "
                                   "adımları sırayla izle."))
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
                f"QPushButton {{ text-align: left; border-radius: 12px; background: {T.SURFACE};"
                f" border: 1px solid {T.BORDER}; }} QPushButton:hover {{ border-color: {T.BORDER_HI}; }}"
                f"QPushButton:checked {{ background: {T.SURFACE2}; border: 2px solid {T.A1}; }}")
            b.clicked.connect(lambda _=False, k=i: self.show_guide(k))
            self.group.addButton(b, i)
            side.addWidget(b)
        side.addStretch(1)
        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setFixedWidth(330)
        side_scroll = scroll_page(side_w)
        side_scroll.setFixedWidth(346)
        body.addWidget(side_scroll)
        card = Card()
        self.heading = label("", "h2")
        card.add(self.heading)
        self.guide = Guide(nav=True)
        self.guide.setMinimumHeight(560)
        card.add(self.guide)
        body.addWidget(card, 1)
        root.addLayout(body, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(content)
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


class MainWindow(QMainWindow):
    PAGES = [("home", "Ana ekran", "home"), ("regions", "Okuma alanları", "regions"), ("tv", "Televizyon", "tv"),
             ("translate", "Çeviri", "translate"), ("history", "Geçmiş", "history"),
             ("guide", "Rehber", "guide"), ("settings", "Ayarlar", "settings")]

    def __init__(self, ctl: AppController):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle("GTA6 Altyazı")
        self.setWindowIcon(app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1100, 720)
        central = QWidget()
        central.setObjectName("page")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 20, 16, 18)
        sl.setSpacing(4)
        sl.addWidget(Logo())
        sl.addSpacing(22)
        self.nav: dict[str, NavButton] = {}
        self.stack = QStackedWidget()
        factories = {"home": HomePage, "regions": RegionsPage, "tv": TvPage, "translate": TranslationPage,
                     "history": HistoryPage, "guide": GuidePage, "settings": SettingsPage}
        self.pages: dict[str, QWidget] = {}
        for key, text, icon in self.PAGES:
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
        self.go("home")
        ctl.notice.connect(lambda m: self.toast.show_text(m))
        ctl.stateChanged.connect(self._foot)
        ctl.enginesReady.connect(lambda _i: self._foot(ctl.state))
        self._foot(ctl.state)

    def go(self, key: str) -> None:
        for k, b in self.nav.items():
            b.setChecked(k == key)
        self.stack.setCurrentWidget(self.pages[key])

    def _foot(self, state: str) -> None:
        info = self.ctl.engine_info
        dot = {"calisiyor": T.OK, "hazir": T.INFO, "hazirlaniyor": T.WARN, "hata": T.BAD}.get(state, T.MUTED)
        name = {"calisiyor": "Çeviri açık", "hazir": "Hazır", "hazirlaniyor": "Hazırlanıyor", "hata": "Hata"}.get(state, state)
        ocr = info.get("ocr", "...") if info else "..."
        self.foot.setText(f"<span style='color:{dot}'>●</span> {name}<br>OCR: {ocr}<br>v{__version__}")

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
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(8, 8, 240, 240)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())))
    p.drawRoundedRect(r, 60, 60)
    f = T.font(10, QFont.Black, display=True)
    f.setPixelSize(96)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(r.adjusted(0, -40, 0, -40), Qt.AlignCenter, "TR")
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(56, 166, 144, 16), 8, 8)
    p.setBrush(QColor(255, 255, 255, 190))
    p.drawRoundedRect(QRectF(82, 194, 92, 16), 8, 8)
    p.end()
    return QIcon(pm)
