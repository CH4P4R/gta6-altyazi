"""Arayüzlü uygulamanın giriş noktası."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")


def setup_logging() -> None:
    from .. import paths
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(paths.data("altyazi.log"), maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stderr:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    for noisy in ("httpx", "httpx2", "anthropic", "urllib3", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run_gui(argv: list[str] | None = None) -> int:
    from .. import winutil
    winutil.set_dpi_aware()
    winutil.add_cuda_dll_dirs()
    setup_logging()

    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from .. import config as config_mod
    from ..app import AppController
    from . import theme as T
    from .main_window import MainWindow, app_icon

    app = QApplication(argv or sys.argv)
    app.setApplicationName("GTA6 Altyazı")
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in ((QPalette.Window, T.BG), (QPalette.Base, T.SURFACE2), (QPalette.Text, T.TEXT),
                        (QPalette.WindowText, T.TEXT), (QPalette.Button, T.SURFACE2), (QPalette.ButtonText, T.TEXT),
                        (QPalette.Highlight, T.A1), (QPalette.HighlightedText, "#ffffff"),
                        (QPalette.PlaceholderText, T.FAINT), (QPalette.ToolTipBase, T.SURFACE3),
                        (QPalette.ToolTipText, T.TEXT)):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setFont(T.font(10))
    app.setStyleSheet(T.QSS)
    app.setWindowIcon(app_icon())

    first = config_mod.is_first_run()
    cfg = config_mod.load()
    ctl = AppController(cfg)
    win = MainWindow(ctl)
    win.show()
    if first:
        config_mod.save(cfg)   # sihirbaz yarıda kapatılsa da bir dahakine ana ekran açılsın
        win.open_wizard()
    return app.exec()
