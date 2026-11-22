"""Yerel web sunucusu: OBS tarayıcı kaynağı veya TV/telefon tarayıcısı için canlı altyazı.

http://localhost:8787/        -> siyah zeminde altyazı (TV/telefon için)
http://localhost:8787/obs     -> saydam zeminde altyazı (OBS tarayıcı kaynağı, 1920x1080, oyun görüntüsünün üstüne)
http://localhost:8787/kumanda -> telefon kumandası: başlat/durdur (düğme ya da fiş), "Ekranı çevir", son altyazılar
http://localhost:8787/marka/   -> kumanda sayfasının görselleri (altyazi/ui/marka)
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
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .pipeline import DisplayItem

log = logging.getLogger(__name__)

MAIN_ZONE = "altyazi"
PING_FRAME = ": ping\n\nevent: ping\ndata: {}\n\n"
# Telefon kumandasının görselleri (/marka/simge.png, /marka/sahne.json ...); PyInstaller paketinde de aynı yerde
MARKA_DIR = Path(__file__).parent / "ui" / "marka"
_MARKA_NAME = re.compile(r"[a-z0-9_]+\.(png|json)")
_MARKA_TYPES = {"png": "image/png", "json": "application/json; charset=utf-8"}


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
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover"><title>GTA6 Altyazı</title>
<meta name="theme-color" content="#eaf2fc">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="GTA6 Altyazı">
<link rel="apple-touch-icon" href="/marka/simge.png"><link rel="icon" href="/marka/simge_yazisiz.png">
<style>
:root{--bg1:#eaf2fc;--bg2:#f5f8fd;--card:#fff;--ink:#0f1b33;--mut:#6b7891;--line:#e2e9f4;--blue:#1769e8;--blue2:#0b4fc4;
 --pale:#e9f1fe;--green:#1fbf6a;--amber:#f2a516;--red:#ff4a57;--red2:#d0101f;--r:26px;
 --sh:0 1px 2px rgba(15,27,51,.04),0 8px 24px rgba(23,66,140,.07);color-scheme:light}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
[hidden]{display:none!important}
html{background:var(--bg2)}
body{margin:0;min-height:100vh;color:var(--ink);background:linear-gradient(180deg,var(--bg1) 0,var(--bg2) 420px) no-repeat,var(--bg2);
 font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 -webkit-font-smoothing:antialiased;-webkit-text-size-adjust:100%;overflow-x:hidden}
body.noscroll{overflow:hidden}
button{font:inherit;color:inherit;border:0;background:none;padding:0;cursor:pointer}
.ic{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;flex:none}
.ic.fill{fill:currentColor;stroke:none}
main{max-width:520px;margin:0 auto;padding:calc(10px + env(safe-area-inset-top)) 20px calc(120px + env(safe-area-inset-bottom))}
body.run main,body.fis main{padding-bottom:calc(32px + env(safe-area-inset-bottom))}

/* üst çubuk */
.top{display:flex;align-items:center;gap:10px;height:56px}
.logo{width:44px;height:44px;border-radius:13px;overflow:hidden;flex:none;box-shadow:0 4px 12px rgba(23,105,232,.25);position:relative;
 background:linear-gradient(145deg,#2f86ff,#0b4fc4)}
.logo img{width:100%;height:100%;display:block}
.fb{display:none;position:absolute;left:0;top:0;right:0;bottom:0;align-items:center;justify-content:center;color:#fff}
.noimg img{display:none!important}.noimg .fb{display:flex}
.sp{flex:1}
.ib{width:44px;height:44px;border-radius:50%;background:var(--card);display:flex;align-items:center;justify-content:center;
 box-shadow:var(--sh);color:var(--ink);transition:transform .12s}
.ib:active{transform:scale(.92)}
.ib .ic{width:21px;height:21px}
.conn{display:none;align-items:center;gap:6px;font-size:12.5px;font-weight:600;color:#b4232f;background:#ffe8ea;
 padding:6px 10px;border-radius:99px}
.conn i{width:7px;height:7px;border-radius:50%;background:#e5343f}
body.off .conn{display:flex}

/* başlık */
.hero{padding:18px 2px 18px}
.hero h1{margin:0;font-size:40px;line-height:1.05;letter-spacing:-.025em;font-weight:800}
.hero p{margin:8px 0 0;font-size:16px;line-height:1.4;color:var(--mut)}
body.run .hero{padding:10px 2px 14px}
body.run .hero h1{font-size:30px}

/* kartlar */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{background:var(--card);border-radius:var(--r);box-shadow:var(--sh);padding:16px 16px 15px;min-width:0;text-align:left;
 display:flex;flex-direction:column;align-items:flex-start;position:relative;transition:transform .12s}
button.card:active{transform:scale(.97)}
.ci{width:42px;height:42px;border-radius:14px;background:var(--pale);color:var(--blue);display:flex;align-items:center;justify-content:center;
 margin-bottom:14px}
.card small{font-size:13px;color:var(--mut);font-weight:500}
.card b{font-size:18px;font-weight:700;margin-top:2px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;letter-spacing:-.01em}
.card em{font-style:normal;font-size:12.5px;color:var(--mut);margin-top:6px;display:flex;align-items:center;gap:6px;max-width:100%;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dot{width:8px;height:8px;border-radius:50%;background:#c3cbd8;flex:none}
.dot.g{background:var(--green);box-shadow:0 0 0 3px rgba(31,191,106,.15)}
.dot.a{background:var(--amber);box-shadow:0 0 0 3px rgba(242,165,22,.15)}
.card.wide{grid-column:1/-1;flex-direction:row;align-items:center;gap:14px;padding:16px}
.card.wide .ci{margin:0}
.card.wide .tx{flex:1;min-width:0}
.card.wide b{display:block;white-space:normal;font-size:16.5px;line-height:1.25}
.card.wide em{margin-top:4px}
.pill{font-size:12.5px;font-weight:700;color:var(--blue);background:var(--pale);padding:6px 11px;border-radius:99px;flex:none}
.chev{color:#a7b2c4;width:18px;height:18px}

/* alttaki ana düğme */
.dock{position:fixed;left:0;right:0;bottom:0;z-index:5;padding:14px 20px calc(14px + env(safe-area-inset-bottom));
 background:linear-gradient(to top,var(--bg2) 62%,rgba(245,248,253,0))}
.dock .cta{max-width:480px;margin:0 auto}
body.run .dock,body.fis .dock{display:none}
.cta{display:flex;width:100%;align-items:center;justify-content:center;gap:10px;height:60px;border-radius:20px;color:#fff;
 font-size:17.5px;font-weight:700;letter-spacing:-.005em;background:linear-gradient(180deg,var(--blue),var(--blue2));
 box-shadow:0 10px 24px rgba(11,79,196,.32),inset 0 1px 0 rgba(255,255,255,.25);transition:transform .12s,opacity .2s}
.cta:active{transform:scale(.98)}
.cta:disabled{opacity:.5;box-shadow:none}
.cta .ic{width:18px;height:18px}

/* canlı TV önizlemesi */
.tv{position:relative;border-radius:var(--r);overflow:hidden;min-height:200px;padding:16px 18px 22px;display:flex;flex-direction:column;
 justify-content:flex-end;color:#fff;background:radial-gradient(120% 90% at 80% 0%,rgba(120,80,200,.35),transparent 60%),
 linear-gradient(150deg,#1b1f3b,#2a1a2e);box-shadow:0 14px 34px rgba(27,31,59,.28)}
.tv:after{content:"";position:absolute;left:0;right:0;top:0;height:50%;background:linear-gradient(180deg,rgba(255,255,255,.06),transparent);pointer-events:none}
.badge{position:absolute;left:14px;top:14px;display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:800;letter-spacing:.08em;
 color:#fff;background:rgba(0,0,0,.42);padding:6px 10px 6px 9px;border-radius:99px;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
.badge i{width:7px;height:7px;border-radius:50%;background:#ff3b47;box-shadow:0 0 8px #ff3b47;animation:blink 1.6s infinite}
body.paused .badge i{background:var(--amber);box-shadow:none;animation:none}
@keyframes blink{50%{opacity:.35}}
.tvtr{margin:0;text-align:center;font-size:22px;line-height:1.3;font-weight:800;letter-spacing:-.01em;text-shadow:0 2px 10px rgba(0,0,0,.5);
 transition:opacity .3s}
.tvtr.old{opacity:.5}
.tvwait{text-align:center;color:rgba(255,255,255,.55);font-size:15px;font-weight:600;padding-bottom:6px}
.tven{margin:10px 6px 0;text-align:center;font-size:13.5px;font-style:italic;color:#8792a6;line-height:1.35;min-height:18px}

/* kaydırmalı düğme */
.slide{--p:1;position:relative;height:84px;border-radius:42px;margin:18px 0 0;background:#fff;border:1px solid var(--line);
 box-shadow:var(--sh);touch-action:none;user-select:none;-webkit-user-select:none;cursor:pointer;outline:none}
.slide:focus-visible{box-shadow:0 0 0 3px rgba(23,105,232,.35)}
.slide .fill{position:absolute;left:-1px;top:-1px;right:-1px;bottom:-1px;border-radius:42px;opacity:var(--p);
 background:linear-gradient(180deg,#ff5c68 0%,var(--red) 35%,var(--red2) 100%);
 box-shadow:0 14px 30px rgba(230,24,40,.38),inset 0 1px 0 rgba(255,255,255,.45),inset 0 -6px 14px rgba(120,0,10,.25)}
.slide .fill:after{content:"";position:absolute;left:18px;right:18px;top:3px;height:42%;border-radius:40px 40px 20px 20px;
 background:linear-gradient(180deg,rgba(255,255,255,.38),rgba(255,255,255,0))}
.slide .t{position:absolute;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;pointer-events:none}
.slide .t b{font-size:23px;font-weight:800;letter-spacing:-.015em;line-height:1.1}
.slide .t span{font-size:13.5px;font-weight:600;margin-top:2px}
.slide .on{left:28px;color:#fff;opacity:calc(var(--p)*2 - 1)}
.slide .on span{color:rgba(255,255,255,.85)}
.slide .offt{right:28px;text-align:right;opacity:calc(1 - var(--p)*2)}
.slide .offt span{color:var(--mut)}
.knob{position:absolute;left:6px;top:5px;width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 background:radial-gradient(circle at 32% 24%,rgba(255,255,255,.95),rgba(255,255,255,.55) 45%,rgba(255,255,255,.28));
 border:1px solid rgba(255,255,255,.8);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);
 box-shadow:0 8px 18px rgba(80,0,10,.25),inset 0 1px 1px #fff,inset 0 -3px 6px rgba(0,0,0,.06);
 transition:transform .38s cubic-bezier(.3,1.3,.5,1)}
.slide.drag .knob{transition:none}
.knob img,.knob .rz{width:54px;height:54px;border-radius:50%;display:block}
.knob .rz{display:none}
.knob.noimg .rz{display:block!important}
.slide .hint{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:2px;opacity:calc(1 - var(--p));color:#c3cbd8;pointer-events:none}
.slide.busy{cursor:progress}

/* bilgi çipleri */
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.chip{display:flex;align-items:center;gap:6px;background:#fff;border:1px solid var(--line);border-radius:99px;padding:7px 12px 7px 9px;
 font-size:13px;color:var(--mut);white-space:nowrap;max-width:100%}
.chip .ic{width:16px;height:16px;color:var(--blue)}
.chip b{color:var(--ink);font-weight:700;overflow:hidden;text-overflow:ellipsis}

/* son çeviriler */
.sec-h{display:flex;align-items:baseline;justify-content:space-between;margin:26px 4px 10px}
.sec-h h2{margin:0;font-size:19px;font-weight:800;letter-spacing:-.01em}
.link{color:var(--blue);font-weight:600;font-size:15px}
.sub{background:#fff;border-radius:20px;box-shadow:var(--sh);padding:14px 16px;margin-bottom:10px}
.sub .tr{font-size:16.5px;font-weight:700;line-height:1.35}
.sub .en{color:var(--mut);font-size:13.5px;margin-top:4px;line-height:1.35}
.sub .z{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.07em;color:var(--blue);background:var(--pale);
 border-radius:6px;padding:2px 6px;margin-bottom:6px}
.empty{color:var(--mut);font-size:14.5px;text-align:center;padding:22px 10px;background:rgba(255,255,255,.6);border-radius:20px;
 border:1px dashed #d3dceb}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
.sec{display:flex;align-items:center;justify-content:center;gap:8px;height:54px;border-radius:18px;background:#fff;box-shadow:var(--sh);
 font-size:16px;font-weight:700;color:var(--ink);transition:transform .12s}
.sec:active{transform:scale(.97)}
.sec .ic{width:19px;height:19px;color:var(--blue)}

/* görünüm seçimi: hangi bölüm ne zaman */
#liveBox,#slider,#chips,#recent,#actions{display:none}
body.run #liveBox,body.run #chips,body.run #recent{display:block}
body.run #chips{display:flex}
body.run #actions{display:grid}
body.run #slider{display:block}
body.fis #liveBox,body.fis #slider{display:none!important}
body.run #cards{display:none}
#sceneBox{display:none}
body.fis #sceneBox{display:block}
body.fis #cards{margin-top:18px}

/* fiş sahnesi */
.scene-wrap{margin:0 -20px}
.scene{position:relative;width:100%;height:0;padding-top:56.25%;user-select:none;-webkit-user-select:none}
.scene>*{position:absolute}
.scene .simg{left:0;top:0;width:100%;height:100%;z-index:2;pointer-events:none;-webkit-user-drag:none}
.scene .cable{left:0;top:0;width:100%;height:100%;z-index:1;pointer-events:none;overflow:visible}
.glow{z-index:0;border-radius:8%;opacity:0;transition:opacity .6s;pointer-events:none;
 background:linear-gradient(135deg,#3d8bff,#2c5cff 60%,#7a5cff);
 -webkit-filter:blur(22px);filter:blur(22px);-webkit-transform:scale(1.08,1.14);transform:scale(1.08,1.14)}
body.run .glow{opacity:1}
body.paused .glow{opacity:.35}
.screen{z-index:3;overflow:hidden;border-radius:3px;color:#fff;font-size:10px;
 background:linear-gradient(180deg,rgba(6,14,44,.35),rgba(6,14,44,.6))}
.screen>div{position:absolute;left:0;top:0;right:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
 text-align:center;transition:opacity .4s}
.scr-idle img{width:3.2em;height:3.2em;border-radius:.8em;margin-bottom:.45em;box-shadow:0 .3em .9em rgba(0,0,0,.35)}
.scr-idle b{font-size:1.45em;font-weight:800;letter-spacing:-.01em}
.scr-idle span{font-size:.95em;opacity:.75;margin-top:.15em}
.scr-live{background:linear-gradient(150deg,#1b1f3b,#2a1a2e);justify-content:flex-end!important;padding:0 .8em 1em;opacity:0}
.scr-live .badge{left:.7em;top:.7em;font-size:.72em;padding:.35em .7em .35em .6em}
.scr-live p{margin:0;padding:.25em .4em;font-size:1.25em;font-weight:800;line-height:1.25;text-shadow:0 .1em .4em rgba(0,0,0,.6);
 display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.scr-live p.old{opacity:.5}
body.run .scr-live{opacity:1}
body.run .scr-idle{opacity:0}
.sock{z-index:3;border-radius:22%;pointer-events:none}
.sock:before{content:"";position:absolute;left:-18%;top:-18%;right:-18%;bottom:-18%;border-radius:50%;border:2px dashed rgba(23,105,232,.6);
 animation:pulse 1.8s ease-in-out infinite}
.sock.near:before{border-style:solid;border-color:var(--green);background:rgba(31,191,106,.15)}
body.run .sock:before,.scene.plugged .sock:before{display:none}
@keyframes pulse{50%{transform:scale(1.15);opacity:.45}}
.plug{z-index:4;touch-action:none;cursor:grab}
.plug:before{content:"";position:absolute;left:-22px;top:-22px;right:-22px;bottom:-22px}
.plug svg{width:100%;height:100%;display:block;overflow:visible;filter:drop-shadow(0 3px 4px rgba(0,0,0,.35))}
.plug.grab{cursor:grabbing}
.scene.plugged .pins{display:none}
.caption{text-align:center;margin:10px 0 0;font-size:16px;font-weight:700}
.caption small{display:block;font-size:13px;color:var(--mut);font-weight:500;margin-top:3px}

/* bildirim */
.toast{position:fixed;left:50%;top:calc(12px + env(safe-area-inset-top));z-index:60;transform:translate(-50%,-140%);max-width:calc(100% - 32px);
 background:rgba(15,27,51,.92);color:#fff;font-size:14.5px;font-weight:600;padding:11px 16px;border-radius:16px;
 box-shadow:0 10px 30px rgba(15,27,51,.25);transition:transform .35s cubic-bezier(.3,1.2,.5,1),opacity .25s;text-align:center;pointer-events:none;opacity:0}
.toast.on{transform:translate(-50%,0);opacity:1}

/* alt sayfalar */
.sheet-bg{position:fixed;left:0;top:0;right:0;bottom:0;z-index:30;background:rgba(15,27,51,.35);opacity:0;pointer-events:none;transition:opacity .3s}
.sheet-bg.on{opacity:1;pointer-events:auto}
.sheet{position:fixed;left:0;right:0;bottom:0;z-index:31;max-width:560px;margin:0 auto;background:var(--bg2);border-radius:28px 28px 0 0;
 padding:8px 20px calc(22px + env(safe-area-inset-bottom));transform:translateY(105%);transition:transform .38s cubic-bezier(.25,1,.4,1);
 max-height:86vh;display:flex;flex-direction:column;box-shadow:0 -10px 40px rgba(15,27,51,.18);visibility:hidden;
 transition:transform .38s cubic-bezier(.25,1,.4,1),visibility 0s .38s}
.sheet.on{transform:translateY(0);visibility:visible;transition:transform .38s cubic-bezier(.25,1,.4,1)}
.grip{width:40px;height:5px;border-radius:3px;background:#cfd8e6;margin:4px auto 10px;flex:none}
.sh-h{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex:none}
.sh-h h3{margin:0;font-size:22px;font-weight:800;letter-spacing:-.015em}
.sh-h .ib{width:36px;height:36px;box-shadow:none;background:#e6edf7}
.sh-h .ib .ic{width:18px;height:18px}
.sh-body{overflow-y:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px 4px}
.lbl{font-size:13px;font-weight:700;color:var(--mut);letter-spacing:.02em;margin:4px 4px 8px}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#e3eaf5;border-radius:16px;padding:4px;margin-bottom:20px}
.seg button{display:flex;align-items:center;justify-content:center;gap:8px;height:46px;border-radius:12px;font-weight:700;font-size:15.5px;color:var(--mut)}
.seg button .ic{width:18px;height:18px}
.seg button.sel{background:#fff;color:var(--ink);box-shadow:0 2px 8px rgba(15,27,51,.1)}
.seg button.sel .ic{color:var(--blue)}
.list{background:#fff;border-radius:20px;box-shadow:var(--sh);overflow:hidden;margin-bottom:20px}
.li{display:flex;align-items:center;gap:12px;width:100%;padding:14px 14px;text-align:left;text-decoration:none;color:var(--ink);font-size:15.5px;font-weight:600}
.li+.li{border-top:1px solid #edf1f7}
.li .ci{width:36px;height:36px;border-radius:11px;margin:0}
.li .ci .ic{width:19px;height:19px}
.li .lt{flex:1;min-width:0}
.li .lt small{display:block;font-size:12.5px;color:var(--mut);font-weight:500;margin-top:1px}
.meta{display:flex;justify-content:space-between;font-size:14px;padding:12px 16px;color:var(--mut)}
.meta b{color:var(--ink);font-weight:600}
.meta+.meta{border-top:1px solid #edf1f7}
.hrow{padding:13px 16px}
.hrow+.hrow{border-top:1px solid #edf1f7}
.hrow .tr{font-weight:700;font-size:15.5px;line-height:1.35}
.hrow .en{color:var(--mut);font-size:13px;margin-top:3px;line-height:1.35}
.hrow .tm{font-size:11.5px;color:#9aa6b9;margin-top:5px;font-variant-numeric:tabular-nums}
.hrow .z{font-size:10.5px;font-weight:800;color:var(--blue);margin-right:6px;letter-spacing:.06em}

/* tanıtım */
.ob{position:fixed;left:0;top:0;right:0;bottom:0;z-index:50;display:flex;flex-direction:column;
 background:linear-gradient(180deg,var(--bg1),var(--bg2) 60%);transition:opacity .3s}
.ob.bye{opacity:0}
.ob-top{display:flex;justify-content:flex-end;padding:calc(12px + env(safe-area-inset-top)) 20px 0;height:calc(52px + env(safe-area-inset-top));flex:none}
.ob-top .link{padding:8px 4px;font-size:16px;color:var(--mut)}
.ob-view{flex:1;overflow:hidden;touch-action:pan-y;position:relative}
.ob-track{display:flex;height:100%;transition:transform .45s cubic-bezier(.25,1,.4,1)}
.ob-page{flex:0 0 100%;height:100%;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:0 24px 12px;display:flex;flex-direction:column;align-items:center;text-align:center}
.ob-page:before,.ob-page:after{content:"";flex:1 1 0;min-height:4px}
.ob-icon{width:150px;height:150px;border-radius:34px;position:relative;overflow:hidden;flex:none;
 box-shadow:0 18px 40px rgba(11,79,196,.28);background:linear-gradient(145deg,#2f86ff,#0b4fc4)}
.ob-icon img{width:100%;height:100%;display:block}
.ob-icon .fb .ic{width:64px;height:64px;stroke-width:1.6}
.ob-name{font-size:38px;font-weight:800;letter-spacing:-.03em;margin:20px 0 0;line-height:1.05}
.ob-kick{font-size:13px;font-weight:800;letter-spacing:.24em;color:var(--blue);margin-top:8px}
.demo{width:100%;max-width:360px;background:#fff;border-radius:var(--r);box-shadow:0 12px 32px rgba(23,66,140,.1);padding:18px 18px 16px;
 margin-top:22px;text-align:left}
.demo .en{color:#8a95a8;font-size:14px}
.demo .tr{font-size:20px;font-weight:800;margin-top:4px;letter-spacing:-.01em}
.demo .ft{display:flex;align-items:center;justify-content:space-between;margin-top:14px;padding-top:12px;border-top:1px solid #eef2f8;
 font-size:13.5px;font-weight:600}
.demo .ft span{display:flex;align-items:center;gap:7px}
.ob h2{font-size:25px;line-height:1.2;font-weight:800;letter-spacing:-.02em;margin:24px 0 0;max-width:340px}
.ob p.lead{font-size:15.5px;line-height:1.5;color:var(--mut);margin:10px 0 0;max-width:350px}
.ob-art{width:100%;max-width:360px}
.mini-slide{position:relative;height:72px;border-radius:36px;background:linear-gradient(180deg,#ff5c68,var(--red) 35%,var(--red2));
 box-shadow:0 12px 26px rgba(230,24,40,.35),inset 0 1px 0 rgba(255,255,255,.45);color:#fff;text-align:left;padding:14px 26px}
.mini-slide b{display:block;font-size:20px;font-weight:800;line-height:1.1}
.mini-slide span{font-size:12.5px;font-weight:600;opacity:.85}
.mini-slide .knob{width:60px;height:60px;left:auto;right:6px;top:6px;transition:none;animation:nudge 2.4s ease-in-out infinite}
.mini-slide .knob img,.mini-slide .knob .rz{width:44px;height:44px}
@keyframes nudge{0%,60%,100%{transform:none}75%{transform:translateX(-26px)}}
.or{display:flex;align-items:center;gap:12px;color:#9aa6b9;font-size:12.5px;font-weight:700;letter-spacing:.12em;margin:18px 6px}
.or:before,.or:after{content:"";flex:1;height:1px;background:#dbe3ef}
.mini-plug{display:flex;align-items:center;justify-content:center;gap:16px;background:#fff;border-radius:22px;box-shadow:var(--sh);padding:16px;
 font-weight:700;font-size:15px}
.mini-plug .ci{margin:0}
.ob-dots{display:flex;justify-content:center;gap:7px;margin-bottom:18px}
.ob-dots i{width:8px;height:8px;border-radius:4px;background:#c9d4e5;transition:width .3s,background .3s}
.ob-dots i.on{width:26px;background:var(--blue)}
.ob-foot{flex:none;padding:12px 24px calc(18px + env(safe-area-inset-bottom))}
.ob-foot .cta{max-width:480px;margin:0 auto}
@media (max-height:740px){.ob-icon{width:112px;height:112px;border-radius:28px}.ob-name{font-size:32px;margin-top:14px}.demo{margin-top:16px}
 .ob h2{margin-top:16px;font-size:22px}.hero h1{font-size:34px}}
@media (max-height:700px){.ob-icon{width:96px;height:96px;border-radius:24px}.ob-name{font-size:28px;margin-top:12px}.ob-kick{font-size:11.5px}
 .demo{margin-top:14px;padding:14px 16px 12px}.demo .tr{font-size:17px}.demo .ft{margin-top:10px;padding-top:10px}.ob h2{font-size:20px;margin-top:14px}
 .ob p.lead{font-size:14px;line-height:1.45}.ob-dots{margin-bottom:12px}.ob-foot .cta{height:54px}}
@media (max-width:380px){.card{padding:14px 14px 13px}.card.wide{padding:14px;gap:12px}.card.wide .chev{display:none}.card b{font-size:17px}
 .hero h1{font-size:36px}.slide .t b{font-size:21px}}
@media (min-width:600px){.scene-wrap{margin:0}}
@media (prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important;animation:none!important}}
</style></head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
<symbol id="i-clock" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></symbol>
<symbol id="i-gear" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></symbol>
<symbol id="i-pad" viewBox="0 0 24 24"><path d="M6 11h4M8 9v4M15 12h.01M18 10h.01"/><path d="M17.32 5H6.68a4 4 0 0 0-3.98 3.59C2.6 9.42 2 14.46 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.41-1.41A2 2 0 0 1 9.83 16h4.34a2 2 0 0 1 1.41.59L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.54-.6-6.58-.69-7.26A4 4 0 0 0 17.32 5z"/></symbol>
<symbol id="i-tv" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2.5"/><path d="M8 21h8M12 17v4"/></symbol>
<symbol id="i-globe" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></symbol>
<symbol id="i-zap" viewBox="0 0 24 24"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></symbol>
<symbol id="i-chev" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></symbol>
<symbol id="i-play" viewBox="0 0 24 24"><path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z"/></symbol>
<symbol id="i-pause" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></symbol>
<symbol id="i-scan" viewBox="0 0 24 24"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 9h10M7 13h10M7 17h5"/></symbol>
<symbol id="i-x" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></symbol>
<symbol id="i-plug" viewBox="0 0 24 24"><path d="M12 22v-5M9 8V2M15 8V2M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"/></symbol>
<symbol id="i-toggle" viewBox="0 0 24 24"><rect x="2" y="6" width="20" height="12" rx="6"/><circle cx="16" cy="12" r="3"/></symbol>
<symbol id="i-redo" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></symbol>
<symbol id="i-cast" viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2.5"/><path d="m17 2-5 5-5-5"/></symbol>
<symbol id="i-sub" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="3"/><path d="M6 14h4M14 14h4M6 10h8"/></symbol>
<symbol id="i-chev2" viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"/></symbol>
<symbol id="rozet" viewBox="0 0 54 54"><defs><radialGradient id="rg" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#ff6b75"/><stop offset="1" stop-color="#c50d1c"/></radialGradient></defs><circle cx="27" cy="27" r="27" fill="url(#rg)"/><circle cx="23" cy="27" r="12" fill="#fff"/><circle cx="26" cy="27" r="9.6" fill="#e01b2b"/><path fill="#fff" d="m36.5 21.8 1.5 4.1 4.3.1-3.4 2.6 1.2 4.2-3.6-2.5-3.6 2.5 1.2-4.2-3.4-2.6 4.3-.1z"/></symbol>
</svg>

<main id="app">
 <header class="top">
  <span class="logo"><img src="/marka/simge_yazisiz.png" alt="GTA6 Altyazı" onerror="this.parentNode.classList.add('noimg')"><span class="fb"><svg class="ic"><use href="#i-sub"/></svg></span></span>
  <span class="conn" id="conn"><i></i>Bağlantı yok</span>
  <span class="sp"></span>
  <button class="ib" id="bHist" aria-label="Son çeviriler"><svg class="ic"><use href="#i-clock"/></svg></button>
  <button class="ib" id="bSet" aria-label="Ayarlar"><svg class="ic"><use href="#i-gear"/></svg></button>
 </header>

 <section class="hero"><h1 id="hTitle">Bağlanıyor</h1><p id="hSub">Bilgisayardaki GTA6 Altyazı'ya bağlanılıyor...</p></section>

 <section id="liveBox">
  <div class="tv"><span class="badge"><i></i><span id="bdg">CANLI</span></span>
   <div class="tvwait" id="tvWait">Altyazı bekleniyor...</div><p class="tvtr" id="tvTr"></p></div>
  <p class="tven" id="tvEn"></p>
 </section>

 <section id="sceneBox">
  <div class="scene-wrap"><div class="scene" id="scene">
   <div class="glow" id="sGlow"></div>
   <svg class="cable" id="sCable" preserveAspectRatio="none"><path id="cab1" fill="none" stroke="#14161c" stroke-linecap="round"/><path id="cab2" fill="none" stroke="rgba(255,255,255,.18)" stroke-linecap="round"/></svg>
   <img class="simg" id="sImg" alt="" draggable="false">
   <div class="screen" id="sScreen">
    <div class="scr-idle"><img src="/marka/simge_yazisiz.png" alt="" onerror="this.style.display='none'"><b>GTA6 Altyazı</b><span>Oyunlarınız artık Türkçe</span></div>
    <div class="scr-live"><span class="badge"><i></i>CANLI</span><p id="sTr"></p></div>
   </div>
   <div class="sock" id="sSock"></div>
   <div class="plug" id="sPlug" role="button" tabindex="0" aria-label="Fiş">
    <svg viewBox="0 0 60 96" preserveAspectRatio="none"><defs><linearGradient id="pg" x1="0" x2="1"><stop offset="0" stop-color="#3a3d45"/><stop offset=".45" stop-color="#16181d"/><stop offset="1" stop-color="#050608"/></linearGradient><linearGradient id="pn" x1="0" x2="1"><stop offset="0" stop-color="#f4f6f9"/><stop offset="1" stop-color="#9aa3b0"/></linearGradient></defs>
     <g class="pins"><rect x="15" y="0" width="7" height="24" rx="3.5" fill="url(#pn)"/><rect x="38" y="0" width="7" height="24" rx="3.5" fill="url(#pn)"/></g>
     <rect x="3" y="18" width="54" height="58" rx="15" fill="url(#pg)"/><rect x="9" y="22" width="16" height="50" rx="8" fill="rgba(255,255,255,.08)"/>
     <path d="M14 52h32M14 59h32M14 66h32" stroke="rgba(255,255,255,.12)" stroke-width="2.5" stroke-linecap="round"/>
     <rect x="21" y="72" width="18" height="24" rx="6" fill="#111318"/></svg>
   </div>
  </div></div>
  <p class="caption" id="sCap">Fişi takın, çeviri başlasın</p>
  <p class="tven" id="sEn"></p>
 </section>

 <div id="slider" class="slide" role="switch" aria-checked="false" tabindex="0" aria-label="Türkçe altyazı">
  <div class="fill"></div>
  <span class="hint"><svg class="ic" style="width:18px;height:18px"><use href="#i-chev"/></svg><svg class="ic" style="width:18px;height:18px;opacity:.6"><use href="#i-chev"/></svg></span>
  <div class="t on"><b>Türkçe</b><span id="slOn">Altyazı açık</span></div>
  <div class="t offt"><b>Türkçe</b><span id="slOff">Altyazı kapalı</span></div>
  <div class="knob" id="knob"><img src="/marka/rozet.png" alt="" draggable="false" onerror="this.parentNode.classList.add('noimg')"><svg class="rz"><use href="#rozet"/></svg></div>
 </div>

 <div id="chips" class="chips">
  <span class="chip"><svg class="ic"><use href="#i-pad"/></svg>PS5 <b id="chPs5">PS5</b></span>
  <span class="chip"><svg class="ic"><use href="#i-tv"/></svg>Çıkış <b id="chOut">TV</b></span>
  <span class="chip"><svg class="ic"><use href="#i-zap"/></svg>Paketler <b id="chPack">Ücretsiz</b></span>
  <span class="chip"><svg class="ic"><use href="#i-globe"/></svg>Çeviri <b id="chEng">—</b></span>
 </div>

 <section id="cards" class="grid">
  <button class="card" id="cPs5" type="button"><span class="ci"><svg class="ic"><use href="#i-pad"/></svg></span><small>PS5</small><b id="cPs5N">PS5</b><em><i class="dot" id="cPs5D"></i><span id="cPs5S">Durum bilinmiyor</span></em></button>
  <div class="card"><span class="ci"><svg class="ic"><use href="#i-tv"/></svg></span><small>Altyazı</small><b id="cOutN">TV</b><em><i class="dot" id="cOutD"></i><span id="cOutS">TV'de gösterilir</span></em></div>
  <button class="card wide" id="cPack" type="button"><span class="ci"><svg class="ic"><use href="#i-zap"/></svg></span>
   <span class="tx"><b>Hazır paketlerle anında altyazı</b><em id="cPackS">Paketteki satırlar beklemeden gelir</em></span>
   <span class="pill">Ücretsiz</span><svg class="ic chev"><use href="#i-chev"/></svg></button>
  <div class="card"><span class="ci"><svg class="ic"><use href="#i-globe"/></svg></span><small>Çeviri</small><b id="cEngN">—</b><em id="cEngS">Çeviri motoru</em></div>
  <button class="card" id="cSess" type="button"><span class="ci"><svg class="ic"><use href="#i-clock"/></svg></span><small>Son oturum</small><b id="cSessN">—</b><em id="cSessS">Henüz oturum yok</em></button>
 </section>

 <section id="recent"><div class="sec-h"><h2>Son çeviriler</h2><button class="link" id="bAll" type="button">Tümü</button></div><div id="list"></div></section>
 <div class="row2" id="actions"><button class="sec" id="bFs" type="button"><svg class="ic"><use href="#i-scan"/></svg>Ekranı çevir</button>
  <button class="sec" id="bPz" type="button"><svg class="ic"><use id="pzIc" href="#i-pause"/></svg><span id="pzTx">Duraklat</span></button></div>
</main>

<div class="dock" id="dock"><button class="cta" id="bStart" type="button"><svg class="ic fill"><use href="#i-play"/></svg><span id="ctaTx">Çeviriyi başlat</span></button></div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<div class="sheet-bg" id="sheetBg"></div>
<section class="sheet" id="shSet" role="dialog" aria-label="Ayarlar">
 <div class="grip"></div>
 <div class="sh-h"><h3>Ayarlar</h3><button class="ib" data-close aria-label="Kapat"><svg class="ic"><use href="#i-x"/></svg></button></div>
 <div class="sh-body">
  <div class="lbl">Ana ekran</div>
  <div class="seg" id="seg"><button type="button" data-st="dugme"><svg class="ic"><use href="#i-toggle"/></svg>Düğme</button><button type="button" data-st="fis"><svg class="ic"><use href="#i-plug"/></svg>Fiş</button></div>
  <div class="list">
   <button class="li" id="bOb" type="button"><span class="ci"><svg class="ic"><use href="#i-redo"/></svg></span><span class="lt">Kurulum tanıtımını tekrar göster<small>Üç adımlık kısa tanıtım</small></span><svg class="ic chev"><use href="#i-chev"/></svg></button>
   <a class="li" href="/"><span class="ci"><svg class="ic"><use href="#i-cast"/></svg></span><span class="lt">TV görünümünü aç<small>Bu cihaz altyazı ekranı olsun</small></span><svg class="ic chev"><use href="#i-chev"/></svg></a>
  </div>
  <div class="lbl">Bilgi</div>
  <div class="list"><div class="meta">Sürüm<b id="mVer">—</b></div><div class="meta">Bağlantı<b id="mConn">—</b></div><div class="meta">Adres<b id="mAddr">—</b></div></div>
 </div>
</section>
<section class="sheet" id="shHist" role="dialog" aria-label="Son çeviriler">
 <div class="grip"></div>
 <div class="sh-h"><h3>Son çeviriler</h3><button class="ib" data-close aria-label="Kapat"><svg class="ic"><use href="#i-x"/></svg></button></div>
 <div class="sh-body" id="histBody"></div>
</section>

<div class="ob" id="ob" hidden>
 <div class="ob-top"><button class="link" id="obSkip" type="button">Geç</button></div>
 <div class="ob-view" id="obView"><div class="ob-track" id="obTrack">
  <section class="ob-page">
   <div class="ob-icon"><img src="/marka/simge.png" alt="" onerror="this.parentNode.classList.add('noimg')"><span class="fb"><svg class="ic"><use href="#i-sub"/></svg></span></div>
   <div class="ob-name">GTA6 Altyazı</div>
   <div class="ob-kick">TÜRKÇE ALTYAZI</div>
   <div class="demo"><div class="en">Are you listening to me?</div><div class="tr">Beni dinliyor musunuz?</div>
    <div class="ft"><span><i class="dot g"></i>PS5 bağlı</span><span class="pill">Hazır çeviri</span></div></div>
   <h2>PS5 oyunlarına Türkçe altyazı</h2>
   <p class="lead">Bilgisayarınız oyundaki İngilizce altyazıyı okur, çevirir ve TV'de gösterir. Bu telefon da kumanda olur: başlat, durdur, son çevirileri oku.</p>
  </section>
  <section class="ob-page">
   <div class="ob-art">
    <div class="mini-slide"><b>Türkçe</b><span>Altyazı açık</span><div class="knob"><img src="/marka/rozet.png" alt="" onerror="this.parentNode.classList.add('noimg')"><svg class="rz"><use href="#rozet"/></svg></div></div>
    <div class="or">YA DA</div>
    <div class="mini-plug"><span class="ci"><svg class="ic"><use href="#i-plug"/></svg></span>Fişi prize takın, çeviri başlasın</div>
   </div>
   <div class="ob-kick" style="margin-top:30px">KUMANDA</div>
   <h2 style="margin-top:8px">Kolu bırakmadan</h2>
   <p class="lead">Çeviriyi telefondan başlatın ve durdurun. Kırmızı düğmeyi kaydırın ya da Ayarlar'dan Fiş görünümünü seçip fişi prize takın. Duraklat ile altyazıyı bir süre gizleyin.</p>
  </section>
  <section class="ob-page">
   <div class="ob-art">
    <div class="sub" style="text-align:left"><div class="tr">Arabaya bin, hemen!</div><div class="en">Get in the car, now!</div></div>
    <div class="sub" style="text-align:left;opacity:.75"><div class="tr">Planı bir daha anlat.</div><div class="en">Run me through the plan again.</div></div>
    <div class="sec" style="margin-top:6px"><svg class="ic"><use href="#i-scan"/></svg>Ekranı çevir</div>
   </div>
   <div class="ob-kick" style="margin-top:30px">GEÇMİŞ</div>
   <h2 style="margin-top:8px">Son çeviriler burada</h2>
   <p class="lead">Kaçırdığınız cümleler telefonda kalır; saat simgesinden hepsine bakın. Oyundaki telefon, harita ya da menü için Ekranı çevir'e dokunun, ekrandaki yazılar Türkçe olsun.</p>
  </section>
 </div></div>
 <div class="ob-foot"><div class="ob-dots" id="obDots"><i class="on"></i><i></i><i></i></div><button class="cta" id="obNext" type="button">Devam</button></div>
</div>

<script>
(function(){
"use strict";
var $=function(id){return document.getElementById(id)};
var B=document.body;
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v)}catch(e){}return null}
var RM=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches);
var S={durum:"",info:{},paused:false,conn:false,pending:null,pendT:0,style:store("gta6.stil")==="fis"?"fis":"dugme",
 scene:null,sceneLoading:false,hist:[],cur:null,curOld:false,sess:null,last:null,notice:""};
try{S.last=JSON.parse(store("gta6.oturum")||"null")}catch(e){S.last=null}

var tT=0;
function toast(m){if(!m)return;var t=$("toast");t.textContent=m;t.classList.add("on");clearTimeout(tT);
 tT=setTimeout(function(){t.classList.remove("on")},2800)}
function post(n){return fetch("/komut/"+n,{method:"POST",cache:"no-store"}).then(function(r){return r.json()})}
function cmd(n){return post(n).catch(function(){toast("Bilgisayara ulaşılamadı");return null})}
function txt(id,v){var e=$(id);if(e&&e.textContent!==v)e.textContent=v}

/* ---------------------------------------------------------------- durum */
function refresh(){return post("durum").then(function(j){if(!j)return;S.info=j;S.paused=!!j.duraklatildi;setDurum(j.durum)})
 .catch(function(){})}
function setDurum(s){
 if(!s){render();return}
 var was=S.durum;S.durum=s;
 if(S.pending!==null&&(S.pending===(s==="calisiyor"))){S.pending=null;clearTimeout(S.pendT)}
 if(s==="calisiyor"&&was!=="calisiyor"){S.sess={t:Date.now(),n:0};if(was)S.paused=false}
 if(was==="calisiyor"&&s!=="calisiyor")endSess();
 render()}
function endSess(){var s=S.sess;S.sess=null;if(!s||!s.n)return;
 S.last={n:s.n,m:Math.max(1,Math.round((Date.now()-s.t)/60000)),t:Date.now()};store("gta6.oturum",JSON.stringify(S.last))}
function toggle(want){
 var run=S.durum==="calisiyor";
 if(want===run){S.pending=null;render();return}
 if(!S.conn){toast("Bilgisayara bağlı değil");render();return}
 if(S.durum!=="hazir"&&S.durum!=="calisiyor"){toast("Uygulama hazırlanıyor, birkaç saniye sonra tekrar deneyin");render();return}
 S.pending=want;render();clearTimeout(S.pendT);
 S.pendT=setTimeout(function(){if(S.pending!==null){S.pending=null;render();refresh()}},10000);
 try{if(navigator.vibrate)navigator.vibrate(12)}catch(e){}
 cmd("baslat_durdur").then(function(j){if(!j){S.pending=null;render();return}
  if(j.mesaj&&!/^(Başlatılıyor|Durduruluyor)/.test(j.mesaj))toast(j.mesaj)})}

/* ---------------------------------------------------------------- yardımcılar */
function where(){var c=S.info.cikis||"TV";
 return c==="Bilgisayar"?"bilgisayarda":c==="TV"?"TV'de":"TV'de ve bilgisayarda"}
function bin(n){if(n>=1e6)return(Math.round(n/1e5)/10).toString().replace(".",",")+" milyon";
 if(n>=1000)return Math.round(n/1000)+" bin";return String(n)}
function sessText(){
 if(S.sess&&S.durum==="calisiyor")return[S.sess.n+" satır · "+Math.max(1,Math.round((Date.now()-S.sess.t)/60000))+" dk","Şu anki oturum"];
 if(S.last)return[S.last.n+" satır · "+S.last.m+" dk","Son çeviri oturumu"];
 if(S.info.oturum_satir>0)return[S.info.oturum_satir+" satır","Bu açılışta"];
 return["—","Henüz oturum yok"]}
function isMain(z){return z==="altyazi"||String(z).indexOf("altyazi.")===0}
function norm(s){return String(s||"").trim().toLowerCase()}
function addHist(d){
 var e={zone:d.zone||"",text:d.text||"",en:d.english||"",t:Date.now()};if(!e.text)return;
 var a=norm(e.en);
 for(var i=S.hist.length-1;i>=0&&i>=S.hist.length-6;i--){var h=S.hist[i];if(h.zone!==e.zone)continue;var b=norm(h.en);
  if(a&&b&&(a===b||a.indexOf(b)===0||b.indexOf(a)===0)){h.text=e.text;h.en=e.en;if(isMain(e.zone))S.cur=h;return}break}
 S.hist.push(e);if(S.hist.length>100)S.hist.shift();
 if(isMain(e.zone)){S.cur=e;if(S.sess)S.sess.n++}}
function subEl(h,cls){var w=document.createElement("div");w.className=cls;
 if(!isMain(h.zone)){var z=document.createElement("span");z.className="z";z.textContent="EKRAN";w.appendChild(z)}
 var tr=document.createElement("div");tr.className="tr";tr.textContent=h.text;w.appendChild(tr);
 if(h.en){var en=document.createElement("div");en.className="en";en.textContent=h.en;w.appendChild(en)}
 return w}

/* ---------------------------------------------------------------- çizim */
function render(){
 var run=S.durum==="calisiyor",on=S.pending!==null?S.pending:run,info=S.info,fis=S.style==="fis"&&!!S.scene;
 B.classList.toggle("run",run);B.classList.toggle("fis",fis);B.classList.toggle("paused",run&&S.paused);
 B.classList.toggle("off",!S.conn);
 var t,s;
 if(!S.conn){t=S.durum?"Bağlantı yok":"Bağlanıyor";s="Bilgisayardaki GTA6 Altyazı açık olmalı; telefon aynı Wi-Fi ağında olsun."}
 else if(run){t=S.paused?"Duraklatıldı":"Çeviri açık";s=S.paused?"Devam'a dokunun, altyazılar yeniden gelsin.":"Altyazılar "+where()+" gösteriliyor."}
 else if(S.durum==="hazir"){t="Hazır";s=fis?"PS5'te oyunu açın, sonra fişi prize takın.":"PS5'te oyunu açın, sonra başlatın."}
 else if(S.durum==="hata"){t="Bir sorun var";s=S.notice||"Bilgisayardaki uygulamaya göz atın."}
 else{t="Hazırlanıyor";s="Çeviri motorları yükleniyor, birkaç saniye sürer."}
 txt("hTitle",t);txt("hSub",s);
 // ana düğme
 var cta=$("bStart");cta.disabled=!S.conn||S.durum!=="hazir"||S.pending===true;
 txt("ctaTx",S.pending===true?"Başlatılıyor...":S.durum==="hazirlaniyor"?"Hazırlanıyor...":"Çeviriyi başlat");
 // kaydırmalı düğme
 if(!drag)setSlider(on?1:0);
 var sl=$("slider");sl.setAttribute("aria-checked",on?"true":"false");sl.classList.toggle("busy",S.pending!==null);
 txt("slOn",S.pending===true?"Başlatılıyor...":"Altyazı açık");txt("slOff",S.pending===false?"Durduruluyor...":"Altyazı kapalı");
 // canlı yazı
 var c=S.cur;
 $("tvWait").hidden=!!c;txt("tvTr",c?c.text:"");$("tvTr").classList.toggle("old",!!c&&S.curOld);txt("tvEn",c&&c.en?c.en:"");
 txt("bdg",S.paused?"DURAKLATILDI":"CANLI");
 // kartlar
 var ps5=info.ps5_adi||"PS5";txt("cPs5N",ps5);txt("chPs5",info.ps5_adi||"—");
 var ps=run?["g","Bağlı, görüntü alınıyor"]:info.ps5==="acik"?["g","Açık"]:info.ps5==="uykuda"?["a","Uykuda"]:["","Bağlanmak için dokunun"];
 $("cPs5D").className="dot "+ps[0];txt("cPs5S",ps[1]);
 var out=info.cikis||"TV";txt("cOutN",out);txt("chOut",out);
 var tvOut=out.indexOf("TV")>=0;
 $("cOutD").className="dot "+(info.tv_bagli?"g":"");
 txt("cOutS",info.tv_bagli?"TV bağlı":tvOut?"TV bekleniyor":"Bilgisayar ekranında");
 txt("cEngN",info.ceviri||"—");txt("chEng",info.ceviri||"—");
 txt("cEngS",/Claude|Gemini|DeepL|yapay/.test(info.ceviri||"")?"Yapay zekâ çevirisi":"Çeviri motoru");
 txt("cPackS",info.paket_oyun>0&&info.paket_satir>0?info.paket_oyun+" oyun · "+bin(info.paket_satir)+" satır":"Paketteki satırlar beklemeden gelir");
 txt("chPack",info.paket_acik===false?"Kapalı":"Ücretsiz");
 var st=sessText();txt("cSessN",st[0]);txt("cSessS",st[1]);
 // duraklat
 txt("pzTx",S.paused?"Devam":"Duraklat");$("pzIc").setAttribute("href",S.paused?"#i-play":"#i-pause");
 // son çeviriler
 var L=$("list");L.textContent="";var last=S.hist.slice(-4).reverse();
 if(!last.length){var em=document.createElement("div");em.className="empty";em.textContent="Çeviriler geldikçe burada görünür.";L.appendChild(em)}
 last.forEach(function(h){L.appendChild(subEl(h,"sub"))});
 // ayarlar
 txt("mVer",info.surum?"v"+info.surum:"—");txt("mConn",S.conn?"Bağlı":"Bağlantı yok");txt("mAddr",location.host||"—");
 Array.prototype.forEach.call(document.querySelectorAll("#seg button"),function(b){b.classList.toggle("sel",b.getAttribute("data-st")===S.style)});
 if($("shHist").classList.contains("on"))renderHist();
 if(fis)renderScene(on)}

function renderHist(){var H=$("histBody");H.textContent="";
 if(!S.hist.length){var e=document.createElement("div");e.className="empty";e.textContent="Bu oturumda henüz çeviri yok. Çeviri başlayınca gelen her satır burada listelenir.";H.appendChild(e);return}
 var box=document.createElement("div");box.className="list";
 S.hist.slice().reverse().forEach(function(h){var r=subEl(h,"hrow");var tm=document.createElement("div");tm.className="tm";
  var d=new Date(h.t);tm.textContent=("0"+d.getHours()).slice(-2)+":"+("0"+d.getMinutes()).slice(-2);r.appendChild(tm);box.appendChild(r)});
 H.appendChild(box)}

/* ---------------------------------------------------------------- kaydırmalı düğme */
var sl=$("slider"),kn=$("knob"),drag=null;
function slMax(){return Math.max(1,sl.clientWidth-kn.offsetWidth-12)}
function setSlider(p){kn.style.transform="translateX("+(p*slMax()).toFixed(1)+"px)";sl.style.setProperty("--p",p.toFixed(3))}
function curOn(){return S.pending!==null?S.pending:S.durum==="calisiyor"}
sl.addEventListener("pointerdown",function(e){if(e.button>0)return;drag={x:e.clientX,p0:curOn()?1:0,p:curOn()?1:0,moved:false};
 try{sl.setPointerCapture(e.pointerId)}catch(_){}sl.classList.add("drag")});
sl.addEventListener("pointermove",function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>6)drag.moved=true;
 if(!drag.moved)return;drag.p=Math.max(0,Math.min(1,drag.p0+dx/slMax()));setSlider(drag.p)});
sl.addEventListener("pointerup",function(){if(!drag)return;var d=drag;drag=null;sl.classList.remove("drag");
 var on=curOn(),want=d.moved?d.p>0.5:!on;if(want!==on)toggle(want);else render()});
sl.addEventListener("pointercancel",function(){drag=null;sl.classList.remove("drag");render()});
sl.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle(!curOn())}});
addEventListener("resize",function(){if(!drag)render()});

/* ---------------------------------------------------------------- fiş sahnesi */
var G=null,plug={x:0,y:0},pd=null,anim=0;
function okRect(r,n){if(!r||r.length!==n)return false;for(var i=0;i<n;i++)if(typeof r[i]!=="number"||!isFinite(r[i]))return false;return true}
function loadScene(){
 if(S.scene||S.sceneLoading)return;S.sceneLoading=true;
 fetch("/marka/sahne.json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(g){
  if(!(g&&g.w>0&&g.h>0&&okRect(g.screen,4)&&okRect(g.socket,4)&&okRect(g.ps5,4)&&okRect(g.plug_rest,2)))throw 0;
  var im=$("sImg");im.onload=function(){S.sceneLoading=false;buildScene(g);render()};
  im.onerror=function(){sceneFail()};im.src="/marka/sahne.png"}).catch(sceneFail)}
function sceneFail(){S.sceneLoading=false;S.scene=null;if(S.sceneAsked&&S.style==="fis")toast("Fiş görünümü yüklenemedi, Düğme gösteriliyor");render()}
function pc(v,t){return(v/t*100).toFixed(3)+"%"}
function place(el,r){el.style.left=pc(r[0],G.w);el.style.top=pc(r[1],G.h);el.style.width=pc(r[2]-r[0],G.w);el.style.height=pc(r[3]-r[1],G.h)}
function sockC(){var s=G.socket;return{x:(s[0]+s[2])/2,y:(s[1]+s[3])/2}}
function plugSize(){var s=G.socket,m=Math.min(s[2]-s[0],s[3]-s[1]);return{w:m*0.7,h:m*1.12}}
function buildScene(g){G=g;S.scene=g;
 $("scene").style.paddingTop=(g.h/g.w*100).toFixed(3)+"%";$("sCable").setAttribute("viewBox","0 0 "+g.w+" "+g.h);
 place($("sGlow"),g.screen);place($("sScreen"),g.screen);place($("sSock"),g.socket);
 var t=curOn()?sockC():{x:g.plug_rest[0],y:g.plug_rest[1]};plug.x=t.x;plug.y=t.y;drawPlug()}
function drawPlug(){if(!G)return;var ps=plugSize(),el=$("sPlug");
 el.style.left=pc(plug.x-ps.w/2,G.w);el.style.top=pc(plug.y-ps.h/2,G.h);el.style.width=pc(ps.w,G.w);el.style.height=pc(ps.h,G.h);
 var p=G.ps5,cf=okRect(G.cable_from,2)?G.cable_from:[p[0]+(p[2]-p[0])*0.6,p[1]+(p[3]-p[1])*0.6],sx=cf[0],sy=cf[1],ex=plug.x,ey=plug.y+ps.h/2-2;
 var low=Math.min(G.h*0.985,Math.max(sy,ey)+G.h*0.09);
 var d="M"+sx.toFixed(1)+" "+sy.toFixed(1)+"C"+(sx+(ex-sx)*0.3).toFixed(1)+" "+low.toFixed(1)+" "+ex.toFixed(1)+" "+(low+G.h*0.02).toFixed(1)+" "+ex.toFixed(1)+" "+ey.toFixed(1);
 var w=Math.max(4,ps.w*0.16);
 $("cab1").setAttribute("d",d);$("cab1").setAttribute("stroke-width",w.toFixed(1));
 $("cab2").setAttribute("d",d);$("cab2").setAttribute("stroke-width",(w*0.3).toFixed(1));
 var sc=sockC(),near=Math.hypot(plug.x-sc.x,plug.y-sc.y)<snapR();$("sSock").classList.toggle("near",!!pd&&near)}
function snapR(){var s=G.socket;return Math.max(s[2]-s[0],s[3]-s[1])*1.1}
function animPlug(tx,ty){cancelAnimationFrame(anim);var fx=plug.x,fy=plug.y;
 if(RM||Math.hypot(tx-fx,ty-fy)<1){plug.x=tx;plug.y=ty;drawPlug();return}
 var t0=performance.now(),dur=460;
 (function step(now){var k=Math.min(1,(now-t0)/dur),e=1-Math.pow(1-k,3);plug.x=fx+(tx-fx)*e;plug.y=fy+(ty-fy)*e;drawPlug();
  if(k<1)anim=requestAnimationFrame(step);else anim=0})(t0)}
function renderScene(on){
 var sc=$("scene");sc.classList.toggle("plugged",on);
 var c=S.cur;txt("sTr",c?c.text:"Altyazı bekleniyor...");$("sTr").classList.toggle("old",!c||S.curOld);
 txt("sEn",S.durum==="calisiyor"&&c&&c.en?c.en:"");
 $("sCap").textContent=on?"Fişi çekin, çeviri dursun":"Fişi takın, çeviri başlasın";
 // ekran yazısının boyu ekranın genişliğine göre
 var w=sc.clientWidth*(G.screen[2]-G.screen[0])/G.w;if(w>0)$("sScreen").style.fontSize=Math.max(6,w/17).toFixed(1)+"px";
 if(!pd){var t=on?sockC():{x:G.plug_rest[0],y:G.plug_rest[1]};if(Math.hypot(t.x-plug.x,t.y-plug.y)>1&&!anim)animPlug(t.x,t.y);else if(!anim)drawPlug()}}
var pg=$("sPlug");
pg.addEventListener("pointerdown",function(e){if(!G||e.button>0)return;e.preventDefault();cancelAnimationFrame(anim);anim=0;
 pd={x:e.clientX,y:e.clientY,x0:plug.x,y0:plug.y,moved:false};try{pg.setPointerCapture(e.pointerId)}catch(_){}pg.classList.add("grab")});
pg.addEventListener("pointermove",function(e){if(!pd)return;var r=$("scene").getBoundingClientRect(),k=G.w/r.width;
 var dx=e.clientX-pd.x,dy=e.clientY-pd.y;if(Math.hypot(dx,dy)>6)pd.moved=true;if(!pd.moved)return;
 plug.x=Math.max(0,Math.min(G.w,pd.x0+dx*k));plug.y=Math.max(0,Math.min(G.h,pd.y0+dy*k));drawPlug()});
function plugUp(cancel){if(!pd)return;var d=pd;pd=null;pg.classList.remove("grab");$("sSock").classList.remove("near");
 var on=curOn(),sc=sockC(),want=cancel?on:d.moved?Math.hypot(plug.x-sc.x,plug.y-sc.y)<snapR():!on;
 if(want!==on)toggle(want);render()}
pg.addEventListener("pointerup",function(){plugUp(false)});
pg.addEventListener("pointercancel",function(){plugUp(true)});
pg.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle(!curOn())}});

/* ---------------------------------------------------------------- düğmeler, alt sayfalar */
$("bStart").onclick=function(){toggle(true)};
$("bFs").onclick=function(){cmd("tam_ekran").then(function(j){if(j)toast(j.mesaj||"Ekran çevriliyor...")})};
$("bPz").onclick=function(){cmd("duraklat").then(function(j){if(!j)return;S.paused=!!j.duraklatildi;if(j.mesaj)toast(j.mesaj);render()})};
$("cPs5").onclick=function(){cmd("baglan").then(function(j){if(j&&j.mesaj)toast(j.mesaj)})};
$("cPack").onclick=function(){toast("Paketler bilgisayardaki uygulamanın Paketler bölümünden indirilir")};
$("cSess").onclick=function(){openSheet("shHist")};
$("bAll").onclick=function(){openSheet("shHist")};
$("bHist").onclick=function(){openSheet("shHist")};
$("bSet").onclick=function(){openSheet("shSet")};
function openSheet(id){closeSheets();$("sheetBg").classList.add("on");$(id).classList.add("on");if(id==="shHist")renderHist()}
function closeSheets(){$("sheetBg").classList.remove("on");$("shSet").classList.remove("on");$("shHist").classList.remove("on")}
$("sheetBg").onclick=closeSheets;
Array.prototype.forEach.call(document.querySelectorAll("[data-close]"),function(b){b.onclick=closeSheets});
Array.prototype.forEach.call(document.querySelectorAll("#seg button"),function(b){b.onclick=function(){
 S.style=b.getAttribute("data-st");store("gta6.stil",S.style);if(S.style==="fis"){S.sceneAsked=true;loadScene()}render()}});
$("bOb").onclick=function(){closeSheets();obShow()};
addEventListener("keydown",function(e){if(e.key==="Escape")closeSheets()});

/* ---------------------------------------------------------------- tanıtım */
var obI=0,obX=null;
function obShow(){$("ob").hidden=false;B.classList.add("noscroll");obGo(0)}
function obGo(i){obI=Math.max(0,Math.min(2,i));$("obTrack").style.transform="translateX("+(-obI*100)+"%)";
 Array.prototype.forEach.call($("obDots").children,function(d,k){d.classList.toggle("on",k===obI)});
 $("obNext").textContent=obI===2?"Başlayalım":"Devam"}
function obDone(){store("gta6.ob","1");var o=$("ob");o.classList.add("bye");B.classList.remove("noscroll");
 setTimeout(function(){o.hidden=true;o.classList.remove("bye")},RM?0:300)}
$("obNext").onclick=function(){if(obI<2)obGo(obI+1);else obDone()};
$("obSkip").onclick=obDone;
$("obView").addEventListener("pointerdown",function(e){obX={x:e.clientX,y:e.clientY}});
$("obView").addEventListener("pointerup",function(e){if(!obX)return;var dx=e.clientX-obX.x,dy=e.clientY-obX.y;obX=null;
 if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.3)obGo(obI+(dx<0?1:-1))});
$("obView").addEventListener("pointercancel",function(){obX=null});

/* ---------------------------------------------------------------- canlı akış */
function connect(){var es=new EventSource("/olaylar");
 es.onopen=function(){S.conn=true;refresh();render()};
 es.onmessage=function(m){var d;try{d=JSON.parse(m.data)}catch(e){return}
  if(d.type==="show"){addHist(d);if(isMain(d.zone))S.curOld=false}
  else if(d.type==="clear"){if(isMain(d.zone))S.curOld=true}
  else if(d.type==="notice"){S.notice=d.mesaj||"";toast(d.mesaj)}
  else if(d.type==="durum"){setDurum(d.durum);refresh();return}
  else return;
  render()};
 es.onerror=function(){es.close();S.conn=false;render();setTimeout(connect,1500)}}

if(store("gta6.ob")!=="1")obShow();
if(S.style==="fis")loadScene();
render();connect();refresh();
setInterval(function(){if(!document.hidden)refresh()},15000);
document.addEventListener("visibilitychange",function(){if(!document.hidden)refresh()});
})();
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

            def _marka(self, name: str) -> None:
                """Kumanda sayfasının görselleri: yalnız klasördeki düz adlar (alt klasör, '..' yok)."""
                m = _MARKA_NAME.fullmatch(name)
                try:
                    body = (MARKA_DIR / name).read_bytes() if m else None
                except OSError:
                    body = None
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", _MARKA_TYPES[m.group(1)])
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "max-age=3600")
                self.end_headers()
                self.wfile.write(body)

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
                elif path.startswith("/marka/"):
                    self._marka(path[len("/marka/"):])
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
