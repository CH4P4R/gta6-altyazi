"""Ana pencere ve sayfalar."""

from __future__ import annotations

import time
import webbrowser

from PySide6.QtCore import Qt, QTimer
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
        right = vbox(hbox(self.lat, label("ms", "muted"), None, spacing=4), self.lat_sub, self.spark, spacing=2)
        hero.add(hbox(self.start, 18, left, None, right, spacing=10))
        root.addWidget(hero)

        # --- durum kartları
        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_ps = StatusCard("ps", "PS5 / chiaki-ng", "chiaki-ng'yi aç", ctl.launch_chiaki)
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
        ctl.tvStatus.connect(self.on_tv)
        ctl.enginesReady.connect(self.on_engines)
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
            "hazir": ("Çeviriyi başlat", "chiaki-ng'de PS5'e bağlandıysan başlat düğmesine bas.", "Hazır"),
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

    def on_source(self, ok: bool, title: str) -> None:
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
        steps.add(label("1 · TV'de bir kerelik hazırlık (TCL / Google TV)", "h2"))
        steps.add(label("① Ayarlar › Sistem › Hakkında › <b>Android TV OS derlemesi</b> satırına art arda 7 kez bas.<br>"
                        "② Ayarlar › Sistem › <b>Geliştirici seçenekleri</b>'ne gir.<br>"
                        "③ <b>USB hata ayıklama</b> varsa aç. Yoksa ya da TV bulunamazsa <b>Kablosuz hata ayıklama</b>'yı aç "
                        "ve aşağıdaki eşleştirme kısmını kullan.", "muted", wrap=True))
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
        conn.add(hbox(field("Mod", self.mode), None, self.auto, spacing=16))
        self.connect_btn = button("Bağlan, kur ve başlat", "primary", self._connect)
        self.test_btn = button("Deneme altyazısı gönder", None, ctl.tv_test)
        conn.add(hbox(self.connect_btn, self.test_btn, None))
        self.status = label("", "muted", wrap=True)
        conn.add(self.status)
        pair = Card(inner=True, margins=14)
        pair.add(label("Kablosuz hata ayıklama ile eşleştirme (gerekirse)", "h3"))
        pair.add(label("TV'de Kablosuz hata ayıklama › Eşleştirme koduyla cihaz eşleştir. Ekranda çıkan adres:port ve "
                       "6 haneli kodu yaz.", "faint", wrap=True))
        self.pair_addr = QLineEdit()
        self.pair_addr.setPlaceholderText("192.168.1.40:37123")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("123456")
        self.pair_code.setFixedWidth(110)
        pair.add(hbox(self.pair_addr, self.pair_code, button("Eşleştir", None, self._pair), spacing=10))
        conn.add(pair)
        root.addWidget(conn)

        cal = Card()
        cal.add(label("3 · Konum ayarı (gerekirse)", "h2"))
        cal.add(label("TV görüntüyü kenarlardan kırpıyorsa (overscan) yazılar biraz kayabilir. Deneme altyazısı "
                      "gönderip kaydırıcılarla düzelt.", "muted", wrap=True))
        x, y, w, h = ctl.cfg.tv.kalibrasyon
        self.cal = [slider(-50, 50, int(x * 1000)), slider(-50, 50, int(y * 1000)),
                    slider(900, 1100, int(w * 1000)), slider(900, 1100, int(h * 1000))]
        grid = QGridLayout()
        for i, (name, s) in enumerate(zip(("Sağa/sola kaydır", "Yukarı/aşağı kaydır", "Genişlik", "Yükseklik"),
                                          self.cal)):
            grid.addWidget(label(name, "h3"), i // 2, (i % 2) * 2)
            grid.addWidget(s, i // 2, (i % 2) * 2 + 1)
        cal.add(grid)
        cal.add(hbox(button("Kaydet ve dene", "primary", self._save_cal), button("Sıfırla", "ghost", self._reset_cal),
                     None))
        root.addWidget(cal)
        root.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll_page(content))
        ctl.tvStatus.connect(self.on_status)
        ctl.tvFound.connect(self.on_found)
        self.on_status(*ctl.tv_state)

    def _save_common(self) -> None:
        cfg = self.ctl.edit_config()
        cfg.tv.ip = self.ip.text().strip()
        cfg.tv.mod = self.mode.currentData()
        cfg.tv.otomatik = self.auto.isChecked()
        cfg.tv.kalibrasyon = [self.cal[0].value() / 1000, self.cal[1].value() / 1000,
                              self.cal[2].value() / 1000, self.cal[3].value() / 1000]
        self.ctl.apply_config(cfg)

    def _connect(self) -> None:
        if not self.ip.text().strip():
            self.status.setText("Önce TV'nin IP adresini yaz ya da \"Ağda ara\"ya bas.")
            return
        self._save_common()
        self.ctl.tv_connect(self.ip.text().strip(), force_install=True)

    def _scan(self) -> None:
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

    def _save_cal(self) -> None:
        self._save_common()
        self.ctl.tv_test()

    def _reset_cal(self) -> None:
        for s, v in zip(self.cal, (0, 0, 1000, 1000)):
            s.setValue(v)

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
        fast.lay.addStretch(1)
        row.addWidget(fast, 1)
        q = Card()
        q.add(label("Kalite katmanı (yapay zeka)", "h2"))
        self.qual = combo([("claude", "Claude (önerilen)"), ("gemini", "Google Gemini"), ("deepl", "DeepL"),
                           ("yok", "Kapalı")], c.kalite)
        q.add(self.qual)
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
        self.deepl.setPlaceholderText("DeepL anahtarı")
        self.claude_box = vbox(field("Claude API anahtarı", self.key), self.model, self.fastmode, spacing=8)
        q.add(self.claude_box)
        q.add(self.gem)
        q.add(self.deepl)
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
        cache.add(hbox(vbox(label("Önbellek", "h2"), self.cache_l), None,
                       button("Klasörü aç", None, self._open_data)))
        root.addWidget(cache)
        root.addLayout(hbox(None, button("Kaydet", "primary", self.save)))
        root.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll_page(content))
        self._results: list[str] = []
        ctl.testResult.connect(self.on_test)
        ctl.enginesReady.connect(lambda i: self.cache_l.setText(f"{i.get('onbellek', 0)} çeviri kayıtlı"))
        if ctl.engine_info:
            self.cache_l.setText(f"{ctl.engine_info.get('onbellek', 0)} çeviri kayıtlı")
        self._vis()

    def _vis(self) -> None:
        k = self.qual.currentData()
        for w in (self.key, self.model, self.fastmode):
            w.setVisible(k == "claude")
        self.claude_box.itemAt(0).layout().itemAt(0).widget().setVisible(k == "claude")
        self.gem.setVisible(k == "gemini")
        self.deepl.setVisible(k == "deepl")

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

    def save(self) -> None:
        cfg = self.ctl.edit_config()
        c = cfg.ceviri
        c.hizli = self.fast.currentData()
        c.kalite = self.qual.currentData()
        c.claude_anahtar = self.key.text().strip()
        c.claude_model = self.model.currentData()
        c.claude_hizli_mod = self.fastmode.isChecked() and c.claude_model == "claude-opus-5-5"
        c.gemini_anahtar = self.gem.text().strip()
        c.deepl_anahtar = self.deepl.text().strip()
        gl = {}
        for line in self.gloss.toPlainText().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip():
                    gl[k.strip()] = v.strip()
        c.sozluk = gl
        self.ctl.apply_config(cfg)
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
        self.src = combo([("pencere", "chiaki-ng / Remote Play penceresi"), ("capture", "Capture kart"),
                          ("video", "Video dosyası (test)")], cfg.kaynak.tur)
        self.win_name = QLineEdit(cfg.kaynak.pencere_adi)
        self.chiaki = QLineEdit(cfg.kaynak.chiaki_yolu)
        self.chiaki.setPlaceholderText(ctl.chiaki_path() or "chiaki-ng bulunamadı")
        self.cap_idx = QSpinBox()
        self.cap_idx.setRange(0, 9)
        self.cap_idx.setValue(cfg.kaynak.capture_cihaz)
        self.video = QLineEdit(cfg.kaynak.dosya)
        src.add(field("Kaynak", self.src))
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
        root.addWidget(keys)

        other = Card()
        other.add(label("Diğer", "h2"))
        other.add(hbox(button("Kurulum sihirbazını aç", None, lambda: self.window().open_wizard()),
                       button("Kayıt ve ayar klasörü", None, self._open_data),
                       button("OBS katmanını kopyala", None, self._copy_obs), None, spacing=10))
        other.add(label(f"GTA6 Altyazı {__version__} · OBS tarayıcı kaynağı: http://localhost:{cfg.sunucu.port}/obs "
                        "(1920×1080)", "faint", wrap=True))
        root.addWidget(other)
        root.addLayout(hbox(None, button("Kaydet", "primary", self.save)))
        root.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll_page(content))

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "chiaki-ng programını seç", "", "Program (*.exe);;Tümü (*)")
        if path:
            self.chiaki.setText(path)

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
        self.ctl.apply_config(cfg)
        self.window().toast.show_text("Ayarlar kaydedildi")


# ============================================================================ Pencere
class MainWindow(QMainWindow):
    PAGES = [("home", "Ana ekran", "home"), ("regions", "Okuma alanları", "regions"), ("tv", "Televizyon", "tv"),
             ("translate", "Çeviri", "translate"), ("history", "Geçmiş", "history"),
             ("settings", "Ayarlar", "settings")]

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
                     "history": HistoryPage, "settings": SettingsPage}
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
