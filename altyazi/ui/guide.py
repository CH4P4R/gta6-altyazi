"""Resimli adım adım rehber görünümü (sihirbaz ve Rehber sayfası ortak kullanır). İçerik: altyazi/rehber.py."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from .. import rehber
from . import theme as T
from .widgets import button, hbox, label

REHBER = Path(__file__).resolve().parent / "rehber"


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
    """Adımlar: rehber.step(...) sözlükleri. extras: adım kimliği → o adımın altında gösterilecek düğme/durum."""

    def __init__(self, nav: bool = False):
        super().__init__()
        self.steps: list[dict] = []
        self.extras: dict[str, QWidget] = {}
        self._links: dict[int, QWidget] = {}
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
        self._empty = QWidget()
        self.extra.addWidget(self._empty)
        self.dots = QHBoxLayout()
        self.dots.setSpacing(6)
        self._dots: list[QFrame] = []
        self.prev_btn = self.next_btn = None
        if nav:                                      # Rehber sayfasında kendi Geri/İleri düğmeleri
            self.prev_btn = button("‹ Önceki", "ghost", self.back)
            self.next_btn = button("Sonraki ›", "primary", self.next)
            lay.addLayout(hbox(self.dots, None, self.prev_btn, self.next_btn, spacing=10))
        else:
            lay.addLayout(self.dots)

    def set_steps(self, steps: list[dict], extras: dict[str, QWidget] | None = None) -> None:
        self.steps = steps
        self.extras = extras or {}
        for w in self.extras.values():
            if self.extra.indexOf(w) < 0:
                self.extra.addWidget(w)
        for w in self._links.values():
            self.extra.removeWidget(w)
            w.deleteLater()
        self._links = {}
        for i, st in enumerate(steps):
            if st.get("link") and st.get("id") not in self.extras:
                text, url = st["link"]
                w = QWidget()
                w.setLayout(hbox(button(text, "primary", lambda _=False, u=url: webbrowser.open(u)), None))
                self.extra.addWidget(w)
                self._links[i] = w
        for d in self._dots:
            self.dots.removeWidget(d)
            d.setParent(None)
            d.deleteLater()
        self._dots = []
        for _ in steps:
            d = QFrame()
            d.setFixedSize(26, 6)
            self._dots.append(d)
            self.dots.addWidget(d)
        self.show_step(min(self.index, len(steps) - 1) if steps else 0)

    def show_step(self, i: int) -> None:
        if not self.steps:
            return
        self.index = i
        st = self.steps[i]
        self.image.set_image(st.get("img"))
        self.title.setText(st["title"])
        self.counter.setText(f"ADIM {i + 1} / {len(self.steps)}")
        self.text.setText(rehber.to_html(st, T.FAINT))
        extra = self.extras.get(st.get("id") or "") or self._links.get(i)
        self.extra.setCurrentWidget(extra or self._empty)
        self.extra.setVisible(extra is not None)
        for k, d in enumerate(self._dots):
            d.setStyleSheet(f"background: {T.A1 if k <= i else T.BORDER_HI}; border-radius: 3px;")
        if self.prev_btn is not None:
            self.prev_btn.setEnabled(self.can_back())
            self.next_btn.setEnabled(self.can_next())

    def can_next(self) -> bool:
        return self.index < len(self.steps) - 1

    def can_back(self) -> bool:
        return self.index > 0

    def next(self) -> None:
        if self.can_next():
            self.show_step(self.index + 1)

    def back(self) -> None:
        if self.can_back():
            self.show_step(self.index - 1)
