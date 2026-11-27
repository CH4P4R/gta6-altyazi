"""OBS yayın görünümü: /obs/stil, /yazi yazı tipleri ve sayfanın şerit kipinde çizimi (gerçek Chromium)."""

import json
import time
import urllib.request

import pytest

from altyazi.config import ObsCfg
from altyazi.pipeline import DisplayItem
from altyazi.server import EventServer, PAGE
from tests.test_server import free_port


def start(style):
    port = free_port()
    srv = EventServer(port)
    srv.obs_style = style
    srv.start()
    time.sleep(0.2)
    return srv, port


def test_style_endpoint_fonts_and_page_flag():
    o = ObsCfg(gorunum="serit", boyut=999, kutu=-5, renk="#ffe14d")
    st = o.style()
    assert st["boyut"] == 250 and st["kutu"] == 0, "sınırlar"
    srv, port = start(st)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/obs/stil", timeout=3) as r:
        assert json.loads(r.read())["gorunum"] == "serit"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/yazi/Barlow-SemiBold.ttf", timeout=3) as r:
        assert r.headers["Content-Type"] == "font/ttf" and len(r.read()) > 10000
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/yazi/..%2Fconfig.yaml", timeout=3)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/obs", timeout=3) as r:
        page = r.read().decode()
    assert "const OBS=true" in page and "transparent" in page
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
        assert "const OBS=false" in r.read().decode()
    assert "OBSMODE" in PAGE


def test_strip_mode_draws_at_the_bottom_in_chosen_color():
    pw = pytest.importorskip("playwright.sync_api")
    srv, port = start(ObsCfg(gorunum="serit", renk="#ffe14d", kutu=0, kontur=False).style())
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 960, "height": 540})
            pg.goto(f"http://127.0.0.1:{port}/obs")
            pg.wait_for_timeout(600)
            srv.show(DisplayItem("altyazi", (0.3, 0.10, 0.7, 0.16), (0.1, 0.05, 0.9, 0.2), 0.04, "Get in.",
                                 "Arabaya bin, gidiyoruz.", "orta", "ust", 255, 1.0))
            pg.wait_for_timeout(700)
            # Sarı yazının pikselleri: üstteki asıl yerde değil, altta şeritte
            got = pg.evaluate("""() => {const c=document.getElementById('c'),x=c.getContext('2d');
              const d=x.getImageData(0,0,c.width,c.height).data;let top=0,bottom=0;
              for(let i=0;i<d.length;i+=4){if(d[i]>200&&d[i+1]>180&&d[i+2]<140&&d[i+3]>200){
                const y=Math.floor(i/4/c.width)/c.height; if(y<0.5)top++;else bottom++}}return [top,bottom]}""")
            b.close()
        assert got[1] > 200 and got[0] == 0, got
    finally:
        srv.stop() if hasattr(srv, "stop") else None
