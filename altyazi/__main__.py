"""Kullanım:
    python -m altyazi                  # arayüzlü uygulama
    python -m altyazi calistir         # arayüzsüz çalıştır (config.yaml'a göre)
    python -m altyazi pencereler       # açık pencereleri listele (chiaki'nin başlığını bulmak için)
    python -m altyazi kameralar        # capture kartları ve ses girişlerini listele
    python -m altyazi kalibre          # o anki kareyi bölgeler ve maskelerle kalibrasyon.png'ye kaydet
    python -m altyazi test resim.png   # bir ekran görüntüsünde OCR + çeviriyi dene (pencere açmadan)
    python -m altyazi tv bul           # ev ağındaki Android/Google TV'yi bul
    python -m altyazi tv kur [ip]      # TV uygulamasını kur ve başlat
    python -m altyazi tv eslestir IP:PORT KOD   # yeni Google TV'lerde kablosuz hata ayıklama eşleştirmesi
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time

from . import config as config_mod
from . import winutil


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "anthropic", "urllib3", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _recognizer(cfg):
    from .ocr import make_recognizer

    rec = make_recognizer(cfg.ocr)
    rec.warmup()
    return rec


def cmd_run(cfg) -> int:
    from PySide6.QtWidgets import QApplication

    from .capture import make_source
    from .overlay import Bridge, OverlayWindow, Painter, QtSink, VideoWindow
    from .pipeline import MultiSink, Pipeline
    from .server import EventServer
    from .translate import TranslationEngine

    log = logging.getLogger("altyazi")
    rec = _recognizer(cfg)
    engine = TranslationEngine(cfg.ceviri)
    source = make_source(cfg)

    app = QApplication(sys.argv)
    bridge = Bridge()
    painter = Painter(cfg.gosterim.yazi_tipi, cfg.gosterim.gecikme_goster)
    server = None
    if cfg.sunucu.acik:
        server = EventServer(cfg.sunucu.port, cfg.tv.kalibrasyon, on_command=lambda ad: commands(ad))
        server.start()
        if cfg.tv.ip and cfg.tv.otomatik:
            from .tv import setup_in_background
            setup_in_background(cfg.tv.ip, cfg.sunucu.port, cfg.tv.mod)
    sink = MultiSink(QtSink(bridge), server)

    frame_sink = None
    if cfg.gosterim.mod == "pencere":
        win = VideoWindow(painter, bridge, cfg.gosterim.tam_ekran)
        frame_sink = win.push_frame
    else:
        win = OverlayWindow(painter, bridge, source.hwnd)
    win.show()

    audio = None
    if cfg.kaynak.tur == "capture" and cfg.kaynak.capture_ses:
        try:
            from .audio import start_passthrough
            audio = start_passthrough(cfg.kaynak.capture_ses_cihaz)
        except Exception as e:  # noqa: BLE001
            log.warning("Ses aktarımı başlatılamadı: %s", e)

    pipe = Pipeline(cfg, sink, rec, engine, source, frame_sink=frame_sink)
    if server is not None:
        pipe.notice = server.notice

    def commands(ad: str) -> dict:
        if ad == "tam_ekran":
            pipe.request_fullscreen()
            return {"mesaj": "Ekran çevriliyor..."}
        if ad == "duraklat":
            paused = pipe.toggle_pause()
            return {"mesaj": "Duraklatıldı" if paused else "Devam ediyor", "duraklatildi": paused}
        return {"mesaj": f"Bilinmeyen komut: {ad}"}

    from .hotkeys import Hotkeys
    hotkeys = Hotkeys({cfg.kisayol.tam_ekran: pipe.request_fullscreen, cfg.kisayol.duraklat: pipe.toggle_pause})
    hotkeys.start()
    pipe.start()
    log.info("Hazır. Çıkmak için bu pencerede Ctrl+C.")
    try:
        code = app.exec()
    except KeyboardInterrupt:
        code = 0
    pipe.stop()
    hotkeys.stop()
    if audio is not None:
        audio.close()
    return code


def cmd_windows() -> int:
    wins = winutil.list_windows()
    if not wins:
        print("Pencere bulunamadı (bu komut sadece Windows'ta çalışır).")
    for hwnd, title in wins:
        print(f"{hwnd:>10}  {title}")
    return 0


def cmd_cameras() -> int:
    import cv2

    print("Görüntü cihazları:")
    for i in range(6):
        cap = cv2.VideoCapture(i, getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY))
        if cap.isOpened():
            print(f"  {i}: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        cap.release()
    try:
        from .audio import list_inputs
        print("Ses girişleri:")
        for i, n in list_inputs():
            print(f"  {i}: {n}")
    except Exception as e:  # noqa: BLE001
        print(f"Ses cihazları okunamadı: {e}")
    return 0


def _grab_frame(cfg, timeout: float = 5.0):
    from .capture import make_source

    got: dict = {}
    ev = threading.Event()

    def on_frame(frame, _t):  # noqa: ANN001
        got.setdefault("f", frame)
        ev.set()

    src = make_source(cfg)
    src.start(on_frame)
    ev.wait(timeout)
    src.stop()
    if "f" not in got:
        raise RuntimeError("Kaynaktan kare alınamadı")
    return got["f"]


def cmd_calibrate(cfg, image: str | None) -> int:
    import cv2
    import numpy as np

    from .detector import ZoneDetector, zone_rect

    frame = cv2.imread(image) if image else _grab_frame(cfg)
    frame = frame[..., :3].copy()
    h, w = frame.shape[:2]
    vis = frame.copy()
    colors = [(0, 255, 255), (255, 128, 0), (0, 255, 0), (255, 0, 255), (0, 128, 255)]
    for i, z in enumerate(cfg.bolgeler):
        x0, y0, x1, y1 = zone_rect(z, w, h)
        mask = ZoneDetector(z).text_mask(frame[y0:y1, x0:x1])
        overlay = vis[y0:y1, x0:x1]
        overlay[mask] = (0, 0, 255)                           # metin sayılan pikseller kırmızı
        c = colors[i % len(colors)]
        cv2.rectangle(vis, (x0, y0), (x1, y1), c, 2)
        cv2.putText(vis, f"{z.ad} ({np.count_nonzero(mask)} px)", (x0 + 4, max(18, y0 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    cv2.imwrite("kalibrasyon.png", vis)
    cv2.imwrite("kalibrasyon_ham.png", frame)
    print(f"Kaydedildi: kalibrasyon.png (bölgeler + kırmızı = metin sayılan pikseller), {w}x{h}")
    print("Ham kare: kalibrasyon_ham.png (bunu bana atarsan bölgeleri ayarlarım)")
    return 0


def cmd_test(cfg, path: str) -> int:
    import cv2

    from .pipeline import Pipeline
    from .translate import TranslationEngine

    frame = cv2.imread(path)
    if frame is None:
        print(f"Resim açılamadı: {path}")
        return 1
    rec = _recognizer(cfg)
    engine = TranslationEngine(cfg.ceviri)
    done = threading.Event()

    class PrintSink:
        def show(self, it):  # noqa: ANN001
            print(f"[{it.zone}] {it.latency_ms:5.0f} ms  OCR {it.ocr_ms:3.0f} ms  {it.source:>16} {it.mt_ms:4.0f} ms"
                  f"\n    EN: {it.english}\n    TR: {it.text}")
            done.set()

        def clear(self, zone):  # noqa: ANN001
            pass

    pipe = Pipeline(cfg, PrintSink(), rec, engine)
    pipe.process(frame, time.perf_counter())
    done.wait(3)
    time.sleep(3 if engine.refine else 0.3)   # kalite katmanının sonucunu da bekle
    return 0


def cmd_tv(cfg, action: str | None, ip: str | None, extra: str | None = None) -> int:
    import re

    from . import tv

    if action in (None, "bul"):
        print("Ev ağında TV aranıyor...")
        found = tv.scan()
        try:
            mdns = tv.Adb().run("mdns", "services", timeout=10)
            paired = sorted(set(re.findall(r"_adb-tls-connect\S*\s+(\d+\.\d+\.\d+\.\d+)", mdns)))
        except tv.TvError:
            paired = []
        for h in found:
            print(f"  {h}  (klasik ağ hata ayıklaması açık)")
        for h in paired:
            print(f"  {h}  (kablosuz hata ayıklama ile eşleştirilmiş)")
        if not found and not paired:
            print("Bulunamadı. TV açık mı? Geliştirici seçeneklerinde 'USB hata ayıklama' açık mı?\n"
                  "Yeni Google TV'lerde: 'Kablosuz hata ayıklama' > 'Eşleştirme koduyla cihaz eşleştir', sonra:\n"
                  "  baslat.bat tv eslestir IP:PORT KOD")
            return 1
        print(f"\nKurmak için: baslat.bat tv kur {(found or paired)[0]}")
        return 0
    if action == "eslestir":
        if not ip or ":" not in ip or not extra:
            print("Kullanım: baslat.bat tv eslestir 192.168.1.xx:PORT 123456  (TV'deki eşleştirme ekranında yazar)")
            return 1
        print(tv.Adb().pair(ip, extra))
        print(f"Eşleştirildi. Şimdi: baslat.bat tv kur {ip.split(':')[0]}")
        return 0
    if action == "kur":
        host = ip or cfg.tv.ip
        if not host:
            found = tv.scan()
            if len(found) != 1:
                print("TV'nin adresini yaz: baslat.bat tv kur 192.168.1.xx" + (f"  (bulunanlar: {found})" if found else ""))
                return 1
            host = found[0]
        server = tv.setup(host.split(":")[0], cfg.sunucu.port, force_install=True, mode=cfg.tv.mod,
                          on_prompt=lambda: print("TV'ye bak: 'Hata ayıklamaya izin verilsin mi?' -> "
                                                  "'Her zaman izin ver' + İzin ver (60 sn bekliyorum)"))
        print(f"Tamam! TV uygulaması kuruldu ve açıldı. TV bu bilgisayara bağlanacak: {server}")
        if host != cfg.tv.ip:
            print(f"Bir dahakine otomatik açılması için config.local.yaml'a yaz:\n  tv:\n    ip: \"{host}\"")
        print("Not: Windows güvenlik duvarı sorarsa 'Özel ağlar'a izin ver, yoksa TV bağlanamaz.")
        return 0
    print("Kullanım: tv bul | tv kur [ip] | tv eslestir IP:PORT KOD")
    return 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows konsolunda Türkçe karakterler
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="altyazi", description="GTA 6 gerçek zamanlı Türkçe altyazı")
    ap.add_argument("komut", nargs="?", default="arayuz",
                    choices=["arayuz", "calistir", "pencereler", "kameralar", "kalibre", "test", "tv"])
    ap.add_argument("dosya", nargs="?", help="kalibre/test için resim dosyası, tv için bul/kur")
    ap.add_argument("ek", nargs="?", help="tv kur/eslestir için TV'nin adresi")
    ap.add_argument("ek2", nargs="?", help="tv eslestir için eşleştirme kodu")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("-v", "--ayrintili", action="store_true")
    ap.add_argument("--arka-plan", action="store_true", help="simge durumunda başlat (Windows açılışı)")
    a = ap.parse_args(argv)
    if a.komut == "arayuz":
        from .ui.run import run_gui
        return run_gui(background=a.arka_plan)
    _setup_logging(a.ayrintili)
    winutil.set_dpi_aware()
    winutil.add_cuda_dll_dirs()
    if a.komut == "pencereler":
        return cmd_windows()
    if a.komut == "kameralar":
        return cmd_cameras()
    cfg = config_mod.load(a.config if a.config != "config.yaml" else None)
    if a.komut == "kalibre":
        return cmd_calibrate(cfg, a.dosya)
    if a.komut == "tv":
        try:
            return cmd_tv(cfg, a.dosya, a.ek, a.ek2)
        except Exception as e:  # noqa: BLE001
            print(f"Hata: {e}")
            return 1
    if a.komut == "test":
        if not a.dosya:
            ap.error("test için resim dosyası verin")
        return cmd_test(cfg, a.dosya)
    return cmd_run(cfg)


if __name__ == "__main__":
    sys.exit(main())
