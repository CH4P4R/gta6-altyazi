"""İlk açılış kurulum sihirbazı."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLineEdit,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..app import CHIAKI_DOWNLOAD, AppController
from . import theme as T
from .widgets import Card, Dot, Icon, Logo, PreviewArt, QrCode, Stepper, button, hbox, label, vbox

STEPS = ["Hoş geldin", "PS5 bağlantısı", "Televizyon", "Çeviri", "Hazır"]


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


class Wizard(QDialog):
    def __init__(self, ctl: AppController, parent=None):  # noqa: ANN001
        super().__init__(parent)
        self.ctl = ctl
        self.cfg = ctl.edit_config()
        self.setWindowTitle("GTA6 Altyazı · Kurulum")
        self.setModal(True)
        self.resize(1040, 680)
        self.setMinimumSize(980, 640)
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

        for builder in (self._welcome, self._ps5, self._tv, self._translation, self._done):
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

    def _ps5(self) -> QWidget:
        w, lay = self._page("PS5 bağlantısı",
                            "Bilgisayar PS5'in görüntüsünü chiaki-ng ile alır ve sadece yazıları okumak için kullanır. "
                            "Sen oyunu her zamanki gibi oynarsın.")
        self.r_psn = check_row("1. İkinci PSN hesabı aç (ücretsiz)",
                               "chiaki-ng'ye kendi hesabınla bağlanırsan kolun kopar. Yeni bir hesap aç, PS5'te bu "
                               "hesapla bir kez giriş yap.",
                               button("Hesap aç", None, lambda: webbrowser.open("https://www.playstation.com")))
        self.r_rp = check_row("2. PS5'te Uzaktan Oynatma",
                              "İkinci hesaptayken Ayarlar › Sistem › Uzaktan Oynatma: aç ve Cihazı Bağla'ya bas "
                              "(8 haneli kod çıkar). Güç Tasarrufu'nda İnternete Bağlı Kal'ı da aç.")
        self.chiaki_btn_open = button("Aç", None, self._open_chiaki)
        self.r_chiaki = check_row("3. chiaki-ng", "", button("İndir", None, lambda: webbrowser.open(CHIAKI_DOWNLOAD)),
                                  button("Gözat", None, self._browse_chiaki), self.chiaki_btn_open)
        self.r_conn = check_row("4. chiaki-ng'de PS5'i ikinci hesapla kaydet ve bağlan",
                                "PS5'i kaydederken ikinci hesapla giriş yap ve 8 haneli kodu gir. Bağlanınca bu satır "
                                "yeşil olur.")
        for r in (self.r_psn, self.r_rp, self.r_chiaki, self.r_conn):
            lay.addWidget(r)
        self._refresh_chiaki()
        lay.addStretch(1)
        return w

    def _tv(self) -> QWidget:
        w, lay = self._page("Televizyon",
                            "Türkçe altyazıyı TV'de oyunun üstünde göstermek için TV'ye küçük bir uygulama kurulur. "
                            "Bunu bilgisayar ağ üzerinden kendisi yapar.")
        self.use_tv = QCheckBox("TV'de de Türkçe altyazı görmek istiyorum")
        self.use_tv.setChecked(True)
        lay.addWidget(self.use_tv)
        steps = Card(inner=True, margins=14)
        steps.add(label("TCL / Google TV'de bir kez:", "h3"))
        steps.add(label("① Ayarlar › Sistem › Hakkında › <b>Android TV OS derlemesi</b>'ne 7 kez bas.<br>"
                        "② Ayarlar › Sistem › Geliştirici seçenekleri › <b>USB hata ayıklama</b>'yı aç "
                        "(yoksa <b>Kablosuz hata ayıklama</b>).<br>"
                        "③ Aşağıdan TV'yi bul ve <b>Bağlan</b>'a bas. TV'de çıkan soruya <b>İzin ver</b> de.",
                        "muted", wrap=True))
        lay.addWidget(steps)
        self.tv_ip = QLineEdit(self.cfg.tv.ip)
        self.tv_ip.setPlaceholderText("TV'nin IP adresi")
        self.tv_scan_btn = button("Ağda ara", None, self._scan)
        self.tv_found = QComboBox()
        self.tv_found.hide()
        self.tv_found.currentIndexChanged.connect(lambda i: self.tv_ip.setText(self.tv_found.itemData(i) or
                                                                               self.tv_ip.text()))
        self.tv_conn_btn = button("Bağlan ve kur", "primary", self._tv_connect)
        lay.addLayout(hbox(self.tv_ip, self.tv_scan_btn, self.tv_found, self.tv_conn_btn, spacing=10))
        self.pair_addr = QLineEdit()
        self.pair_addr.setPlaceholderText("Eşleştirme adresi (ör. 192.168.1.40:37123)")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("Kod")
        self.pair_code.setFixedWidth(100)
        lay.addLayout(hbox(self.pair_addr, self.pair_code,
                           button("Eşleştir", None, lambda: self.ctl.tv_pair(self.pair_addr.text().strip(),
                                                                             self.pair_code.text().strip())),
                           spacing=10))
        self.tv_dot = Dot("off")
        self.tv_msg = label("", "muted", wrap=True)
        lay.addLayout(hbox(self.tv_dot, self.tv_msg, 1, spacing=6))
        lay.addStretch(1)
        return w

    def _translation(self) -> QWidget:
        w, lay = self._page("Çeviri",
                            "Yerel model internetsiz ve anında çevirir. En doğal Türkçe için Claude'u bağla: "
                            "argoyu, esprileri ve karakterlerin konuşma tarzını korur.")
        c = self.cfg.ceviri
        card = Card(inner=True, margins=16)
        self.key = QLineEdit(c.claude_anahtar)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("Claude API anahtarı (sk-ant-...)")
        card.add(label("Claude API anahtarı", "h3"))
        card.add(hbox(self.key, button("Anahtar al", None,
                                       lambda: webbrowser.open("https://console.anthropic.com/settings/keys"))))
        self.model = QComboBox()
        self.model.addItem("Claude Opus 5.5 · en iyi kalite (hızlı mod açık)", "claude-opus-5-5")
        self.model.addItem("Claude Haiku 5.5 · daha hızlı ve ucuz", "claude-haiku-5-5")
        self.model.setCurrentIndex(max(0, self.model.findData(c.claude_model)))
        card.add(self.model)
        card.add(label("Anahtar sadece bu bilgisayarda saklanır. Anahtar girmezsen yalnızca yerel model kullanılır.",
                       "faint", wrap=True))
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
                         "Kasada ikinci bir Discord hesabıyla sesli kanala gir, sesini kapat ve TÜM EKRANI paylaş. "
                         "Sen Mac'ten kendi hesabınla konuş (kulaklıkla)."))
        tips.add(feature("regions", "GTA 6 çıkınca",
                         "Okuma alanları sayfasında Görüntü al'a bas, kutuları gerçek altyazının üstüne çek."))
        lay.addWidget(tips)
        self.auto_cb = QCheckBox("TV günleri için her şey kendiliğinden olsun: bilgisayar açılınca uygulama açılsın, "
                                 "PS5'i açınca chiaki bağlansın ve çeviri başlasın")
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
    def _go(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        self.stepper.setCurrent(i)
        self.back.setVisible(i > 0)
        self.skip.setVisible(i in (1, 2, 3))
        self.next.setText({0: "Başlayalım", 4: "Bitir"}.get(i, "Devam"))

    def _back(self) -> None:
        self._go(max(0, self.stack.currentIndex() - 1))

    def _next(self) -> None:
        i = self.stack.currentIndex()
        if i == 2:
            self.cfg.tv.ip = self.tv_ip.text().strip() if self.use_tv.isChecked() else ""
        if i == 3:
            self._save_translation()
        if i == 4:
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
        self._go(i + 1)

    # ------------------------------------------------------------------ PS5
    def _refresh_chiaki(self) -> None:
        from ..app import find_chiaki
        path = find_chiaki(self.cfg.kaynak.chiaki_yolu)
        text = (f"Bulundu: {path}" if path else
                "Bulunamadı. İndir'e basıp kur (Windows sürümü), sonra gerekirse Gözat ile chiaki.exe'yi seç.")
        self.r_chiaki.lay.itemAt(1).widget().setText(text)
        self.r_chiaki.dot.setState("ok" if path else "off")
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
        if not hasattr(self, "r_conn"):
            return
        self.r_conn.dot.setState("ok" if ok else "off")
        if ok:
            for r in (self.r_psn, self.r_rp):
                r.dot.setState("ok")
            self.r_conn.lay.itemAt(1).widget().setText(f"chiaki penceresi bulundu: {title}")

    # ------------------------------------------------------------------ TV
    def _scan(self) -> None:
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
        self.ctl.apply_config(self.cfg)
        self.cfg = self.ctl.edit_config()
        self.ctl.tv_connect(ip, force_install=True)

    def _on_tv(self, state: str, msg: str) -> None:
        if hasattr(self, "tv_dot"):
            self.tv_dot.setState({"bagli": "ok", "baglaniyor": "warn", "onay": "info", "hata": "bad"}.get(state, "off"))
            self.tv_msg.setText(msg)

    # ------------------------------------------------------------------ çeviri
    def _save_translation(self) -> None:
        c = self.cfg.ceviri
        c.claude_anahtar = self.key.text().strip()
        c.claude_model = self.model.currentData()
        c.claude_hizli_mod = c.claude_model == "claude-opus-5-5"
        c.kalite = "claude" if c.claude_anahtar or c.kalite != "claude" else "yok"

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
