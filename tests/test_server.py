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


def test_remote_command_endpoint_and_page():
    import urllib.request
    port = free_port()
    calls = []
    srv = EventServer(port, on_command=lambda ad: (calls.append(ad), {"mesaj": "ok", "duraklatildi": True})[1])
    srv.start()
    time.sleep(0.2)
    req = urllib.request.Request(f"http://127.0.0.1:{port}/komut/duraklat", method="POST")
    with urllib.request.urlopen(req, timeout=3) as r:
        assert json.loads(r.read()) == {"mesaj": "ok", "duraklatildi": True}
    assert calls == ["duraklat"]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/kumanda", timeout=3) as r:
        assert "Ekranı çevir" in r.read().decode()


def test_hotkey_parse():
    from altyazi.hotkeys import parse
    assert parse("ctrl+shift+9") == (0x2 | 0x4, ord("9"))
    assert parse("num9") == (0, 0x69)
    assert parse("alt+F10") == (0x1, 0x79)


def test_claude_read_screen_request_shape(monkeypatch):
    import threading as th
    from http.server import BaseHTTPRequestHandler, HTTPServer
    seen = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            out = {"items": [{"id": 0, "english": "Go to the car.", "turkish": "Arabaya git.", "box": [0, 0, 0, 0]}]}
            r = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
                 "stop_reason": "end_turn", "stop_sequence": None,
                 "content": [{"type": "text", "text": json.dumps(out)}], "usage": {"input_tokens": 1, "output_tokens": 1}}
            b = json.dumps(r).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
    srv = HTTPServer(("127.0.0.1", 0), H)
    th.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    from altyazi.config import CeviriCfg
    from altyazi.translate import ClaudeMT
    m = ClaudeMT(CeviriCfg(claude_anahtar="test"))
    items = m.read_screen(b"\xff\xd8fakejpeg", [(0, "Go to the cor.")])
    assert items == [{"id": 0, "english": "Go to the car.", "turkish": "Arabaya git.", "box": [0, 0, 0, 0]}]
    b = seen["body"]
    img, txt = b["messages"][0]["content"]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/jpeg"
    assert "0: Go to the cor." in txt["text"]
    assert b["output_config"]["format"]["type"] == "json_schema"
    assert b["output_config"]["format"]["schema"]["required"] == ["items"]
    assert b["speed"] == "fast" and b["fallbacks"] == "default"
    srv.shutdown()
