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


def run_gui(argv: list[str] | None = None, background: bool = False) -> int:
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
    instance = _single_instance()
    if instance is None:                     # program zaten açık: onun penceresi öne geldi
        logging.getLogger(__name__).info("Program zaten açık; açık olan pencere öne getirildi")
        return 0
    app.setApplicationName("GTA6 Altyazı")
    app.setStyle("Fusion")
    try:                                         # açık / koyu görünüm (Hakkında › Görünüm)
        T.apply(config_mod.load().gosterim.tema)
    except Exception:  # noqa: BLE001
        T.apply("koyu")
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
    instance.newConnection.connect(lambda: _bring_to_front(instance, win))
    if background:          # Windows açılışında: simge durumunda başla, sihirbazı açma
        win.showMinimized()
    else:
        win.show()
        if first:
            config_mod.save(cfg)   # sihirbaz yarıda kapatılsa da bir dahakine ana ekran açılsın
            win.open_wizard()
    code = app.exec()
    _exit(ctl, code)
    return code


def _single_instance():  # noqa: ANN202
    """Tek kopya: açık bir kopya varsa ona 'öne gel' de ve None döndür; yoksa dinleyen QLocalServer döndür."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    from ..tekkopya import instance_name
    name = instance_name()
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(800):
        sock.write(b"goster\n")
        sock.flush()
        sock.waitForBytesWritten(800)
        sock.disconnectFromServer()
        return None
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(name):
        QLocalServer.removeServer(name)        # önceki kopya çöktüyse kalan ad (Mac/Linux)
        server.listen(name)
    return server


def _bring_to_front(server, win) -> None:  # noqa: ANN001
    from PySide6.QtCore import Qt
    while server.hasPendingConnections():
        c = server.nextPendingConnection()
        c.disconnected.connect(c.deleteLater)
    win.setWindowState((win.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
    win.showNormal()
    win.raise_()
    win.activateWindow()


def _exit(ctl, code: int) -> None:  # noqa: ANN001
    """Pencere kapanınca süreç gerçekten bitsin. Yoksa arka planda süren bir iş (çeviri isteği, model yükleme) süreci
    penceresiz açık tutuyor, port 8787'yi bırakmıyordu; program yeniden açılınca "port başka bir programda" çıkıyordu.
    Ayarlar ve çeviri önbelleği zaten anında yazılıyor."""
    try:
        ctl.shutdown()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Kapanışta hata")
    logging.getLogger(__name__).info("Program kapandı")
    logging.shutdown()
    if os.environ.get("GTA6_NO_HARD_EXIT") != "1":
        os._exit(code)
