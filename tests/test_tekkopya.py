"""Tek kopya ve port 8787'yi kimin tuttuğu."""

import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from altyazi import tekkopya


def free_port():
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    p = s.getsockname()[1]
    s.close()
    return p


NETSTAT_TR = """
Etkin Bağlantılar

  Proto  Yerel Adres            Yabancı Adres          Durum           PID
  TCP    0.0.0.0:135            0.0.0.0:0              DİNLENİYOR      1100
  TCP    0.0.0.0:8787           0.0.0.0:0              DİNLENİYOR      4242
  TCP    192.168.1.20:8787      192.168.1.50:51234     KURULDU         4242
  TCP    [::]:8787              [::]:0                 DİNLENİYOR      4242
"""


def test_parse_netstat_any_language():
    assert tekkopya.parse_netstat(NETSTAT_TR, 8787) == 4242
    assert tekkopya.parse_netstat(NETSTAT_TR, 135) == 1100
    assert tekkopya.parse_netstat(NETSTAT_TR, 9999) is None
    # yalnız kurulu bağlantı (dinleyen yok) dolu sayılmaz
    assert tekkopya.parse_netstat("  TCP    1.2.3.4:8787   5.6.7.8:5000   ESTABLISHED   7\n", 8787) is None


def test_parse_tasklist():
    assert tekkopya.parse_tasklist('"CouchSubs.exe","4242","Console","1","120.000 K"\r\n') == "CouchSubs.exe"
    assert tekkopya.parse_tasklist("BİLGİ: Belirtilen ölçütlerle eşleşen çalışan görev yok.\r\n") is None


def test_port_holder_free():
    assert tekkopya.port_holder(free_port())[0] == "bos"


def test_port_holder_our_server_reports_pid():
    from altyazi.server import EventServer
    port = free_port()
    srv = EventServer(port)
    srv.start()
    kind, pid, _name = tekkopya.port_holder(port)
    assert kind == "gta6altyazi" and pid == os.getpid()


def test_port_holder_other_program():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(404)
            self.end_headers()

        def log_message(self, *a):
            pass

    class Quick(HTTPServer):
        def server_bind(self):  # ters DNS (getfqdn) macOS CI'da 35 sn sürüyordu
            import socketserver
            socketserver.TCPServer.server_bind(self)
            self.server_name, self.server_port = "localhost", self.server_address[1]

    port = free_port()
    httpd = Quick(("0.0.0.0", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        kind, _pid, name = tekkopya.port_holder(port)
        assert kind == "baska"
        msg = tekkopya.holder_message(port, kind, "CouchSubs.exe")
        assert "CouchSubs" in msg and "kendiliğinden" in msg
    finally:
        httpd.shutdown()


def test_kill_never_kills_self():
    assert tekkopya.kill(os.getpid()) is False
    assert tekkopya.kill(0) is False


def test_single_instance(monkeypatch):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(tekkopya, "instance_name", lambda: f"gta6altyazi-test-{os.getpid()}")
    from altyazi.ui import run
    first = run._single_instance()
    assert first is not None and first.isListening()
    assert run._single_instance() is None          # ikinci kopya açılmaz
    app.processEvents()
    first.close()
    third = run._single_instance()                 # ilk kopya kapanınca yeniden açılabilir
    assert third is not None
    third.close()


def test_multisink_add():
    from altyazi.pipeline import MultiSink

    class S:
        def __init__(self):
            self.n = 0

        def show(self, it):
            self.n += 1

        def clear(self, z):
            pass

    a, b = S(), S()
    m = MultiSink(a, None)
    m.add(b)
    m.add(b)
    m.show(object())
    assert a.n == 1 and b.n == 1


def test_server_retries_until_port_frees(monkeypatch):
    """Port doluyken program açılırsa sunucu birkaç saniyede bir yeniden dener; port boşalınca kendiliğinden açılır."""
    import time
    import types

    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from altyazi.app import AppController
    from altyazi.config import Config

    app = QApplication.instance() or QApplication([])
    port = free_port()
    blocker = socket.socket()
    blocker.bind(("0.0.0.0", port))
    blocker.listen(1)

    class Fake(QObject):
        pass

    f = Fake()
    cfg = Config()
    cfg.sunucu.port = port
    f.cfg, f.server, f.pipe = cfg, None, None
    f.tv_state = ("hata", "")
    states = []
    f._tv = lambda *a: (states.append(a), setattr(f, "tv_state", a))
    f.command = lambda *a, **k: {}
    f._apply_tv_style = lambda: None
    for name in ("_try_server", "_retry_server"):
        setattr(f, name, types.MethodType(getattr(AppController, name), f))
    AppController._start_server(f)
    assert f.server is None
    assert "kendiliğinden" in f.server_problem
    AppController.tv_connect(f, "192.168.1.40")        # sunucu yokken TV bağlan: sebebi söylenir
    assert states[-1][0] == "hata" and "kendiliğinden" in states[-1][1]
    blocker.close()
    end = time.time() + 8
    while f.server is None and time.time() < end:
        app.processEvents()
        time.sleep(0.05)
    assert f.server is not None and f.server_problem == ""
    assert tekkopya.port_holder(port)[0] == "gta6altyazi"


def test_orphan_copy_is_closed_and_port_taken(monkeypatch):
    """Penceresi kapanmış ama süreci kalmış eski kopya portu tutuyorsa kapatılır, sunucu hemen açılır."""
    import subprocess
    import sys
    import time
    import types
    import urllib.request

    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from altyazi.app import AppController
    from altyazi.config import Config

    QApplication.instance() or QApplication([])
    port = free_port()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orphan = subprocess.Popen([sys.executable, "-c",
                               f"import time; from altyazi.server import EventServer; EventServer({port}).start(); "
                               "time.sleep(120)"], cwd=root)
    try:
        end = time.time() + 15
        while time.time() < end:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/hello", timeout=1)
                break
            except OSError:
                time.sleep(0.2)

        class Fake(QObject):
            pass

        f = Fake()
        cfg = Config()
        cfg.sunucu.port = port
        f.cfg, f.server, f.pipe, f.tv_state = cfg, None, None, ("yok", "")
        f._tv = lambda *a: None
        f.command = lambda *a, **k: {}
        f._apply_tv_style = lambda: None
        for name in ("_try_server", "_retry_server"):
            setattr(f, name, types.MethodType(getattr(AppController, name), f))
        AppController._start_server(f)
        assert f.server is not None, f.server_problem
        assert orphan.wait(10) is not None
        kind, pid, _ = tekkopya.port_holder(port)
        assert kind == "gta6altyazi" and pid == os.getpid()
    finally:
        if orphan.poll() is None:
            orphan.kill()
