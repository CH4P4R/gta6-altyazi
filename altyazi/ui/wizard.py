"""İlk açılış kurulum sihirbazı."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from ..app import CHIAKI_DOWNLOAD, AppController
from . import theme as T
from .widgets import Card, Dot, Icon, Logo, PreviewArt, QrCode, Stepper, button, hbox, label, vbox

STEPS = ["Hoş geldin", "Nerede oynayacaksın?", "PS5 ve chiaki-ng", "Televizyon", "Çeviri", "Hazır"]
P_WELCOME, P_WHERE, P_PS5, P_TV, P_TRANSLATION, P_DONE = range(6)
REHBER = Path(__file__).resolve().parent / "rehber"
PSN_SIGNUP = "https://www.playstation.com/tr-tr/playstation-network/"


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


class GuideImage(QWidget):
    """Rehber görseli: oranı korunarak, köşeleri yuvarlatılmış çizilir."""

    def __init__(self):
        super().__init__()
        self.pix: QPixmap | None = None
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, name: str | None) -> None:
        path = REHBER / f"{name}.png" if name else None
        self.pix = QPixmap(str(path)) if path and path.exists() else None
        self.setVisible(self.pix is not None)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        if not self.pix or self.pix.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        ratio = self.pix.width() / self.pix.height()
        w = min(self.width(), self.height() * ratio)
        h = w / ratio
        r = QRectF((self.width() - w) / 2, 0, w, h)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.setClipPath(path)
        p.drawPixmap(r, self.pix, QRectF(self.pix.rect()))


class Guide(QWidget):
    """Resimli, adım adım anlatım. Her adım: görsel + başlık + açıklama + (isteğe bağlı) düğmeler/durum."""

    def __init__(self):
        super().__init__()
        self.steps: list[dict] = []
        self.index = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.image = GuideImage()
        lay.addWidget(self.image, 1)
        self.counter = label("", "tag")
        self.title = label("", "h2")
        lay.addLayout(hbox(self.title, None, self.counter, spacing=10))
        self.text = label("", "muted", wrap=True)
        self.text.setTextFormat(Qt.RichText)
        self.text.setOpenExternalLinks(True)
        lay.addWidget(self.text)
        self.extra = QStackedWidget()
        self.extra.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lay.addWidget(self.extra)
        self.dots = QHBoxLayout()
        self.dots.setSpacing(6)
        lay.addLayout(self.dots)
        self._empty = QWidget()
        self.extra.addWidget(self._empty)

    def set_steps(self, steps: list[dict]) -> None:
        self.steps = steps
        for st in steps:
            w = st.get("extra")
            if w is not None and self.extra.indexOf(w) < 0:
                self.extra.addWidget(w)
        while self.dots.count():
            item = self.dots.takeAt(0)
            if item.widget():
                item.widget().setParent(None)      # eski çizgiler ekranda asılı kalmasın
                item.widget().deleteLater()
        self._dots = []
        for _ in steps:
            d = QFrame()
            d.setFixedSize(26, 6)
            self._dots.append(d)
            self.dots.addWidget(d)
        self.dots.addStretch(1)
        self.show_step(min(self.index, len(steps) - 1))

    def show_step(self, i: int) -> None:
        self.index = i
        st = self.steps[i]
        self.image.set_image(st.get("img"))
        self.title.setText(st["title"])
        self.counter.setText(f"ADIM {i + 1} / {len(self.steps)}")
        self.text.setText(st["text"])
        self.extra.setCurrentWidget(st.get("extra") or self._empty)
        self.extra.setVisible(st.get("extra") is not None)
        for k, d in enumerate(self._dots):
            color = T.A1 if k <= i else T.BORDER_HI
            d.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def can_next(self) -> bool:
        return self.index < len(self.steps) - 1

    def can_back(self) -> bool:
        return self.index > 0

    def next(self) -> None:
        self.show_step(self.index + 1)

    def back(self) -> None:
        self.show_step(self.index - 1)


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
        self.ps5_guide.set_steps(self._ps5_steps())
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
        self.ps5_guide.set_steps(self._ps5_steps())
        self._refresh_chiaki()
        return w

    def _ps5_steps(self) -> list[dict]:
        where = self.where
        account = {"monitor": "<b>Kendi PlayStation hesabınla</b> giriş yap (oyunların ve kayıtların o hesapta).",
                   "tv": "<b>İkinci PSN hesabınla</b> giriş yap. Kendi hesabınla girersen TV'de oynarken kolun kopar.",
                   "ikisi": "Bugün nerede oynayacaksan o hesapla gir: <b>monitörde kendi hesabın</b>, <b>TV'de ikinci "
                            "hesap</b>. Diğerini sonra aynı adımlarla eklersin."}[where]
        steps: list[dict] = []
        if where in ("tv", "ikisi"):
            steps.append({"title": "İkinci PSN hesabı aç (ücretsiz)",
                          "text": "TV'de oynarken bilgisayar PS5'i ikinci bir hesapla izler; kendi hesabınla "
                                  "bağlanırsa TV'deki kolun kopar.<br>① Aşağıdaki düğmeyle ücretsiz yeni bir PSN "
                                  "hesabı aç.<br>② PS5'i aç ve bu yeni hesapla <b>bir kez</b> oturum aç."
                                  + ("<br><span>Sadece monitörde oynayacaksan bu adımı geçebilirsin.</span>"
                                     if where == "ikisi" else ""),
                          "extra": self.act_psn})
        steps += [
            {"img": "chiaki-indir", "title": "chiaki-ng'yi indir ve kur",
             "text": "① <b>İndirme sayfasını aç</b>'a bas.<br>② En üstteki sürümün <b>Assets</b> listesinde adında "
                     "<b>windows</b> geçen dosyayı indir.<br>③ İndirdiğin dosyayı çalıştırıp kur. Kurulunca aşağıdaki "
                     "satır yeşil olur (olmazsa <b>chiaki.exe'yi seç</b> ile yerini göster).",
             "extra": self.act_chiaki},
            {"img": "chiaki-kopyala", "title": "chiaki-ng'de PSN girişi",
             "text": "① chiaki-ng'yi aç. PS5 eklemek için hesabını ister: <b>PSN Login</b> ekranı açılır "
                     "(açılmazsa sağ üstteki ☰ menüsünden ya da PS5 eklerken çıkar).<br>② <b>Click to Re-Copy URL</b>'ye "
                     "bas. Sony'nin giriş adresi kopyalanır."},
            {"img": "tarayici-giris", "title": "Tarayıcıda giriş yap",
             "text": "① Chrome ya da Edge'i aç, adres çubuğuna tıkla, <b>Ctrl+V</b> yap ve <b>Enter</b>'a bas.<br>"
                     f"② Açılan PlayStation sayfasında {account}"},
            {"img": "tarayici-adres", "title": "Açılan sayfanın adresini kopyala",
             "text": "Giriş bitince boş ya da hatalı görünen bir sayfa açılır. <b>Bu normal.</b><br>① Adres çubuğuna "
                     "tıkla (adres <i>remoteplay.dl.playstation.net/…redirect?code=</i> ile başlar).<br>② <b>Ctrl+A</b>, "
                     "sonra <b>Ctrl+C</b> yap. Bu kod birkaç dakika geçerli, hızlı ol."},
            {"img": "chiaki-yapistir", "title": "chiaki-ng'ye yapıştır",
             "text": "① chiaki-ng'ye dön, <b>Click to Paste URL</b>'ye bas.<br>② Hesap bilgisi alınır; sol üstteki "
                     "<b>‹</b> ile ana ekrana dön.<br>Hata verirse kodun süresi dolmuştur: 2. adımdan tekrarla."},
            {"img": "ps5-kod", "title": "PS5'te bağlantı kodunu al",
             "text": "PS5'te chiaki'ye girdiğin hesapla oturum açıkken:<br>① <b>Ayarlar › Sistem › Uzaktan Oynatma</b>: "
                     "<b>Uzaktan Oynatmayı Etkinleştir</b> açık olsun.<br>② <b>Cihazı Bağla</b>'ya bas; 8 haneli bir kod "
                     "çıkar (ekranda bırak).<br>③ Ayrıca <b>Ayarlar › Sistem › Güç Tasarrufu › Dinlenme Modunda "
                     "Kullanılabilir Özellikler</b>: <b>İnternete Bağlı Kal</b> ve <b>Ağ Üzerinden PS5'i Açmayı "
                     "Etkinleştir</b>'i aç.<br>④ TV'de oynayacaksan: Uzaktan Oynatma ayarlarındaki <b>bağlantı durumu "
                     "açılır penceresini gizle</b> seçeneğini aç; yoksa chiaki bağlanınca TV ekranında \"bağlandı\" "
                     "yazısı çıkar."},
            {"img": "chiaki-kayit", "title": "PS5'i chiaki-ng'ye kaydet",
             "text": "① chiaki-ng ana ekranında PS5'in kutusuna tıkla (görünmüyorsa PS5 ve bilgisayar aynı modeme "
                     "bağlı mı bak; sağ üstteki <b>+</b> ile IP'siyle de eklenir).<br>② <b>PIN</b> kutusuna PS5'teki "
                     "8 haneli kodu yaz.<br>③ <b>Register</b>'a bas."},
            {"img": "chiaki-ayar", "title": "Görüntü ayarları (bir kere)",
             "text": "chiaki-ng ayarlarında (dişli simgesi) <b>Video</b> bölümü:<br>① <b>Resolution: 1080p</b><br>"
                     "② <b>FPS: 60</b><br>③ <b>Bitrate</b> en yüksek.<br>Yazıların net okunması için bu önemli."},
        ]
        if where in ("monitor", "ikisi"):
            steps.append({"img": "kol-usb", "title": "Kolu bilgisayara bağla",
                          "text": "Monitörde oynarken kol bilgisayara bağlı olur.<br>① DualSense'i <b>USB kablosuyla</b> "
                                  "bilgisayara tak (en kolayı; titreşim de çalışır). Bluetooth da olur.<br>"
                                  + ("TV günlerinde kolu yine PS5'e bağlarsın." if where == "ikisi" else "")})
        last = {"monitor": "① chiaki-ng'de PS5'in kutusuna tıkla; PS5'in ekranı açılır, kolla oynarsın.<br>② İstersen "
                           "<b>F11</b> ile tam ekran yap.<br>③ Bağlanınca aşağıdaki satır yeşil olur.",
                "tv": "① chiaki-ng'de PS5'in kutusuna tıkla. Sen TV'den oynamaya devam et; chiaki açık kalsın.<br>"
                      "② chiaki penceresini <b>simge durumuna küçültme</b>, program görüntüyü oradan okuyor.<br>"
                      "③ Bağlanınca aşağıdaki satır yeşil olur.",
                "ikisi": "① chiaki-ng'de PS5'in kutusuna tıkla.<br>② Monitörde oynuyorsan <b>F11</b> ile tam ekran yap; "
                         "TV'de oynuyorsan chiaki açık kalsın, küçültme.<br>③ Bağlanınca aşağıdaki satır yeşil olur."}[where]
        steps.append({"img": "chiaki-baglan", "title": "Bağlan", "text": last, "extra": self.act_conn})
        return steps

    def _tv(self) -> QWidget:
        w, lay = self._page("Televizyon",
                            "Türkçe altyazıyı TV'de oyunun üstünde göstermek için TV'ye küçük bir uygulama kurulur. "
                            "Bunu bilgisayar ağ üzerinden kendisi yapar. Aşağıdaki adımlar Google TV / Android TV "
                            "(TCL, Sony, Philips...) için; LG ve Samsung için Televizyon sayfasına bak.")
        self.tv_ip = QLineEdit(self.cfg.tv.ip)
        self.tv_ip.setPlaceholderText("TV'nin IP adresi")
        self.tv_scan_btn = button("Ağda ara", None, self._scan)
        self.tv_found = QComboBox()
        self.tv_found.hide()
        self.tv_found.currentIndexChanged.connect(lambda i: self.tv_ip.setText(self.tv_found.itemData(i) or
                                                                               self.tv_ip.text()))
        self.tv_conn_btn = button("Bağlan ve kur", "primary", self._tv_connect)
        self.pair_addr = QLineEdit()
        self.pair_addr.setPlaceholderText("Eşleştirme adresi (ör. 192.168.1.40:37123)")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("Kod")
        self.pair_code.setFixedWidth(100)
        self.tv_dot = Dot("off")
        self.tv_msg = label("", "muted", wrap=True)
        conn = QWidget()
        conn.setLayout(vbox(hbox(self.tv_ip, self.tv_scan_btn, self.tv_found, self.tv_conn_btn, spacing=10),
                            hbox(self.pair_addr, self.pair_code,
                                 button("Eşleştir", None, lambda: self.ctl.tv_pair(self.pair_addr.text().strip(),
                                                                                   self.pair_code.text().strip())),
                                 spacing=10),
                            hbox(self.tv_dot, self.tv_msg, 1, spacing=6), spacing=8))
        self.tv_guide = Guide()
        self.tv_guide.set_steps([
            {"img": "tv-gelistirici", "title": "TV'de geliştirici seçeneklerini aç",
             "text": "TV kumandasıyla:<br>① <b>Ayarlar › Sistem › Hakkında</b>'ya gir.<br>② <b>Android TV OS "
                     "derlemesi</b> satırına arka arkaya <b>7 kez</b> bas. \"Artık geliştiricisiniz\" yazar."},
            {"img": "tv-hata-ayiklama", "title": "USB hata ayıklamayı aç",
             "text": "① <b>Ayarlar › Sistem › Geliştirici seçenekleri</b>'ne gir.<br>② <b>USB hata ayıklama</b>'yı aç. "
                     "Yoksa ya da TV bulunamazsa <b>Kablosuz hata ayıklama</b>'yı aç; ekrandaki eşleştirme adresi ve "
                     "kodunu bir sonraki adımda yazarsın."},
            {"img": "tv-izin", "title": "Bağlan ve izin ver",
             "text": "① <b>Ağda ara</b>'ya bas (ya da TV'nin IP'sini yaz), sonra <b>Bağlan ve kur</b>'a bas.<br>"
                     "② TV'de çıkan soruda <b>Bu bilgisayardan her zaman izin ver</b>'i işaretle, <b>İzin ver</b>'e bas."
                     "<br>TV uygulaması kurulup açılınca aşağıdaki satır yeşil olur.",
             "extra": conn},
        ])
        lay.addWidget(self.tv_guide, 1)
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
