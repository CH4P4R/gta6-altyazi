"""Yerel web sunucusu: OBS tarayıcı kaynağı veya TV/telefon tarayıcısı için canlı altyazı.

http://localhost:8787/        -> siyah zeminde altyazı (TV/telefon için)
http://localhost:8787/obs     -> saydam zeminde altyazı (OBS tarayıcı kaynağı)
http://localhost:8787/olaylar -> Server-Sent Events akışı (JSON)
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .pipeline import DisplayItem

log = logging.getLogger(__name__)

PAGE = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>GTA6 Altyazı</title>
<style>
html,body{margin:0;height:100%;background:BG;font-family:'Segoe UI',Roboto,sans-serif;overflow:hidden}
#z{position:absolute;inset:0}
.i{position:absolute;left:5%;right:5%;text-align:center;color:#fff;font-weight:600;
   font-size:4.2vh;line-height:1.25;text-shadow:0 0 4px #000,0 0 4px #000,2px 2px 2px #000}
.i span{background:rgba(0,0,0,.6);padding:.1em .4em;border-radius:.2em;box-decoration-break:clone;
   -webkit-box-decoration-break:clone}
</style></head><body><div id="z"></div><script>
const z=document.getElementById('z'),els={};
function put(d){let e=els[d.zone];if(!e){e=els[d.zone]=document.createElement('div');e.className='i';z.appendChild(e)}
 const top=d.rect[1]*100,bottom=(1-d.rect[3])*100;
 if(d.anchor==='alt'){e.style.bottom=bottom+'%';e.style.top=''}else{e.style.top=top+'%';e.style.bottom=''}
 e.style.textAlign=d.align==='sol'?'left':d.align==='sag'?'right':'center';
 e.innerHTML='';const s=document.createElement('span');s.textContent=d.text;e.appendChild(s)}
function go(){const es=new EventSource('/olaylar');
 es.onmessage=m=>{const d=JSON.parse(m.data);if(d.type==='show')put(d);else if(els[d.zone]){els[d.zone].remove();delete els[d.zone]}};
 es.onerror=()=>{es.close();setTimeout(go,1000)}}
go();
</script></body></html>"""


class EventServer:
    def __init__(self, port: int, tv_calibration: list[float] | None = None):
        self.port = port
        x, y, w, h = tv_calibration or [0.0, 0.0, 1.0, 1.0]
        self.tv = {"x": x, "y": y, "w": w, "h": h}
        self.clients: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.state: dict[str, dict] = {}

    # Sink arayüzü
    def show(self, it: DisplayItem) -> None:
        msg = {"type": "show", "zone": it.zone, "text": it.text, "english": it.english, "rect": it.rect,
               "zone_rect": it.zone_rect, "line_h": it.line_h, "align": it.align, "anchor": it.anchor,
               "box_opacity": it.box_opacity, "font_scale": it.font_scale, "tv": self.tv,
               "source": it.source, "latency_ms": round(it.latency_ms)}
        self.state[it.zone] = msg
        self._broadcast(msg)

    def clear(self, zone: str) -> None:
        self.state.pop(zone, None)
        self._broadcast({"type": "clear", "zone": zone})

    def _broadcast(self, msg: dict) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        with self.lock:
            for q in self.clients:
                q.put(data)

    def start(self) -> None:
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: ANN002
                pass

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                if path in ("/", "/obs"):
                    body = PAGE.replace("BG", "transparent" if path == "/obs" else "#000").encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif path == "/olaylar":
                    # Küçük mesajlar Nagle algoritması yüzünden 40-200 ms beklemesin
                    self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    q: queue.Queue = queue.Queue()
                    for m in list(srv.state.values()):
                        q.put(json.dumps(m, ensure_ascii=False))
                    with srv.lock:
                        srv.clients.append(q)
                    try:
                        while True:
                            try:
                                data = q.get(timeout=15)
                                self.wfile.write(f"data: {data}\n\n".encode())
                            except queue.Empty:
                                self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    finally:
                        with srv.lock:
                            srv.clients.remove(q)
                else:
                    self.send_error(404)

        httpd = ThreadingHTTPServer(("0.0.0.0", self.port), H)
        httpd.daemon_threads = True
        threading.Thread(target=httpd.serve_forever, daemon=True, name="sunucu").start()
        log.info("Web: http://localhost:%d/  (OBS için /obs)", self.port)
