import json
import socket
import time

from altyazi.pipeline import DisplayItem
from altyazi.server import EventServer


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_tv_stream_delivers_fast_with_all_fields():
    port = free_port()
    srv = EventServer(port, [0.01, 0.02, 0.98, 0.97])
    srv.start()
    time.sleep(0.2)
    c = socket.create_connection(("127.0.0.1", port), timeout=3)
    c.sendall(b"GET /olaylar HTTP/1.1\r\nHost: x\r\nAccept: text/event-stream\r\n\r\n")
    f = c.makefile("rb")
    while f.readline() not in (b"\r\n", b"\n"):   # HTTP başlıklarını atla
        pass
    time.sleep(0.1)
    it = DisplayItem("altyazi", (0.3, 0.85, 0.7, 0.93), (0.1, 0.76, 0.9, 0.97), 0.037, "Get in.", "Bin.",
                     "orta", "alt", 255, 1.0, source="yerel", latency_ms=42)
    t = time.perf_counter()
    srv.show(it)
    line = f.readline()
    ms = (time.perf_counter() - t) * 1000
    assert line.startswith(b"data: ")
    d = json.loads(line[6:])
    assert d["type"] == "show" and d["text"] == "Bin." and d["zone_rect"] == [0.1, 0.76, 0.9, 0.97]
    assert d["line_h"] == 0.037 and d["box_opacity"] == 255 and d["tv"] == {"x": 0.01, "y": 0.02, "w": 0.98, "h": 0.97}
    assert ms < 50, ms
    f.readline()
    srv.clear("altyazi")
    assert json.loads(f.readline()[6:]) == {"type": "clear", "zone": "altyazi"}
    c.close()
