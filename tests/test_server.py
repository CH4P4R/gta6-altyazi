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
    from altyazi.harcama import tracker
    m = ClaudeMT(CeviriCfg(claude_anahtar="test"))
    before = tracker.requests
    items = m.read_screen(b"\xff\xd8fakejpeg", [(0, "Go to the cor.")])
    assert items == [{"id": 0, "english": "Go to the car.", "turkish": "Arabaya git.", "box": [0, 0, 0, 0]}]
    b = seen["body"]
    img, txt = b["messages"][0]["content"]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/jpeg"
    assert "0: Go to the cor." in txt["text"]
    assert b["output_config"]["format"]["type"] == "json_schema"
    assert b["output_config"]["format"]["schema"]["required"] == ["items"]
    assert b["speed"] == "fast" and b["fallbacks"] == "default"
    assert tracker.requests == before + 1                    # yanıtın token sayısı harcama sayacına yazıldı
    srv.shutdown()


def test_tv_protocol_events():
    """TV uygulamaları (CouchSubs protokolü): style ilk gelir, altyazı/ek alan/tam ekran olaylara çevrilir."""
    import socket as _s
    import time as _t
    import urllib.request as _u

    from altyazi.pipeline import DisplayItem
    from altyazi.server import EventServer

    s = _s.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = EventServer(port)
    srv.start()
    _t.sleep(0.2)
    resp = _u.urlopen(f"http://127.0.0.1:{port}/events", timeout=5)

    def read_event():
        name, data = None, None
        while True:
            line = resp.readline().decode().rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
            elif line == "" and name:
                return name, data

    assert read_event()[0] == "style"
    for _ in range(50):
        if srv.tv_count:
            break
        _t.sleep(0.02)
    base = dict(rect=(0.2, 0.8, 0.8, 0.86), zone_rect=(0, 0.75, 1, 0.95), line_h=0.03, english="Get in the car.",
                align="orta", anchor="alt", box_opacity=255, font_scale=1.3)
    srv.show(DisplayItem(zone="altyazi", text="Arabaya bin.", seq=5, **base))
    name, data = read_event()
    assert name == "subtitle" and data["text"] == "Arabaya bin." and data["box"]["top"] == 0.8 and "replace" not in data
    srv.show(DisplayItem(zone="altyazi", text="Arabaya bin!", seq=5, **base))
    assert read_event()[1]["replace"] is True
    srv.show(DisplayItem(zone="yardim", text="Araca binmek için △", seq=6, **base))
    name, data = read_event()
    assert name == "region" and data["id"] == "yardim"
    srv.clear("yardim")
    assert read_event() == ("region", {"id": "yardim", "text": ""})
    srv.show(DisplayItem(zone="altyazi.2", text="Arabaya git.", seq=8, **base))
    name, data = read_event()
    assert name == "region" and data["main"] is True        # ayrılan paragraf TV'de altyazı boyunda
    srv.show(DisplayItem(zone="tam0", text="Harita", seq=7, **base))
    name, data = read_event()
    assert name == "screen" and data["items"][0]["text"] == "Harita"
    srv.clear("tam0")
    assert read_event()[0] == "screen-clear"
    srv.clear("altyazi")
    assert read_event()[0] == "clear"


class _Resp:
    def __init__(self, code, data=None, text=""):
        self.status_code, self._data, self.text = code, data or {}, text

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_gemini_rest_request_and_model_fallback():
    """Gemini SDK'sız çalışır (kurulumda ek paket yok); eskimiş model adında sıradakine geçer."""
    from altyazi.config import CeviriCfg
    from altyazi.translate import GeminiMT
    mt = GeminiMT(CeviriCfg(gemini_anahtar="k", gemini_model="eski-model"))
    calls = []

    def post(url, json=None, timeout=None):
        calls.append((url, json))
        if "eski-model" in url:
            return _Resp(404)
        return _Resp(200, {"candidates": [{"content": {"parts": [{"text": "Arabaya bin."}]}}]})
    mt.s.post = post
    assert mt.translate("Get in the car.", "altyazi") == "Arabaya bin."
    assert "gemini-flash-latest:generateContent" in calls[-1][0]
    body = calls[-1][1]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert "Get in the car." in body["contents"][0]["parts"][0]["text"]
    assert "Grand Theft Auto" in body["systemInstruction"]["parts"][0]["text"]
    assert mt.s.headers["x-goog-api-key"] == "k"


def test_local_ai_openai_compatible():
    from altyazi.config import CeviriCfg
    from altyazi.translate import LocalAIMT, TranslationEngine
    mt = LocalAIMT(CeviriCfg(yerelai_adres="http://localhost:11434/v1/", yerelai_model="qwen2.5:7b"))
    seen = {}

    def post(url, json=None, timeout=None):
        seen.update(url=url, body=json)
        return _Resp(200, {"choices": [{"message": {"content": "<think>hmm</think>\nArabaya bin."}}]})
    mt.s.post = post
    assert mt.translate("Get in the car.", "altyazi") == "Arabaya bin."
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["body"]["model"] == "qwen2.5:7b" and seen["body"]["messages"][0]["role"] == "system"
    # anahtarsız da kalite katmanı olarak açılır
    assert isinstance(TranslationEngine._make_refine(CeviriCfg(kalite="yerelai")), LocalAIMT)
