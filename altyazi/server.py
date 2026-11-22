"""Yerel web sunucusu: OBS tarayıcı kaynağı veya TV/telefon tarayıcısı için canlı altyazı.

http://localhost:8787/        -> siyah zeminde altyazı (TV/telefon için)
http://localhost:8787/obs     -> saydam zeminde altyazı (OBS tarayıcı kaynağı, 1920x1080, oyun görüntüsünün üstüne)
http://localhost:8787/kumanda -> telefondan "Ekranı çevir" / "Duraklat" düğmeleri + son altyazılar
http://localhost:8787/olaylar -> Server-Sent Events akışı (JSON)
http://localhost:8787/events  -> TV uygulamalarının akışı (CouchSubs TV protokolü: subtitle/clear/screen/region/style)
http://localhost:8787/hello   -> TV uygulaması bilgisayarı ağda bu yanıtla tanır

TV protokolü CouchSubs'tan (https://github.com/yorulmazsinan/couchsubs, AGPL-3.0, Sinan Yorulmaz) alınmıştır.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .pipeline import DisplayItem

log = logging.getLogger(__name__)

MAIN_ZONE = "altyazi"
PING_FRAME = ": ping\n\nevent: ping\ndata: {}\n\n"


def _box(rect) -> dict:  # noqa: ANN001
    x0, y0, x1, y1 = (max(0.0, min(1.0, float(v))) for v in rect)
    return {"left": round(x0, 4), "top": round(y0, 4), "right": round(x1, 4), "bottom": round(y1, 4)}


def frame(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"

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


REMOTE = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>GTA6 Altyazı Kumanda</title>
<meta name="theme-color" content="#0d0b14">
<style>
:root{--bg:#0d0b14;--card:#17131f;--line:#2a2335;--txt:#f4f1fa;--mut:#9a90ad;--a1:#ff4fa3;--a2:#ff9f43}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,"Segoe UI",Roboto,sans-serif;
 padding:16px;max-width:640px;margin:auto}
h1{font-size:18px;margin:4px 0 14px;display:flex;align-items:center;gap:8px}
h1 b{background:linear-gradient(90deg,var(--a1),var(--a2));-webkit-background-clip:text;color:transparent}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
button{border:0;border-radius:18px;padding:22px 10px;font-size:17px;font-weight:700;color:#fff;cursor:pointer;
 background:var(--card);border:1px solid var(--line);transition:transform .08s}
button:active{transform:scale(.97)}
#fs{background:linear-gradient(135deg,var(--a1),var(--a2));border:0}
#go.on{background:#1f3b2e;border-color:#2f6b4f}
.state{display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:14px;
 padding:10px 14px;margin-bottom:12px;font-weight:600}.state i{width:10px;height:10px;border-radius:50%;background:#6c6380}
.state.on i{background:#3ddc97;box-shadow:0 0 10px #3ddc97}.row+.row{margin-top:12px}
#st{color:var(--mut);font-size:13px;min-height:18px;margin:10px 2px}
.sub{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin-top:10px}
.sub .tr{font-size:20px;font-weight:600;line-height:1.35}.sub .en{color:var(--mut);font-size:13px;margin-top:6px}
.sub .z{font-size:11px;color:var(--a2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
</style></head><body>
<h1>🎮 <b>GTA6 Altyazı</b> kumanda</h1>
<div class="state" id="state"><i></i><span id="stxt">Bağlanıyor...</span></div>
<div class="row"><button id="go">▶ Çeviriyi başlat</button><button id="cn">🎮 PS5'e bağlan</button></div>
<div class="row"><button id="fs">📖 Ekranı çevir</button><button id="pz">⏸ Duraklat</button></div>
<div id="st">Bağlanıyor...</div><div id="list"></div>
<script>
const st=document.getElementById('st'),list=document.getElementById('list'),subs={};
async function cmd(n){st.textContent='Gönderildi...';try{const r=await fetch('/komut/'+n,{method:'POST'});
 const j=await r.json();st.textContent=j.mesaj||'Tamam';if(n==='duraklat')pz.textContent=j.duraklatildi?'▶ Devam':'⏸ Duraklat'}
 catch(e){st.textContent='Bilgisayara ulaşılamadı'}}
fs.onclick=()=>cmd('tam_ekran');pz.onclick=()=>cmd('duraklat');go.onclick=()=>cmd('baslat_durdur');cn.onclick=()=>cmd('baglan');
function showState(s){const on=s==='calisiyor';document.getElementById('state').classList.toggle('on',on);go.classList.toggle('on',on);
 stxt.textContent={calisiyor:'Çeviri açık',hazir:'Çeviri kapalı',hazirlaniyor:'Uygulama hazırlanıyor',hata:'Bir sorun var'}[s]||s;
 go.textContent=on?'⏹ Çeviriyi durdur':'▶ Çeviriyi başlat'}
fetch('/komut/durum',{method:'POST'}).then(r=>r.json()).then(j=>showState(j.durum)).catch(()=>{});
function render(){list.innerHTML='';Object.values(subs).sort((a,b)=>b.t-a.t).slice(0,6).forEach(d=>{
 const e=document.createElement('div');e.className='sub';const z=document.createElement('div');z.className='z';
 z.textContent=d.zone.startsWith('tam')?'ekran':d.zone;const tr=document.createElement('div');tr.className='tr';tr.textContent=d.text;
 const en=document.createElement('div');en.className='en';en.textContent=d.english||'';e.append(z,tr,en);list.appendChild(e)})}
function go(){const es=new EventSource('/olaylar');es.onopen=()=>{st.textContent='Bağlı'};
 es.onmessage=m=>{const d=JSON.parse(m.data);if(d.type==='show'){d.t=Date.now();subs[d.zone]=d}
  else if(d.type==='notice'){st.textContent=d.mesaj}else if(d.type==='durum'){showState(d.durum)}else delete subs[d.zone];render()};
 es.onerror=()=>{st.textContent='Bağlantı koptu, tekrar deneniyor...';es.close();setTimeout(go,1500)}}
go();
</script></body></html>"""


def _revision(prev: str, cur: str) -> bool:
    """Aynı cümlenin düzelen okuması mı? (CouchSubs IsRevision: biri ötekinin başı ya da çok benzer)"""
    a, b = (prev or "").strip().lower(), (cur or "").strip().lower()
    if not a or not b:
        return False
    if a.startswith(b) or b.startswith(a):
        return True
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b) >= 85
    except ImportError:
        return False


class EventServer:
    def __init__(self, port: int, tv_calibration: list[float] | None = None, on_command=None):  # noqa: ANN001
        self.port = port
        self.on_command = on_command   # on_command(ad) -> dict (kumanda sayfasındaki düğmeler)
        x, y, w, h = tv_calibration or [0.0, 0.0, 1.0, 1.0]
        self.tv = {"x": x, "y": y, "w": w, "h": h}
        self.clients: list[queue.Queue] = []
        self.lock = threading.RLock()     # TV durumu birden çok iş parçacığından değişir; gönderim de aynı kilitle
        self.screen_ms = 20000            # "Ekranı çevir" kaç ms kalsın (ayar: kisayol.tam_ekran_sure)
        self._sub_english = ""
        self.state: dict[str, dict] = {}
        # TV uygulamaları (CouchSubs protokolü)
        self.tv_clients: list[queue.Queue] = []
        self.tv_style = {"placement": "cover", "fontSize": 58, "lineScale": 1.3, "background": 100, "bold": True,
                         "textColor": "white", "stackPrevious": True, "bottomPercent": 7, "backgroundShape": "fit",
                         "displayMode": "inApp"}
        self._screen: dict[str, dict] = {}
        self._overlay: list[dict] = []   # telefon, harita kartı, mesaj kartı (sahne/izleyici.py); altyazıyı silmez
        self._sub_seq = -1
        self._tv_state: dict[str, str] = {}      # yeni bağlanan TV'ye gönderilecek son çerçeveler
        self.tv_version: str | None = None       # TV uygulamasının bildirdiği sürüm

    # Sink arayüzü
    def show(self, it: DisplayItem) -> None:
        msg = {"type": "show", "zone": it.zone, "text": it.text, "english": it.english, "rect": it.rect,
               "zone_rect": it.zone_rect, "line_h": it.line_h, "align": it.align, "anchor": it.anchor,
               "box_opacity": it.box_opacity, "font_scale": it.font_scale, "tv": self.tv,
               "source": it.source, "latency_ms": round(it.latency_ms)}
        self.state[it.zone] = msg
        self._broadcast(msg)
        self._tv_show(it)

    def clear(self, zone: str) -> None:
        self.state.pop(zone, None)
        self._broadcast({"type": "clear", "zone": zone})
        self._tv_clear(zone)

    # ------------------------------------------------------------------ TV protokolü
    def set_tv_style(self, **kw) -> None:  # noqa: ANN003
        self.tv_style.update({k: v for k, v in kw.items() if v is not None})
        self._tv_send(frame("style", self.tv_style))

    def _tv_show(self, it: DisplayItem) -> None:
        if not it.text:
            return
        with self.lock:
            self._tv_show_locked(it)

    def _tv_show_locked(self, it: DisplayItem) -> None:
        if it.zone == MAIN_ZONE:
            # Süre uzun: yazı ekrandayken TV'de kaybolmasın; kaldırmayı 'clear' yapar (bağlantı koparsa TV 6 sn'de siler)
            data = {"at": int(time.time() * 1000), "duration": 3600000, "text": it.text, "box": _box(it.rect),
                    "line": round(it.line_h, 4)}
            if it.seq == self._sub_seq or _revision(self._sub_english, it.english):
                data["replace"] = True           # aynı satırın daha iyi çevirisi ya da düzelen okuması: yığılmasın
            self._sub_seq = it.seq
            self._sub_english = it.english or ""
            f = frame("subtitle", data)
            self._tv_state[MAIN_ZONE] = f
        elif it.zone.startswith("tam"):
            self._screen[it.zone] = {"box": _box(it.rect), "line": round(it.line_h, 4), "text": it.text}
            self._send_screen_locked()
            return
        else:
            data = {"id": it.zone, "text": it.text, "box": _box(it.rect), "line": round(it.line_h, 4)}
            if it.zone.startswith(MAIN_ZONE + "."):   # altyazı alanından ayrılan paragraf: altyazı gibi büyük ve örten
                data["main"] = True
            f = frame("region", data)
            self._tv_state[it.zone] = f
        self._tv_send(f)

    def _tv_clear(self, zone: str) -> None:
        with self.lock:
            self._tv_clear_locked(zone)

    def _tv_clear_locked(self, zone: str) -> None:
        if zone == MAIN_ZONE:
            self._sub_english = ""
            self._tv_state.pop(MAIN_ZONE, None)
            self._tv_send(frame("clear", {}))
        elif zone.startswith("tam"):
            if self._screen.pop(zone, None) is not None and not self._screen:
                self._send_screen_locked()
        else:
            if self._tv_state.pop(zone, None) is not None:
                self._tv_send(frame("region", {"id": zone, "text": ""}))

    def set_overlay(self, items: list[dict]) -> None:
        """Ekran yazılarının Türkçeleri (ScreenItem.to_json listesi); boş liste kaldırır."""
        with self.lock:
            if items == self._overlay:
                return
            self._overlay = list(items)
            self._send_screen_locked()
        self._broadcast({"type": "overlay", "items": items})

    def _send_screen_locked(self) -> None:
        """'Ekranı çevir' sonuçları ve ekran yazıları tek 'screen' olayında (TV öncekinin yerine bunları koyar)."""
        shots = [self._screen[k] for k in sorted(self._screen)]
        if shots:
            f = frame("screen", {"duration": self.screen_ms, "items": shots + self._overlay})
        elif self._overlay:
            f = frame("screen", {"duration": 120000, "items": self._overlay, "overlay": True})
        else:
            self._tv_state.pop("tam", None)
            self._tv_send(frame("screen-clear", {}))
            return
        self._tv_state["tam"] = f
        self._tv_send(f)

    def _tv_send(self, f: str) -> None:
        with self.lock:
            for q in self.tv_clients:
                q.put(f)

    @property
    def tv_count(self) -> int:
        return len(self.tv_clients)

    def notice(self, text: str) -> None:
        self._broadcast({"type": "notice", "mesaj": text})

    def status(self, state: str) -> None:
        self._broadcast({"type": "durum", "durum": state})

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

            def end_headers(self):  # noqa: N802
                # LG / Samsung TV uygulaması başka bir adresten (kendi paketinden) bağlanır
                self.send_header("Access-Control-Allow-Origin", "*")
                super().end_headers()

            def do_OPTIONS(self):  # noqa: N802
                self.send_response(204)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                # Yeni TV tarayıcıları (Tizen 9+) yerel ağdaki adrese bağlanmadan önce bunu sorar (CouchSubs gibi)
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Access-Control-Max-Age", "600")
                self.end_headers()

            def _json(self, code: int, obj: dict) -> None:
                body = json.dumps(obj, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):  # noqa: N802
                path = self.path.split("?")[0]
                if path.startswith("/komut/") and srv.on_command:
                    try:
                        self._json(200, srv.on_command(path[len("/komut/"):]) or {})
                    except Exception as e:  # noqa: BLE001
                        self._json(500, {"mesaj": f"Hata: {e}"})
                else:
                    self.send_error(404)

            def _tv_stream(self) -> None:
                self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try:   # fişten çekilen / Wi-Fi'ı kopan TV'yi çabuk fark et (Windows'ta varsayılan 2 saat)
                    self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                        self.connection.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 5000))
                    self.connection.settimeout(30)      # yazma takılırsa (TV kapandı) iş parçacığı serbest kalsın
                except (OSError, AttributeError):
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                q: queue.Queue = queue.Queue()
                with srv.lock:      # anlık durum ve listeye ekleme birlikte: arada gönderilen çerçeve kaybolmasın
                    q.put("retry: 2000\n\n" + frame("style", srv.tv_style))
                    # Kısa kopmada TV eski yazıları tutar: önce temizle, sonra şu an ekranda olanı gönder
                    q.put(frame("clear", {}) + frame("region-clear", {}) + frame("screen-clear", {}))
                    for f in list(srv._tv_state.values()):
                        q.put(f)
                    srv.tv_clients.append(q)
                log.info("TV bağlandı: %s", self.client_address[0])
                try:
                    while True:
                        try:
                            data = q.get(timeout=15)
                        except queue.Empty:
                            data = PING_FRAME      # TV 45 sn ping almazsa bağlantıyı yeniden kurar
                        self.wfile.write(data.encode("utf-8"))
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with srv.lock:
                        srv.tv_clients.remove(q)
                    log.info("TV ayrıldı: %s", self.client_address[0])

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                if path in ("/kim", "/hello"):   # TV uygulaması kasayı ağda bu adresle bulur
                    self._json(200, {"app": "gta6altyazi", "pid": os.getpid()})
                    return
                if path == "/events":
                    from urllib.parse import parse_qs, urlparse
                    v = (parse_qs(urlparse(self.path).query).get("v") or [""])[0][:20]
                    if v:
                        srv.tv_version = v           # Sistem sağlığı: TV uygulamasının sürümü
                    self._tv_stream()
                    return
                if path in ("/kumanda", "/ekran"):
                    body = REMOTE.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif path in ("/", "/obs"):
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

        class Server(ThreadingHTTPServer):
            # Windows'ta SO_REUSEADDR başka bir programın (ikinci kopya, CouchSubs) aynı portu sessizce paylaşmasına
            # izin verir; TV yanlış programa bağlanabilir. Port doluysa açıkça hata verilsin.
            allow_reuse_address = sys.platform != "win32"

            def server_bind(self):  # noqa: ANN202
                # SO_EXCLUSIVEADDRUSE kullanılmıyor: o seçenekle program kapandıktan sonra TV'nin eski bağlantısı
                # bitene kadar (birkaç dakika) port yeniden açılamıyordu ("port 8787 başka bir programda").
                # HTTPServer.server_bind bilgisayarın adını ters DNS ile sorar (socket.getfqdn); macOS'ta bazı ağlarda
                # bu 70 sn'ye kadar bekletiyordu (Mac denemesinde görüldü). Ada gerek yok: doğrudan bağla.
                import socketserver
                socketserver.TCPServer.server_bind(self)
                self.server_name, self.server_port = "localhost", self.server_address[1]

        httpd = Server(("0.0.0.0", self.port), H)
        httpd.daemon_threads = True
        threading.Thread(target=httpd.serve_forever, daemon=True, name="sunucu").start()
        log.info("Web: http://localhost:%d/  (OBS için /obs)", self.port)
