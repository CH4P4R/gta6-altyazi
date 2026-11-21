"""PS5'i bağla (chiaki-ng penceresi olmadan): ikinci PSN hesabıyla giriş ve PS5 eşleme.

Oyun TV'de, HDMI'dan oynanır; bilgisayar PS5'e ikinci hesapla Remote Play üzerinden bağlanıp yalnız altyazıyı okur.
Adımlar CouchSubs'ın kurulumuyla aynı: ikinci hesap → Sony girişi → PS5'te "Cihazı Eşleştir" kodu.
"""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit, QVBoxLayout, QWidget

from . import theme as T
from .widgets import Card, button, hbox, label, scroll_page, vbox

ACCOUNT_STEPS = (
    "<b>Neden ikinci hesap?</b> Bilgisayar oyunu Remote Play'den izler. Kendi hesabınla bağlansaydı PS5 kolunu "
    "kapatırdı; ikinci hesapla sen oynamaya devam edersin. PS Plus gerekmez.<br><br>"
    "1. playstation.com'da <b>farklı bir e-postayla</b> ücretsiz yeni hesap aç.<br>"
    "2. PS5'te <b>Kullanıcı Ekle</b> de, yeni hesapla bir kez oturum aç.<br>"
    "3. Hâlâ yeni kullanıcıyken: <b>Ayarlar › Sistem › Uzaktan Oynatma › Uzaktan Oynatmayı Etkinleştir</b>'i aç.<br>"
    "4. Ekranda \"Uzaktan Oynatma bağlandı\" yazısı çıkmasın: aynı yerde <b>Uzaktan Oynatma Bağlantı Durumu "
    "Açılır Penceresini Gizle</b>'yi aç (iki hesapta da).")

LOGIN_HELP = (
    "<b>Sony giriş sayfasını aç</b>'a bas, <b>ikinci hesapla</b> giriş yap. Giriş bitince tarayıcı yalnız "
    "<i>redirect</i> yazan bir remoteplay.dl.playstation.net sayfasında kalır (bu normal). Adres çubuğuna tıkla, "
    "adresin <b>tamamını</b> kopyala. Program kopyalanan adresi kendisi alır; almazsa aşağıya yapıştır. "
    "Şifren doğrudan Sony'ye gider; program yalnız hesap kimliğini saklar.")

PAIR_HELP = (
    "1. PS5'te <b>ikinci kullanıcıya geç</b>.<br>"
    "2. <b>Ayarlar › Sistem › Uzaktan Oynatma › Cihazı Eşleştir</b>'i aç; ekranda 8 haneli kod çıkar.<br>"
    "3. Aşağıda PS5'ini seç, kodu kutulara yaz, <b>Bağlan</b>'a bas (30 saniyeye kadar sürebilir).<br>"
    "4. Bitince PS5'te <b>kendi kullanıcına geri dön</b>. Bunu yalnız bir kez yaparsın.")

PLAY_TIP = ("Oynarken kolu açınca PS5'te <b>kendi (ana) hesabını</b> seç. İkinci hesapla oynama; yoksa kol kendiliğinden "
            "kapanır ya da oyunda çalışmaz.")


class Ps5Panel(QWidget):
    """PS5 bağlantı adımları (ikinci hesap girişi, eşleme, oynarken). Hem pencerede hem sihirbazın içinde kullanılır."""

    def __init__(self, ctl, parent: QWidget | None = None, intro: bool = True):  # noqa: ANN001
        super().__init__(parent)
        self.ctl = ctl
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        if intro:
            lay.addLayout(vbox(label("PS5'i bağla", "h1"),
                               label("Oyunu TV'de oynarsın; bilgisayar PS5'e arka planda ikinci hesapla bağlanıp yalnız "
                                     "altyazıyı okur, Türkçesini TV'ye gönderir. chiaki-ng penceresi gerekmez.",
                                     "muted", wrap=True), spacing=4))

        # 1. ikinci hesap
        c1 = Card(margins=20, spacing=10)
        self.acc_state = label("", "muted", wrap=True)
        c1.add(step_head("1", "İkinci PSN hesabı"))
        c1.add(rich(ACCOUNT_STEPS))
        c1.add(label("Giriş", "h3"))
        c1.add(rich(LOGIN_HELP))
        self.paste = QLineEdit()
        self.paste.setPlaceholderText("https://remoteplay.dl.playstation.net/remoteplay/redirect?code=...")
        self.open_btn = button("Sony giriş sayfasını aç", "primary", self._open_login)
        self.save_btn = button("Kaydet", None, self._save_account)
        c1.add(hbox(self.open_btn, None, spacing=8))
        c1.add(hbox(self.paste, self.save_btn, spacing=8))
        c1.add(label("Sony'nin sayfası açılmazsa (bazı internet sağlayıcıları engelliyor) ikinci hesabın PSN hesap "
                     "kimliğini (base64, 12 karakter, ör. AbCdEfGhIjk=) aynı kutuya yazıp Kaydet'e bas.", "faint",
                     wrap=True))
        c1.add(self.acc_state)
        # Nino: giriş yapıldıysa hesap kimliğinin bir kısmı ve Çıkış yap
        from .parcalar import IconTile
        self.acc_box = Card(inner=True, margins=14, spacing=4)
        self.acc_id = label("", "faint")
        self.acc_id.setObjectName("mono")
        self.logout_btn = button("Çıkış yap", "danger", self._logout)
        self.acc_box.add(hbox(IconTile("check", 40, glow=False), vbox(label("Giriş yapıldı", "h3"), self.acc_id,
                                                                          spacing=2), None, self.logout_btn, spacing=12))
        self.acc_box.hide()
        c1.add(self.acc_box)
        lay.addWidget(c1)

        # 2. eşleme
        c2 = Card(margins=20, spacing=10)
        c2.add(step_head("2", "PS5'i eşle"))
        c2.add(rich(PAIR_HELP))
        self.consoles = QComboBox()
        self.consoles.setEditable(True)
        self.consoles.lineEdit().setPlaceholderText("PS5 aranıyor... (bulunmazsa IP adresini yaz)")
        self.search_btn = button("Yeniden ara", None, self._search)
        c2.add(hbox(self.consoles, self.search_btn, spacing=8))
        from .parcalar import PinInput
        self.pin = PinInput(8)                    # Nino gibi 8 ayrı kutu; yapıştırınca kutulara dağılır
        self.pair_btn = button("Bağlan", "primary", self._pair)
        self.pin.changed.connect(lambda t: self.pair_btn.setEnabled(len(t) == 8))
        self.pair_btn.setEnabled(False)
        c2.add(hbox(self.pin, 12, self.pair_btn, None, spacing=0))
        self.pair_state = label("", "muted", wrap=True)
        c2.add(self.pair_state)
        lay.addWidget(c2)

        c3 = Card(margins=20, spacing=8)
        c3.add(step_head("3", "Oynarken"))
        c3.add(rich(PLAY_TIP))
        self.pass_edit = QLineEdit(ctl.cfg.ps5.giris_sifresi)
        self.pass_edit.setPlaceholderText("PS5 giriş şifresi (yalnız ikinci hesapta açıksa, 4 hane)")
        self.pass_edit.setMaxLength(4)
        self.pass_edit.editingFinished.connect(self.save_passcode)
        c3.add(self.pass_edit)
        lay.addWidget(c3)

        ctl.ps5Paired.connect(self._on_result)
        ctl.ps5Consoles.connect(self._on_consoles)
        self._mode = ""
        self._seen_clip = ""
        self._searched = False
        QApplication.clipboard().dataChanged.connect(self._clipboard)
        self.refresh()

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        super().showEvent(e)
        if not self._searched:            # PS5 araması panel ilk görününce (sihirbazda sayfaya gelince)
            self._searched = True
            self._search()

    # ------------------------------------------------------------------ durum
    def refresh(self) -> None:
        p = self.ctl.cfg.ps5
        if p.hesap:
            self.acc_state.setText("✓ İkinci hesapla giriş yapıldı.")
            self.acc_state.setStyleSheet(f"color: {T.OK};")
            masked = p.hesap[:4] + "••••" + p.hesap[-4:] if len(p.hesap) > 8 else "••••"
            self.acc_id.setText(f"PSN hesap kimliği: {masked}")
            self.acc_box.show()
        else:
            self.acc_box.hide()
        if self.ctl.ps5_paired():
            self.pair_state.setText(f"✓ Eşli: {p.ad or 'PS5'} ({p.ip}). Başka bir PS5 için yeniden eşleyebilirsin.")
            self.pair_state.setStyleSheet(f"color: {T.OK};")

    def _logout(self) -> None:
        """İkinci hesaptan çık: hesap kimliği silinir (PS5 eşlemesi kalır; yeniden giriş yapınca kullanılır)."""
        cfg = self.ctl.edit_config()
        cfg.ps5.hesap = ""
        self.ctl.apply_config(cfg)
        self.acc_state.setText("Çıkış yapıldı. Yeniden giriş için Sony giriş sayfasını aç.")
        self.acc_state.setStyleSheet("")
        self.refresh()

    def _open_login(self) -> None:
        self._seen_clip = QApplication.clipboard().text() or ""
        webbrowser.open(self.ctl.psn_login_url())
        self.acc_state.setText("Tarayıcıda ikinci hesapla giriş yap, sonra adres çubuğundaki adresi kopyala.")
        self.acc_state.setStyleSheet("")

    def _clipboard(self) -> None:
        from ..remoteplay import redirect_from_text
        text = QApplication.clipboard().text() or ""
        if text == self._seen_clip or not redirect_from_text(text):
            return
        self._seen_clip = text
        self.paste.setText(text.strip())
        self._save_account()

    def _save_account(self) -> None:
        text = self.paste.text().strip()
        if not text:
            self.acc_state.setText("Önce adresi yapıştır.")
            return
        self._mode = "hesap"
        self.save_btn.setEnabled(False)
        self.acc_state.setText("Sony'ye soruluyor...")
        self.acc_state.setStyleSheet("")
        self.ctl.psn_finish(text)

    def _search(self) -> None:
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Aranıyor...")
        self.ctl.ps5_search()

    def _on_consoles(self, found: list) -> None:
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Yeniden ara")
        current = self.consoles.currentText()
        self.consoles.clear()
        for c in found:
            self.consoles.addItem(f"{c.name} · {c.host} · {'açık' if c.awake else 'dinlenmede'}", c.host)
        if found:
            self.pair_state.setText(f"<span style='color:{T.OK}'>✓</span> <b>{found[0].name}</b> bulundu"
                                    + (f" (+{len(found) - 1} PS5 daha)" if len(found) > 1 else ""))
        if not found:
            self.consoles.setEditText(current or self.ctl.cfg.ps5.ip)
            self.pair_state.setText("PS5 bulunamadı. PS5 açık ve bilgisayarla aynı ağda mı? IP adresini de yazabilirsin "
                                    "(PS5'te Ayarlar › Ağ › Bağlantı Durumu › Bağlantı Durumunu Görüntüle).")

    def _host(self) -> str:
        i = self.consoles.currentIndex()
        if i >= 0 and self.consoles.itemData(i) and self.consoles.currentText() == self.consoles.itemText(i):
            return str(self.consoles.itemData(i))
        return self.consoles.currentText().split("·")[-1].strip() if "·" in self.consoles.currentText() \
            else self.consoles.currentText().strip()

    def _pair(self) -> None:
        self._mode = "esle"
        self.pair_btn.setEnabled(False)
        self.pair_state.setText("PS5'e bağlanılıyor... 30 saniyeye kadar sürebilir.")
        self.pair_state.setStyleSheet("")
        self.ctl.ps5_pair(self._host(), self.pin.text())

    def _on_result(self, ok: bool, msg: str) -> None:
        target = self.acc_state if self._mode == "hesap" else self.pair_state
        self.save_btn.setEnabled(True)
        self.pair_btn.setEnabled(True)
        target.setText(("✓ " if ok else "") + msg)
        target.setStyleSheet(f"color: {T.OK if ok else T.BAD};")

    def save_passcode(self) -> None:
        pw = self.pass_edit.text().strip()
        if pw != self.ctl.cfg.ps5.giris_sifresi:
            cfg = self.ctl.edit_config()
            cfg.ps5.giris_sifresi = pw
            self.ctl.apply_config(cfg)


class Ps5Dialog(QDialog):
    def __init__(self, ctl, parent: QWidget | None = None):  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle("PS5'i bağla")
        self.resize(720, 800)
        self.setStyleSheet(f"QDialog {{ background: {T.BG}; }}")
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 24, 28, 24)
        self.panel = Ps5Panel(ctl, body)
        lay.addWidget(self.panel)
        lay.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_page(body), 1)
        self.close_btn = button("Bitti", "primary", self.accept)
        outer.addLayout(hbox(None, self.close_btn, margins=(28, 10, 28, 18)))

    def accept(self) -> None:
        self.panel.save_passcode()
        super().accept()


def step_head(num: str, title: str):  # noqa: ANN201
    badge = label(num)
    badge.setFixedSize(30, 30)
    badge.setAlignment(Qt.AlignCenter)
    badge.setStyleSheet("color: white; font-weight: 700; border-radius: 15px; "
                        f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {T.A1}, stop:1 {T.A2});")
    w = QWidget()
    w.setLayout(hbox(badge, label(title, "h2"), None, spacing=10))
    return w


def rich(html: str):  # noqa: ANN201
    w = label("", "muted", wrap=True)
    w.setTextFormat(Qt.RichText)
    w.setText(html)
    return w
