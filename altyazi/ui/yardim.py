"""Yardım sohbeti penceresi ("Sor"): rehberi ve programın durumunu bilen yapay zekâya soru sorulur (yardimci.py)."""

from __future__ import annotations

import html
import re
import threading

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QLayout, QLineEdit, QTextBrowser, QVBoxLayout, QWidget

from . import theme as T
from .widgets import button, hbox, label, vbox


GREETING = ("Merhaba! Ben yardımcın 👋 Kurulumla ilgili her şeyi sorabilirsin. Önce şunu söyler misin: elinde hangi "
            "cihazlar var?")
SUGGESTIONS = ["PS5 + TV", "PS5 + bilgisayar monitörü", "TV uygulamasını nasıl kurarım?", "Altyazı çıkmıyor",
               "Telefon mesajları çevrilmiyor"]


class _Relay(QObject):
    answered = Signal(str)


class FlowLayout(QLayout):
    """Öneri düğmelerini satıra sığdığı kadar dizer, sığmayanı alt satıra geçirir."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8):
        super().__init__(parent)
        self._items: list = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: ANN001, N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):  # noqa: ANN201, N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):  # noqa: ANN201, N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):  # noqa: ANN201, N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return self._place(QRect(0, 0, w, 0), move=False)

    def setGeometry(self, r: QRect) -> None:  # noqa: N802
        super().setGeometry(r)
        self._place(r, move=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _place(self, r: QRect, move: bool) -> int:
        x, y, line = r.x(), r.y(), 0
        for it in self._items:
            hint = it.sizeHint()
            if x + hint.width() > r.right() + 1 and line > 0:
                x, y, line = r.x(), y + line + self._gap, 0
            if move:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line = max(line, hint.height())
        return y + line - r.y()


def md_html(text: str) -> str:
    """Cevaptaki **kalın**, numaralı satırlar ve bağlantılar."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(https?://[^\s<]+)", r"<a style='color:#ff9f43' href='\1'>\1</a>", t)
    return t.replace("\n", "<br>")


class AskDialog(QDialog):
    def __init__(self, ctl, parent=None):  # noqa: ANN001
        super().__init__(parent)
        from ..yardimci import Assistant
        self.ctl = ctl
        self.bot = Assistant(ctl)
        self.setWindowTitle("Sor · yardım")
        self.resize(640, 720)
        self.setStyleSheet(f"QDialog {{ background: {T.BG}; }} QTextBrowser {{ background: {T.SURFACE}; color: {T.TEXT}; border: 1px "
                           f"solid {T.BORDER}; border-radius: 14px; padding: 12px; font-size: 12pt; }} "
                           f"QPushButton#chip {{ font-size: 10.5pt; padding: 7px 14px; border-radius: 15px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        engine = self.bot.available()
        from PySide6.QtWidgets import QLabel
        from .widgets import marka_pixmap
        face = QLabel()
        face.setFixedSize(72, 72)
        face.setPixmap(marka_pixmap("bot.png", 72))
        lay.addLayout(hbox(face, 6, vbox(label("Sor", "h1"),
                                         label("Takıldığın yeri yaz: TV'nin markası, ekranda ne yazdığı... Adım adım "
                                               "anlatırım. İstersen ekranın fotoğrafını da ekle." +
                                               (f" (Cevaplar senin {engine.capitalize()} anahtarınla.)" if engine
                                                else ""), "muted", wrap=True), spacing=4), spacing=10))
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)
        # Sohbet boşken hazır sorular (Nino): basınca o soru gönderilir, ilk sorudan sonra kaybolur
        self.chips = QWidget()
        flow = FlowLayout(self.chips)
        self.chip_buttons = []
        for text in SUGGESTIONS:
            b = button(text, "chip", lambda _=False, t=text: self._ask_chip(t))
            flow.addWidget(b)
            self.chip_buttons.append(b)
        lay.addWidget(self.chips)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Örn: Samsung TV'de 12345 yazamıyorum, kumandada rakam yok")
        self.input.returnPressed.connect(self._send)
        self.photo_btn = button("Fotoğraf ekle", None, self._photo)
        self.send_btn = button("Gönder", "primary", self._send)
        lay.addLayout(hbox(self.input, self.photo_btn, self.send_btn, spacing=8))
        self.photo: bytes | None = None
        self.relay = _Relay()
        self.relay.answered.connect(self._answer)
        self._log: list[str] = []
        self._add("asistan", GREETING)

    def _add(self, who: str, text: str) -> None:
        """Sohbet balonu: yardımcı solda koyu, sen sağda pembe tonlu."""
        me = who != "asistan"
        color = T.TEXT if me else T.A2
        name = "Sen" if me else "Yardımcı"
        bg = "#2c1a2a" if me else T.SURFACE2
        side = "right" if me else "left"
        face = ""
        if not me:
            from .widgets import marka_path
            bot = marka_path("bot.png")
            if bot.exists():
                face = f"<img src='{bot.as_uri()}' width='26' height='26' style='vertical-align:middle'> "
        self._log.append(f"<table width='86%' align='{side}' cellpadding='10' cellspacing='0' "
                         f"style='background-color:{bg}; margin-bottom:10px'><tr><td>"
                         f"{face}<b style='color:{color}'>{name}</b><br>{md_html(text)}</td></tr></table>"
                         "<table width='100%' cellspacing='0' cellpadding='0'><tr><td height='4'></td></tr></table>")
        self.view.setHtml("".join(self._log))
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def _ask_chip(self, text: str) -> None:
        self.input.setText(text)
        self._send()

    def _photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ekranın fotoğrafı", "", "Resim (*.png *.jpg *.jpeg *.heic)")
        if not path:
            return
        try:
            import cv2
            img = cv2.imread(path)
            if img is None:
                raise ValueError("resim açılamadı")
            scale = min(1.0, 1568 / max(img.shape[:2]))
            if scale < 1:
                img = cv2.resize(img, (int(img.shape[1] * scale), int(img.shape[0] * scale)))
            ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            self.photo = jpg.tobytes() if ok else None
            self.photo_btn.setText("Fotoğraf eklendi ✓")
        except Exception as e:  # noqa: BLE001
            self._add("asistan", f"Fotoğrafı açamadım ({e}). PNG ya da JPG dene.")

    def _send(self) -> None:
        q = self.input.text().strip()
        if not q:
            return
        self.input.clear()
        self.chips.hide()
        self._add("sen", q + (" 📷" if self.photo else ""))
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Yazıyor...")
        photo, self.photo = self.photo, None
        self.photo_btn.setText("Fotoğraf ekle")
        threading.Thread(target=lambda: self.relay.answered.emit(self.bot.ask(q, photo)), daemon=True).start()

    def _answer(self, text: str) -> None:
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Gönder")
        self._add("asistan", text)
        self.input.setFocus(Qt.OtherFocusReason)
