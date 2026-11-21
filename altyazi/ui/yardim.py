"""Yardım sohbeti penceresi ("Sor"): rehberi ve programın durumunu bilen yapay zekâya soru sorulur (yardimci.py)."""

from __future__ import annotations

import html
import re
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QLineEdit, QTextBrowser, QVBoxLayout

from . import theme as T
from .widgets import button, hbox, label, vbox


class _Relay(QObject):
    answered = Signal(str)


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
                           f"solid {T.BORDER}; border-radius: 14px; padding: 12px; font-size: 12pt; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        engine = self.bot.available()
        lay.addLayout(vbox(label("Sor", "h1"),
                           label("Takıldığın yeri yaz: TV'nin markası, ekranda ne yazdığı... Adım adım anlatırım. "
                                 "İstersen ekranın fotoğrafını da ekle." +
                                 (f" (Cevaplar senin {engine.capitalize()} anahtarınla.)" if engine else ""),
                                 "muted", wrap=True), spacing=4))
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)
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
        self._add("asistan", "Selam! Kurulumda ya da oyunda nerede takıldın? Ekranda bir hata yazıyorsa aynen yaz.")

    def _add(self, who: str, text: str) -> None:
        color = T.A2 if who == "asistan" else T.TEXT
        name = "Asistan" if who == "asistan" else "Sen"
        self._log.append(f"<p><b style='color:{color}'>{name}</b><br>{md_html(text)}</p>")
        self.view.setHtml("".join(self._log))
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

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
