"""Arayüzün beyni: motorları hazırlar, çeviriyi başlatır/durdurur, TV'yi bağlar, geçmişi tutar.

Ağır işler (model yükleme, TV kurulumu, ekran yakalama) arka plan iş parçacıklarında yapılır;
sonuçlar Qt sinyalleriyle arayüze gelir, böylece pencere hiç donmaz.
"""

from __future__ import annotations

import copy
import logging
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from . import config as config_mod
from . import winutil
from .overlay import Bridge, OverlayWindow, Painter, VideoWindow
from .pipeline import DisplayItem, MultiSink, Pipeline

log = logging.getLogger(__name__)

CHIAKI_CANDIDATES = [
    r"%ProgramFiles%\chiaki-ng\chiaki.exe",
    r"%ProgramFiles%\chiaki-ng\chiaki-ng.exe",
    r"%LOCALAPPDATA%\Programs\chiaki-ng\chiaki.exe",
    r"%LOCALAPPDATA%\Programs\chiaki-ng\chiaki-ng.exe",
    r"%USERPROFILE%\Downloads\chiaki-ng\chiaki.exe",
]
CHIAKI_DOWNLOAD = "https://github.com/streetpea/chiaki-ng/releases/latest"


def find_chiaki(configured: str = "") -> str | None:
    for c in ([configured] if configured else []) + CHIAKI_CANDIDATES:
        p = Path(os.path.expandvars(c))
        if p.is_file():
            return str(p)
    return None


class AppController(QObject):
    stateChanged = Signal(str)            # hazirlaniyor | hazir | calisiyor | hata
    notice = Signal(str)
    itemShown = Signal(object)            # DisplayItem
    itemCleared = Signal(str)
    historyChanged = Signal(object, bool)  # (DisplayItem, var olan kaydın güncellemesi mi)
    sourceStatus = Signal(bool, str)
    tvStatus = Signal(str, str)           # yok | baglaniyor | onay | bagli | hata, mesaj
    tvFound = Signal(list)
    enginesReady = Signal(dict)
    frameGrabbed = Signal(object)         # numpy kare ya da None
    testResult = Signal(object)           # translate.Result

    def __init__(self, cfg: config_mod.Config):
        super().__init__()
        self.cfg = cfg
        self.state = "hazirlaniyor"
        self.rec = None
        self.engine = None
        self.engine_info: dict = {}
        self.pipe: Pipeline | None = None
        self.window = None
        self.bridge = Bridge()
        self.history: deque[DisplayItem] = deque(maxlen=1000)
        self._hist_index: dict[int, DisplayItem] = {}
        self.latencies: deque[float] = deque(maxlen=30)
        self.server = None
        self.hotkeys = None
        self.tv_state = ("yok", "")
        self._start_server()
        self._start_hotkeys()
        self._src_timer = QTimer(self)
        self._src_timer.timeout.connect(self._check_source)
        self._src_timer.start(2000)
        self.warmup()

    # ------------------------------------------------------------------ altyapı
    def _start_server(self) -> None:
        if not self.cfg.sunucu.acik:
            return
        from .server import EventServer
        try:
            self.server = EventServer(self.cfg.sunucu.port, self.cfg.tv.kalibrasyon, on_command=self.command)
            self.server.start()
        except OSError as e:
            self.server = None
            log.error("Yerel sunucu açılamadı (port %s): %s", self.cfg.sunucu.port, e)

    def _start_hotkeys(self) -> None:
        from .hotkeys import Hotkeys
        k = self.cfg.kisayol
        self.hotkeys = Hotkeys({k.tam_ekran: lambda: self.command("tam_ekran"),
                                k.duraklat: lambda: self.command("duraklat")})
        self.hotkeys.start()

    def _set_state(self, s: str) -> None:
        self.state = s
        self.stateChanged.emit(s)

    def _notice(self, msg: str) -> None:
        self.notice.emit(msg)
        if self.server:
            self.server.notice(msg)

    def server_url(self, page: str = "kumanda") -> str:
        from .tv import local_ip
        try:
            ip = local_ip()
        except OSError:
            ip = "localhost"
        return f"http://{ip}:{self.cfg.sunucu.port}/{page}"

    # ------------------------------------------------------------------ motorlar
    def warmup(self) -> None:
        self._set_state("hazirlaniyor")
        threading.Thread(target=self._warmup, daemon=True, name="hazirlik").start()

    def _warmup(self) -> None:
        info = {}
        try:
            from .ocr import Recognizer
            from .translate import TranslationEngine
            c = self.cfg
            if self.rec is None:
                self.rec = Recognizer(c.ocr.model or None, c.ocr.anahtar_dosyasi or None, use_gpu=c.ocr.gpu)
                self.rec.warmup()
            self.engine = TranslationEngine(c.ceviri)
            info["ocr"] = self.rec.device
            f = self.engine.fast
            info["hizli"] = (f"{f.name} ({'GPU' if getattr(f, 'device', '') == 'cuda' else 'CPU'})"
                             if f and f.name == "yerel" else (f.name if f else None))
            info["kalite"] = self.engine.refine.name if self.engine.refine else None
            info["onbellek"] = len(self.engine.cache.mem)
            self.engine_info = info
            self.enginesReady.emit(info)
            self._set_state("hazir")
        except Exception as e:  # noqa: BLE001
            log.exception("Motorlar hazırlanamadı")
            self._notice(f"Motorlar hazırlanamadı: {e}")
            self._set_state("hata")

    # ------------------------------------------------------------------ çalıştırma
    def start(self) -> bool:
        if self.state != "hazir":
            self._notice("Henüz hazır değil, motorlar yükleniyor...")
            return False
        from .capture import make_source
        try:
            source = make_source(self.cfg)
        except Exception as e:  # noqa: BLE001
            self._notice(str(e))
            return False
        painter = Painter(self.cfg.gosterim.yazi_tipi, self.cfg.gosterim.gecikme_goster)
        frame_sink = None
        if self.cfg.gosterim.mod == "pencere":
            self.window = VideoWindow(painter, self.bridge, self.cfg.gosterim.tam_ekran)
            frame_sink = self.window.push_frame
        else:
            self.window = OverlayWindow(painter, self.bridge, source.hwnd)
        self.window.show()
        self.pipe = Pipeline(self.cfg, MultiSink(self, self.server), self.rec, self.engine, source,
                             frame_sink=frame_sink)
        self.pipe.notice = self._notice
        self.pipe.start()
        self._set_state("calisiyor")
        self._notice("Çeviri başladı")
        if self.cfg.tv.ip and self.cfg.tv.otomatik and self.tv_state[0] != "bagli":
            self.tv_connect()
        return True

    def stop(self) -> None:
        if self.pipe:
            self.pipe.stop()
            self.pipe = None
        if self.window:
            self.window.close()
            self.window.deleteLater()
            self.window = None
        if self.server:
            for z in list(self.server.state):
                self.server.clear(z)
        if self.state == "calisiyor":
            self._set_state("hazir")
            self._notice("Çeviri durduruldu")

    def toggle(self) -> None:
        self.stop() if self.state == "calisiyor" else self.start()

    def command(self, name: str) -> dict:
        """Kısayol, kumanda sayfası ve arayüz düğmeleri buradan geçer (her iş parçacığından çağrılabilir)."""
        pipe = self.pipe
        if name == "tam_ekran":
            if not pipe:
                return {"mesaj": "Önce çeviriyi başlat"}
            pipe.request_fullscreen()
            return {"mesaj": "Ekran çevriliyor..."}
        if name == "duraklat":
            if not pipe:
                return {"mesaj": "Çeviri çalışmıyor", "duraklatildi": True}
            paused = pipe.toggle_pause()
            return {"mesaj": "Duraklatıldı" if paused else "Devam ediyor", "duraklatildi": paused}
        return {"mesaj": f"Bilinmeyen komut: {name}"}

    # Sink arayüzü (Pipeline buraya yazar; başka iş parçacığından gelir, sinyaller kuyruğa alınır)
    def show(self, item: DisplayItem) -> None:
        self.bridge.shown.emit(item)
        self.itemShown.emit(item)
        updated = item.seq in self._hist_index
        self._hist_index[item.seq] = item
        if not updated:
            self.history.appendleft(item)
            if len(self._hist_index) > 2000:
                self._hist_index = {i.seq: i for i in self.history}
        else:
            for i, old in enumerate(self.history):
                if old.seq == item.seq:
                    self.history[i] = item
                    break
        self.latencies.append(item.latency_ms)
        self.historyChanged.emit(item, updated)

    def clear(self, zone: str) -> None:
        self.bridge.cleared.emit(zone)
        self.itemCleared.emit(zone)

    def avg_latency(self) -> float | None:
        return sum(self.latencies) / len(self.latencies) if self.latencies else None

    # ------------------------------------------------------------------ ayarlar
    def apply_config(self, cfg: config_mod.Config) -> None:
        old = self.cfg
        self.cfg = cfg
        config_mod.save(cfg)
        if self.server:
            x, y, w, h = cfg.tv.kalibrasyon
            self.server.tv = {"x": x, "y": y, "w": w, "h": h}
        engines_changed = old.ceviri != cfg.ceviri or old.ocr != cfg.ocr
        running = self.state == "calisiyor"
        if old.kisayol != cfg.kisayol:
            if self.hotkeys:
                self.hotkeys.stop()
            self._start_hotkeys()
        if engines_changed:
            if running:
                self.stop()
            if old.ocr != cfg.ocr:
                self.rec = None
            self.warmup()
            return
        if running and (old.bolgeler != cfg.bolgeler or old.kaynak != cfg.kaynak or old.gosterim != cfg.gosterim):
            self.stop()
            self.start()

    def edit_config(self) -> config_mod.Config:
        """Düzenlemek için ayarların kopyası (apply_config ile geri verilir)."""
        return copy.deepcopy(self.cfg)

    # ------------------------------------------------------------------ PS5 / chiaki
    def _check_source(self) -> None:
        k = self.cfg.kaynak
        if k.tur != "pencere":
            self.sourceStatus.emit(True, {"capture": "Capture kart", "video": "Video dosyası",
                                          "resim": "Resim"}.get(k.tur, k.tur))
            return
        found = winutil.find_window(k.pencere_adi) if winutil.IS_WIN else None
        self.sourceStatus.emit(bool(found), found[1] if found else "")

    def chiaki_path(self) -> str | None:
        return find_chiaki(getattr(self.cfg.kaynak, "chiaki_yolu", ""))

    def launch_chiaki(self) -> bool:
        path = self.chiaki_path()
        if not path:
            self._notice("chiaki-ng bulunamadı. Ayarlardan yerini seç ya da indir.")
            return False
        flags = getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen([path], cwd=str(Path(path).parent), creationflags=flags, close_fds=True)
        self._notice("chiaki-ng açılıyor... PS5'e ikinci hesapla bağlan.")
        return True

    # ------------------------------------------------------------------ TV
    def _tv(self, state: str, msg: str = "") -> None:
        self.tv_state = (state, msg)
        self.tvStatus.emit(state, msg)

    def tv_connect(self, host: str | None = None, force_install: bool = False) -> None:
        host = (host or self.cfg.tv.ip).split(":")[0]
        if not host:
            self._tv("yok", "TV adresi girilmedi")
            return

        def run() -> None:
            from . import tv
            try:
                self._tv("baglaniyor", f"{host} adresine bağlanılıyor...")
                server = tv.setup(host, self.cfg.sunucu.port, force_install=force_install, mode=self.cfg.tv.mod,
                                  on_prompt=lambda: self._tv("onay", "TV'ye bak: \"Hata ayıklamaya izin verilsin mi?\" "
                                                                    "sorusunda Her zaman izin ver + İzin ver"))
                self._tv("bagli", f"TV hazır ({host}). TV bu bilgisayara bağlanıyor: {server}")
            except Exception as e:  # noqa: BLE001
                self._tv("hata", str(e))
        threading.Thread(target=run, daemon=True, name="tv").start()

    def tv_scan(self) -> None:
        def run() -> None:
            from . import tv
            found = [(h, "klasik") for h in tv.scan()]
            try:
                import re
                out = tv.Adb().run("mdns", "services", timeout=10)
                for h in sorted(set(re.findall(r"_adb-tls-connect\S*\s+(\d+\.\d+\.\d+\.\d+)", out))):
                    if h not in [f[0] for f in found]:
                        found.append((h, "kablosuz"))
            except Exception:  # noqa: BLE001
                pass
            self.tvFound.emit(found)
        threading.Thread(target=run, daemon=True, name="tv-tara").start()

    def tv_pair(self, host_port: str, code: str) -> None:
        def run() -> None:
            from . import tv
            try:
                tv.Adb().pair(host_port, code)
                self._tv("baglaniyor", "Eşleştirildi, bağlanılıyor...")
                self.tv_connect(host_port.split(":")[0])
            except Exception as e:  # noqa: BLE001
                self._tv("hata", str(e))
        threading.Thread(target=run, daemon=True, name="tv-eslestir").start()

    def tv_test(self) -> None:
        """TV'de yerleşimi görmek için örnek altyazı gönder (3 sn)."""
        if not self.server:
            return
        it = DisplayItem("test", (0.33, 0.86, 0.67, 0.93), (0.1, 0.76, 0.9, 0.97), 0.031,
                         "This is a test subtitle.", "Bu bir deneme altyazısı. Yazı burada görünecek.",
                         "orta", "alt", 255, self.cfg.bolgeler[0].yazi_olcek if self.cfg.bolgeler else 1.3)
        self.server.show(it)
        threading.Timer(4.0, lambda: self.server.clear("test")).start()

    # ------------------------------------------------------------------ kare / test
    def grab_frame(self) -> None:
        pipe = self.pipe
        if pipe is not None and pipe.last_frame is not None:
            self.frameGrabbed.emit(pipe.last_frame.copy())
            return

        def run() -> None:
            from .capture import make_source
            got = {}
            ev = threading.Event()

            def on_frame(f, _t):  # noqa: ANN001
                if "f" not in got:
                    got["f"] = f.copy()
                    ev.set()
            try:
                src = make_source(self.cfg)
                src.start(on_frame)
                ev.wait(4)
                src.stop()
            except Exception as e:  # noqa: BLE001
                self._notice(str(e))
            self.frameGrabbed.emit(got.get("f"))
        threading.Thread(target=run, daemon=True, name="kare").start()

    def test_translation(self, text: str) -> None:
        if not self.engine:
            self._notice("Motorlar henüz hazır değil")
            return
        t0 = time.perf_counter()

        def cb(r):  # noqa: ANN001
            r.ms = (time.perf_counter() - t0) * 1000
            self.testResult.emit(r)
        self.engine.submit(text, "altyazi", cb)

    def shutdown(self) -> None:
        self.stop()
        if self.hotkeys:
            self.hotkeys.stop()


def open_path(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", path])
