"""Yerel web sunucusu: OBS tarayıcı kaynağı veya TV/telefon tarayıcısı için canlı altyazı.

http://localhost:8787/        -> siyah zeminde altyazı (TV/telefon için)
http://localhost:8787/obs     -> saydam zeminde altyazı (OBS tarayıcı kaynağı, 1920x1080, oyun görüntüsünün üstüne)
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
<style>html,body{margin:0;height:100%;background:BG;overflow:hidden}canvas{display:block}</style>
</head><body><canvas id="c"></canvas><script>
// PC ve TV'deki çizimle aynı: İngilizcenin yerini kutuyla kapatır, Türkçeyi aynı boyutta ortasına yazar.
// OBS: Tarayıcı kaynağı, 1920x1080, oyun görüntüsünün (capture kart) tam üstüne.
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),items={};
const FONT='600 {px}px "Segoe UI Semibold","Segoe UI",Roboto,sans-serif';
function size(){const r=devicePixelRatio||1;cv.width=innerWidth*r;cv.height=innerHeight*r;
 cv.style.width=innerWidth+'px';cv.style.height=innerHeight+'px';ctx.setTransform(r,0,0,r,0,0);draw()}
function wrap(t,maxW){const out=[];let cur='';for(const w of t.trim().split(/\\s+/)){const tr=cur?cur+' '+w:w;
 if(cur&&ctx.measureText(tr).width>maxW){out.push(cur);cur=w}else cur=tr}if(cur)out.push(cur);return out.length?out:['']}
function rrect(x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);
 ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();ctx.fill()}
function item(it,W,H){const [x0,y0,x1,y1]=it.rect,z=it.zone_rect||it.rect;
 const R={l:x0*W,t:y0*H,r:x1*W,b:y1*H};R.w=R.r-R.l;R.h=R.b-R.t;
 const zoneW=(z[2]-z[0])*W,line=Math.max(14,(it.line_h||0.035)*H),pad=line*0.28;
 ctx.font=FONT.replace('{px}',Math.round(line*0.92*(it.font_scale||1)));
 const maxW=it.align==='orta'?Math.max(R.w,zoneW*0.96):Math.min(zoneW,Math.max(R.w*1.15,line*12));
 const lines=wrap(it.text,maxW-2*pad),m=ctx.measureText('Ğg'),asc=m.actualBoundingBoxAscent,fh=asc+m.actualBoundingBoxDescent;
 const sp=fh*1.15,tw=Math.max(...lines.map(s=>ctx.measureText(s).width))+2*pad,th=sp*lines.length+2*pad-(sp-fh);
 const bx=it.align==='sol'?R.l-pad:it.align==='sag'?R.r+pad-tw:(R.l+R.r)/2-tw/2;
 const by=th<=R.h+2*pad?(R.t+R.b)/2-th/2:(it.anchor==='alt'?R.b+pad-th:R.t-pad);
 const cl=Math.min(bx,R.l-pad),ct=Math.min(by,R.t-pad),cr=Math.max(bx+tw,R.r+pad),cb=Math.max(by+th,R.b+pad);
 ctx.fillStyle='rgba(0,0,0,'+((it.box_opacity??255)/255)+')';rrect(cl,ct,cr-cl,cb-ct,pad*0.8);
 ctx.lineJoin='round';ctx.lineWidth=Math.max(2,line*0.10);ctx.strokeStyle='#000';ctx.fillStyle='#fff';
 let y=by+pad+asc;for(const s of lines){const w=ctx.measureText(s).width;
  const x=it.align==='sol'?bx+pad:it.align==='sag'?bx+tw-pad-w:bx+tw/2-w/2;ctx.strokeText(s,x,y);ctx.fillText(s,x,y);y+=sp}}
function draw(){ctx.clearRect(0,0,innerWidth,innerHeight);for(const k in items)item(items[k],innerWidth,innerHeight)}
function go(){const es=new EventSource('/olaylar');
 es.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='show')items[d.zone]=d;else delete items[d.zone];draw()};
 es.onerror=()=>{es.close();for(const k in items)delete items[k];draw();setTimeout(go,1000)}}
addEventListener('resize',size);size();go();
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
