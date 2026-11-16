"""PS5'i ev ağında bulma (Remote Play keşif protokolü, chiaki ile aynı).

PS5'e UDP 9302'den "SRCH" mesajı gider; PS5 açıksa "HTTP/1.1 200 Ok", dinlenme modundaysa
"HTTP/1.1 620 Server Standby" ile ve adıyla (host-name) cevap verir.
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

PORT = 9302
PROTOCOL = "00030010"
LOCAL_PORTS = range(9303, 9320)   # chiaki de önce bu aralıktan bağlanır


@dataclass
class Console:
    ip: str
    name: str
    awake: bool
    host_type: str = ""
    running_app: str = ""


def parse_response(data: bytes, ip: str) -> Console | None:
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if not lines or not lines[0].startswith("HTTP/1.1"):
        return None
    parts = lines[0].split()
    code = parts[1] if len(parts) > 1 else ""
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return Console(ip=ip, name=headers.get("host-name", ""), awake=code == "200",
                   host_type=headers.get("host-type", ""), running_app=headers.get("running-app-name", ""))


def _socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    for p in LOCAL_PORTS:
        try:
            s.bind(("", p))
            return s
        except OSError:
            continue
    s.bind(("", 0))
    return s


def discover(timeout: float = 1.5, targets: list[str] | None = None, port: int = PORT) -> list[Console]:
    """Ağdaki PS5'leri bul. targets verilmezse yayın (broadcast) yapılır."""
    msg = f"SRCH * HTTP/1.1\ndevice-discovery-protocol-version:{PROTOCOL}\n".encode()
    if targets is None:
        targets = ["255.255.255.255"]
        try:
            from .tv import local_ip
            ip = local_ip()
            targets.append(".".join(ip.split(".")[:3] + ["255"]))
        except OSError:
            pass
    found: dict[str, Console] = {}
    s = _socket()
    try:
        s.settimeout(0.2)
        deadline = time.time() + timeout
        next_send = 0.0
        while time.time() < deadline:
            if time.time() >= next_send:          # UDP kaybolabilir: birkaç kez gönder
                for t in targets:
                    try:
                        s.sendto(msg, (t, port))
                    except OSError:
                        pass
                next_send = time.time() + 0.5
            try:
                data, (ip, _p) = s.recvfrom(2048)
            except (socket.timeout, OSError):
                continue
            c = parse_response(data, ip)
            if c:
                found[ip] = c
    finally:
        s.close()
    return list(found.values())
