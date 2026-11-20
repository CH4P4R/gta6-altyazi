"""Programın tek kopyası ve yerel sunucu portu (8787).

- Program ikinci kez açılınca (ör. Windows açılışında simge durumunda açılmışken masaüstünden yeniden açılınca) ikinci
  kopya açılmaz; açık olan pencere öne gelir. Eskiden ikinci kopya açılıp "port 8787 başka bir programda" diyordu.
- Port doluysa onu hangi programın tuttuğu bulunur. Penceresiz kalmış eski bir GTA6 Altyazı kopyasıysa kapatılır;
  başka bir programsa adıyla söylenir.
"""

from __future__ import annotations

import csv
import getpass
import io
import json
import logging
import os
import re
import socket
import subprocess
import sys
import urllib.request

log = logging.getLogger(__name__)

APP_EXE = "gta6altyazi"          # Windows'ta GTA6Altyazi.exe, Mac'te .app içindeki GTA6Altyazi
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def instance_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "kullanici"
    return "gta6altyazi-" + re.sub(r"[^A-Za-z0-9_.-]", "_", user)[:40]


# ------------------------------------------------------------------------------------------- port
def _hello(port: int, timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/hello"), timeout=timeout) as r:
            data = json.loads(r.read() or b"{}")
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return None


def _run(cmd: list[str], timeout: float = 8) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or b"").decode("utf-8", "replace") if r.stdout else ""


def parse_netstat(text: str, port: int) -> int | None:
    """'netstat -ano -p TCP' çıktısında portu dinleyen sürecin numarası."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1].endswith(f":{port}") and parts[-1].isdigit():
            if parts[2].endswith(":0"):          # dinleyen soket: karşı adres 0.0.0.0:0 (durum adı dile göre değişir)
                return int(parts[-1])
    return None


def parse_tasklist(text: str) -> str | None:
    """'tasklist /FO CSV /NH' çıktısının ilk satırındaki program adı."""
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 2 and row[1].strip().isdigit():
            return row[0].strip()
    return None


def listener_pid(port: int) -> int | None:
    if sys.platform == "win32":
        return parse_netstat(_run(["netstat", "-ano", "-p", "TCP"]), port)
    out = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"])
    pids = [int(x) for x in out.split() if x.isdigit()]
    return pids[0] if pids else None


def process_name(pid: int) -> str | None:
    if sys.platform == "win32":
        return parse_tasklist(_run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]))
    name = _run(["ps", "-p", str(pid), "-o", "comm="]).strip()
    return os.path.basename(name) or None


def port_holder(port: int) -> tuple[str, int | None, str]:
    """Portu kim tutuyor: ('gta6altyazi' | 'baska' | 'bos', süreç numarası, program adı)."""
    hello = _hello(port)
    pid = listener_pid(port)
    name = process_name(pid) if pid else None
    if hello and hello.get("app") == "gta6altyazi":
        pid = int(hello.get("pid") or pid or 0) or None
        return "gta6altyazi", pid, name or "GTA6 Altyazı"
    if name and os.path.splitext(name)[0].lower() == APP_EXE:
        return "gta6altyazi", pid, name
    if pid or hello is not None or _accepts(port):
        return "baska", pid, name or "bilinmeyen program"
    return "bos", None, ""


def _accepts(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def kill(pid: int) -> bool:
    if not pid or pid == os.getpid():
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10,
                           creationflags=_NO_WINDOW)
        else:
            os.kill(pid, 9)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def holder_message(port: int, kind: str, name: str) -> str:
    if kind == "baska":
        nice = "CouchSubs" if "couch" in name.lower() else name
        return (f"Port {port} şu programda: {nice}. TV'ye altyazı gönderebilmek için onu kapat; GTA6 Altyazı birkaç "
                "saniye içinde kendiliğinden bağlanır.")
    return f"Yerel sunucu (port {port}) açılmayı bekliyor; birkaç saniye içinde kendiliğinden açılır."
