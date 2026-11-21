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

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from . import config as config_mod
from . import winutil
from .overlay import Bridge, OverlayWindow, Painter, VideoWindow
from .pipeline import DisplayItem, MultiSink, Pipeline

log = logging.getLogger(__name__)

CHIAKI_CANDIDATES = [
    "/Applications/chiaki-ng.app/Contents/MacOS/chiaki-ng",
    "~/Applications/chiaki-ng.app/Contents/MacOS/chiaki-ng",
    "~/Downloads/chiaki-ng.app/Contents/MacOS/chiaki-ng",
    r"%ProgramFiles%\chiaki-ng\chiaki.exe",
    r"%ProgramFiles%\chiaki-ng\chiaki-ng.exe",
    r"%LOCALAPPDATA%\Programs\chiaki-ng\chiaki.exe",
    r"%LOCALAPPDATA%\Programs\chiaki-ng\chiaki-ng.exe",
    r"%USERPROFILE%\Downloads\chiaki-ng\chiaki.exe",
]
CHIAKI_DOWNLOAD = "https://github.com/streetpea/chiaki-ng/releases/latest"


def find_chiaki(configured: str = "") -> str | None:
    for c in ([configured] if configured else []) + CHIAKI_CANDIDATES:
        if c.endswith(".app"):                       # macOS: .app paketi seçildiyse içindeki program
            c = str(Path(c) / "Contents" / "MacOS" / Path(c).stem)
        p = Path(os.path.expanduser(os.path.expandvars(c)))
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
    ps5Found = Signal(list)               # [ps5.Console]
    ps5Status = Signal(str, str)          # yerleşik Remote Play: baglaniyor | bagli | kopuk | durdu, mesaj
    ps5Paired = Signal(bool, str)         # PSN girişi / PS5 eşlemesi sonucu (başarılı mı, mesaj)
    ps5Consoles = Signal(list)            # remoteplay.ConsoleInfo listesi (eşleme ekranı)
    packProgress = Signal(str, float)     # (paket kimliği, 0..1; 1 bitti, -1 hata)
    packCatalog = Signal(list)            # CouchSubs paket sunucusundaki paketler [{id, title, entries, ...}]
    updateAvailable = Signal(dict)        # uygulamanın yeni sürümü: {version, url, size, notes}
    updateProgress = Signal(float)        # güncelleme indirme ilerlemesi (0..1; -1 hata)
    spendChanged = Signal()               # Claude harcama sayacı değişti (harcama.tracker)
    _uiCommand = Signal(str)              # başka iş parçacıklarından gelen ve ana iş parçacığında yapılması gereken işler

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
        self._user_stopped = False        # kullanıcı elle durdurduysa pencere açıkken kendiliğinden başlatma
        self._last_launch = 0.0
        self._ps5_busy = False
        self.ps5_state: str = ""          # "acik" | "uykuda" | "" (bilinmiyor)
        self.rp_state = ("durdu", "")     # yerleşik Remote Play oturumunun durumu
        self._uiCommand.connect(self._run_ui_command, Qt.QueuedConnection)
        from . import harcama, paths
        harcama.tracker.load(paths.data("harcama.json"))
        harcama.tracker.listener = self.spendChanged.emit
        self._start_server()
        self._start_hotkeys()
        self._src_timer = QTimer(self)
        self._src_timer.timeout.connect(self._check_source)
        self._src_timer.start(2000)
        self._ps5_timer = QTimer(self)
        self._ps5_timer.timeout.connect(self._auto_connect_tick)
        self._ps5_timer.start(10000)
        self.warmup()

    # ------------------------------------------------------------------ altyapı
    def _start_server(self) -> None:
        """TV/OBS/telefon sunucusunu aç. Port doluysa kimin tuttuğunu bul; kendiliğinden yeniden dene."""
        self.server_problem = ""
        if not self.cfg.sunucu.acik:
            return
        if self._try_server():
            return
        from . import tekkopya
        port = self.cfg.sunucu.port
        kind, pid, name = tekkopya.port_holder(port)
        log.warning("Port %s dolu: %s (pid %s, %s)", port, kind, pid, name)
        if kind == "gta6altyazi" and pid and pid != os.getpid():
            # Tek kopya denetimi geçildiyse bu, penceresi kapanmış ama süreci kapanmamış eski bir kopyadır
            log.warning("Penceresiz kalmış eski GTA6 Altyazı kopyası kapatılıyor (pid %s)", pid)
            tekkopya.kill(pid)
            for _ in range(20):
                time.sleep(0.25)
                if self._try_server():
                    return
        self.server_problem = tekkopya.holder_message(port, kind, name)
        self._server_tries = 0
        self._server_timer = QTimer(self)
        self._server_timer.timeout.connect(self._retry_server)
        self._server_timer.start(2000)

    def _try_server(self) -> bool:
        from .server import EventServer
        try:
            srv = EventServer(self.cfg.sunucu.port, self.cfg.tv.kalibrasyon, on_command=self.command)
            srv.screen_ms = max(3, int(self.cfg.kisayol.tam_ekran_sure)) * 1000
            srv.start()
        except OSError as e:
            log.info("Yerel sunucu açılamadı (port %s): %s", self.cfg.sunucu.port, e)
            return False
        self.server = srv
        self._apply_tv_style()
        return True

    def _retry_server(self) -> None:
        self._server_tries += 1
        if self._try_server():
            self._server_timer.stop()
            self.server_problem = ""
            log.info("Yerel sunucu açıldı (%d. denemede)", self._server_tries)
            if self.tv_state[0] == "hata":
                self._tv("yok", "")
            if self.pipe and self.pipe.sink is not None and hasattr(self.pipe.sink, "add"):
                self.pipe.sink.add(self.server)
            return
        if self._server_tries % 15 == 0:          # yarım dakikada bir: hâlâ kim tutuyor
            from . import tekkopya
            kind, _pid, name = tekkopya.port_holder(self.cfg.sunucu.port)
            self.server_problem = tekkopya.holder_message(self.cfg.sunucu.port, kind, name)

    def _start_hotkeys(self) -> None:
        from .hotkeys import Hotkeys
        k = self.cfg.kisayol
        self.hotkeys = Hotkeys({k.tam_ekran: lambda: self.command("tam_ekran"),
                                k.duraklat: lambda: self.command("duraklat")})
        self.hotkeys.start()

    def _set_state(self, s: str) -> None:
        self.state = s
        self.stateChanged.emit(s)
        if self.server:
            self.server.status(s)

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
            info["paket"] = sum(p.count for p in self.engine.packs.packs)
            self.engine_info = info
            self.enginesReady.emit(info)
            self._set_state("hazir")
            if not getattr(self, "_updates_checked", False):
                self._updates_checked = True
                threading.Thread(target=self._check_updates, daemon=True, name="guncelleme").start()
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
            source = make_source(self.cfg, on_state=self._rp_state, on_moved=self._rp_moved)
        except Exception as e:  # noqa: BLE001
            self._notice(str(e))
            if self.cfg.kaynak.tur == "remoteplay":
                self.ps5Status.emit("kopuk", str(e))
            return False
        painter = Painter(self.cfg.gosterim.yazi_tipi, self.cfg.gosterim.gecikme_goster)
        frame_sink = None
        if self.tv_only():
            self.window = None            # oyun TV'de: Türkçe yalnız TV'de (bilgisayar ekranına katman açılmaz)
        elif self.cfg.gosterim.mod == "pencere":
            self.window = VideoWindow(painter, self.bridge, self.cfg.gosterim.tam_ekran)
            frame_sink = self.window.push_frame
        else:
            self.window = OverlayWindow(painter, self.bridge, source.hwnd)
        if self.window is not None:
            self.window.show()
        self.pipe = Pipeline(self.cfg, MultiSink(self, self.server), self.rec, self.engine, source,
                             frame_sink=frame_sink)
        self.pipe.notice = self._notice
        self.pipe.start()
        winutil.keep_awake(True)
        self._set_state("calisiyor")
        self._notice("Çeviri başladı")
        # TV uygulaması kapatıldıysa (bağlı TV yoksa) yeniden aç; bağlantı sürüyorsa ikinciyi başlatma
        if self.cfg.tv.ip and self.cfg.tv.otomatik and self.server and self.server.tv_count == 0 \
                and self.tv_state[0] not in ("baglaniyor", "onay"):
            self.tv_connect()
        return True

    def tv_only(self) -> bool:
        """Oyun TV'de, görüntü yerleşik Remote Play'den: bilgisayar ekranında katman gerekmez."""
        return self.cfg.kaynak.tur == "remoteplay" and self.cfg.kaynak.oyun_yeri == "tv"

    # ------------------------------------------------------------------ yerleşik Remote Play
    def ps5_paired(self) -> bool:
        from . import remoteplay as rp
        return rp.RegisteredConsole.from_cfg(self.cfg.ps5) is not None and bool(rp.account_from_b64(self.cfg.ps5.hesap))

    def _rp_state(self, state: str, msg: str) -> None:
        self.rp_state = (state, msg)
        self.ps5Status.emit(state, msg)

    def _rp_moved(self, console) -> None:  # noqa: ANN001
        self._rp_new_host = console.host
        self._uiCommand.emit("ps5_tasindi")

    def psn_login_url(self) -> str:
        from . import remoteplay as rp
        return rp.PSN_LOGIN_URL

    def psn_finish(self, text: str) -> None:
        """Tarayıcıdan kopyalanan yönlendirme adresiyle (ya da elle yazılan hesap kimliğiyle) ikinci hesabı kaydet."""
        from . import remoteplay as rp
        text = (text or "").strip()

        def run() -> None:
            try:
                manual = rp.account_from_b64(text) if rp.PSN_REDIRECT not in text.lower() else None
                if manual is not None:
                    account = manual
                else:
                    url = rp.redirect_from_text(text)
                    if not url:
                        raise rp.PsnError("Bu bir Sony giriş adresi değil. Girişten sonra açılan "
                                          "remoteplay.dl.playstation.net sayfasının adresini kopyala.")
                    account = rp.account_id_from_redirect(url)
                self._psn_account = rp.account_b64(account)
                self._uiCommand.emit("psn_kaydet")
                self.ps5Paired.emit(True, "İkinci hesapla giriş tamam.")
            except Exception as e:  # noqa: BLE001
                log.warning("PSN girişi: %s", e)
                self.ps5Paired.emit(False, str(e))
        threading.Thread(target=run, daemon=True, name="psn").start()

    def ps5_search(self) -> None:
        def run() -> None:
            from . import remoteplay as rp
            try:
                self.ps5Consoles.emit(rp.discover(None, 3.0))
            except Exception as e:  # noqa: BLE001
                self._notice(f"PS5 aranamadı: {e}")
                self.ps5Consoles.emit([])
        threading.Thread(target=run, daemon=True, name="ps5-ara").start()

    def ps5_pair(self, host: str, pin_text: str) -> None:
        from . import remoteplay as rp
        pin = rp.parse_pin(pin_text)
        account = rp.account_from_b64(self.cfg.ps5.hesap)
        if account is None:
            self.ps5Paired.emit(False, "Önce ikinci hesapla giriş yap (1. adım).")
            return
        if pin is None:
            self.ps5Paired.emit(False, "Kod 8 haneli olmalı (PS5 ekranındaki sayı).")
            return
        if not host.strip():
            self.ps5Paired.emit(False, "PS5'i seç ya da IP adresini yaz.")
            return

        def run() -> None:
            try:
                console = rp.register(host.strip(), account, pin)
                self._paired_console = console
                self._uiCommand.emit("ps5_eslendi")
                self.ps5Paired.emit(True, f"PS5 eşlendi: {console.name}")
            except Exception as e:  # noqa: BLE001
                self.ps5Paired.emit(False, str(e))
        threading.Thread(target=run, daemon=True, name="ps5-esle").start()

    def stop(self) -> None:
        winutil.keep_awake(False)
        if getattr(self, "_speaker", None) is not None:
            self._speaker.interrupt()
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
        """Kullanıcının kendi bastığı başlat/durdur."""
        if self.state == "calisiyor":
            self._user_stopped = True
            self.stop()
        else:
            self._user_stopped = False
            self.start()

    # ------------------------------------------------------------------ güncellemeler
    def _check_updates(self) -> None:
        from . import updater
        problem = updater.last_update_problem()
        if problem:
            self.notice.emit(problem)
        o = self.cfg.otomatik
        if o.paket_guncelle:
            try:
                done = updater.update_packs()
                if done and self.engine:
                    self.engine.packs.reload()
                    names = ", ".join(f"{p.title} ({p.count:,} satır)".replace(",", ".") for p in done)
                    self.notice.emit(f"Hazır paket güncellendi: {names}")
            except Exception as e:  # noqa: BLE001
                log.warning("Paket güncellemesi başarısız: %s", e)
        if o.surum_denetle:
            rel = updater.latest_release()
            if updater.newer_than_current(rel):
                self.update_info = rel
                self.updateAvailable.emit(rel)

    def install_update(self) -> None:
        """Yeni sürümü indir, sessiz kur; kurulum programı kapatır ve yeniden açar."""
        from . import updater
        rel = getattr(self, "update_info", None)
        if not rel:
            return

        def run() -> None:
            try:
                setup = updater.download_setup(rel, lambda f: self.updateProgress.emit(min(f, 0.99)))
                self.updateProgress.emit(1.0)
                self.notice.emit("Güncelleme kuruluyor: program kapanıp 1 dakika içinde yeni sürümle açılacak.")
                updater.run_setup(setup, rel.get("version", ""))
                self._uiCommand.emit("cik")
            except Exception as e:  # noqa: BLE001
                log.warning("Güncelleme kurulamadı: %s", e)
                self.notice.emit(f"Güncelleme kurulamadı: {e}")
                self.updateProgress.emit(-1.0)

        self.stop()
        threading.Thread(target=run, daemon=True, name="guncelle").start()

    def _run_ui_command(self, name: str) -> None:
        if name == "cik":
            from PySide6.QtWidgets import QApplication
            self.shutdown()
            QApplication.quit()
        elif name == "toggle":
            self.toggle()
        elif name == "baglan":
            self.launch_chiaki(stream=True)
        elif name == "ps5_kaydet" and getattr(self, "_found_ps5", None):
            cfg = self.edit_config()
            cfg.otomatik.ps5_adi, cfg.otomatik.ps5_ip = self._found_ps5.name, self._found_ps5.ip
            self.apply_config(cfg)
            self._notice(f"PS5 kaydedildi: {self._found_ps5.name}")
        elif name == "psn_kaydet" and getattr(self, "_psn_account", None):
            cfg = self.edit_config()
            cfg.ps5.hesap = self._psn_account
            self.apply_config(cfg)
        elif name == "ps5_eslendi" and getattr(self, "_paired_console", None):
            cfg = self.edit_config()
            for k, v in self._paired_console.to_cfg().items():
                setattr(cfg.ps5, k, v)
            cfg.kaynak.tur = "remoteplay"
            cfg.kaynak.oyun_yeri = "tv"
            self.apply_config(cfg)
            self._notice(f"PS5 eşlendi: {self._paired_console.name}. Görüntü artık arka planda alınacak.")
            self._check_source()
        elif name == "ps5_tasindi" and getattr(self, "_rp_new_host", None):
            cfg = self.edit_config()
            cfg.ps5.ip = self._rp_new_host
            self.apply_config(cfg)
        elif name == "ps5_baslat":
            if self.state == "hazir" and not self._user_stopped:
                self._notice("PS5 açık, çeviri kendiliğinden başlıyor")
                self.start()
        elif name == "baglan_oto":
            self._notice("PS5 açık, chiaki kendiliğinden bağlanıyor...")
            self.launch_chiaki(stream=True)

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
        if name == "baslat_durdur":
            running = self.state == "calisiyor"
            if self.state not in ("hazir", "calisiyor"):
                return {"mesaj": "Uygulama hazırlanıyor, birkaç saniye sonra tekrar dene", "durum": self.state}
            self._uiCommand.emit("toggle")
            return {"mesaj": "Durduruluyor..." if running else "Başlatılıyor...", "durum": self.state}
        if name == "baglan":
            self._uiCommand.emit("baglan")
            return {"mesaj": "chiaki-ng açılıyor..."}
        if name == "durum":
            from . import remoteplay
            return {"durum": self.state, "ps5": self.ps5_state, "duraklatildi": bool(pipe and pipe.paused),
                    "remoteplay": remoteplay.available(),
                    "mesaj": {"calisiyor": "Çeviri açık", "hazir": "Çeviri kapalı",
                              "hazirlaniyor": "Hazırlanıyor"}.get(self.state, self.state)}
        return {"mesaj": f"Bilinmeyen komut: {name}"}

    # Sink arayüzü (Pipeline buraya yazar; başka iş parçacığından gelir, sinyaller kuyruğa alınır)
    def show(self, item: DisplayItem) -> None:
        self._maybe_speak(item)
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

    def _maybe_speak(self, item: DisplayItem) -> None:
        """Dublaj: altyazının son (en kaliteli) çevirisi okunur; hızlı ön çeviri kalite katmanı varsa okunmaz."""
        g = self.cfg.gosterim
        if not g.seslendir or item.zone != "altyazi" or not item.text:
            return
        from .translate import REFINED
        if self.engine is not None and self.engine.refine is not None and item.quality < REFINED:
            return
        sp = getattr(self, "_speaker", None)
        if sp is None:
            from .seslendirme import Speaker
            sp = self._speaker = Speaker(rate=g.ses_hizi)
        sp.rate = g.ses_hizi
        sp.say(item.text)

    def set_overlay(self, items: list[dict]) -> None:
        """Ekran yazılarının Türkçeleri bilgisayardaki katmana da (monitörde oynayan için)."""
        self.bridge.overlaid.emit(items)

    def avg_latency(self) -> float | None:
        return sum(self.latencies) / len(self.latencies) if self.latencies else None

    # ------------------------------------------------------------------ ayarlar
    def _apply_tv_style(self) -> None:
        """TV uygulamasının görünümü: Türkçe, İngilizce satırın 'yazı ölçeği' katı boyda ve onu tam örterek."""
        if not self.server:
            return
        main = next((b for b in self.cfg.bolgeler if b.ad == "altyazi"), None)
        scale = main.yazi_olcek if main else 1.3
        opacity = round((main.kutu_opaklik if main else 255) / 255 * 100)
        self.server.set_tv_style(lineScale=float(scale), background=opacity,
                                 displayMode="overlay" if self.cfg.tv.mod == "katman" else "inApp")

    def apply_config(self, cfg: config_mod.Config, explicit_keys: bool = False) -> None:
        old = self.cfg
        config_mod.save(cfg, explicit_keys=explicit_keys)    # boş anahtar dolu olanı silmez (save korur)
        self.cfg = cfg
        if self.server:
            x, y, w, h = cfg.tv.kalibrasyon
            self.server.tv = {"x": x, "y": y, "w": w, "h": h}
            self._apply_tv_style()
        engines_changed = old.ceviri != cfg.ceviri or old.ocr != cfg.ocr
        running = self.state == "calisiyor"
        if old.kisayol != cfg.kisayol:
            if self.hotkeys:
                self.hotkeys.stop()
            self._start_hotkeys()
        if old.otomatik.windows_ile_baslat != cfg.otomatik.windows_ile_baslat:
            winutil.set_autostart(cfg.otomatik.windows_ile_baslat)
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
        if k.tur == "remoteplay":
            if self.state != "calisiyor":
                if self.ps5_paired():
                    st = getattr(self, "ps5_state", "")
                    msg = {"acik": "PS5 açık. Çeviri başlayınca arka planda bağlanılır.",
                           "uykuda": "PS5 dinlenme modunda. Açılınca çeviri kendiliğinden başlar."}.get(
                        st, f"{self.cfg.ps5.ad or 'PS5'} eşli. Çeviri başlayınca arka planda bağlanılır.")
                    self.ps5Status.emit("durdu", msg)
                else:
                    self.ps5Status.emit("yok", "")
            return
        if k.tur != "pencere":
            self.sourceStatus.emit(True, {"capture": "Capture kart", "video": "Video dosyası",
                                          "resim": "Resim"}.get(k.tur, k.tur))
            return
        found = winutil.find_window(k.pencere_adi) if winutil.CAN_FIND_WINDOWS else None
        self.sourceStatus.emit(bool(found), found[1] if found else "")
        self._auto_source(bool(found))

    def _auto_source(self, found: bool) -> None:
        """chiaki penceresi açılınca başlat, kapanınca durdur (TV günleri: kasada kimse yok)."""
        if not found:
            self._user_stopped = False
            if self.state == "calisiyor":
                self._notice("chiaki penceresi kapandı, çeviri durduruldu")
                self.stop()
            return
        if self.cfg.otomatik.chiaki_gorunce_baslat and self.state == "hazir" and not self._user_stopped:
            self._notice("chiaki bağlandı, çeviri kendiliğinden başlıyor")
            self.start()

    def _auto_connect_tick(self) -> None:
        """PS5 açılınca chiaki'yi kendiliğinden bağla; yerleşik Remote Play'de çeviriyi kendiliğinden başlat."""
        if self.cfg.kaynak.tur == "remoteplay":
            self._auto_rp_tick()
            return
        o = self.cfg.otomatik
        if not o.ps5_acilinca_baglan or self._ps5_busy or self.cfg.kaynak.tur != "pencere":
            return
        if time.time() - self._last_launch < 45:
            return
        if winutil.CAN_FIND_WINDOWS and winutil.find_window(self.cfg.kaynak.pencere_adi):
            return

        def run() -> None:
            from . import ps5
            self._ps5_busy = True
            try:
                consoles = ps5.discover(1.2, targets=[o.ps5_ip] if o.ps5_ip else None)
                mine = [c for c in consoles if not o.ps5_adi or c.name == o.ps5_adi] or consoles
                self.ps5_state = ("acik" if any(c.awake for c in mine) else "uykuda") if mine else ""
                if any(c.awake for c in mine):
                    self._last_launch = time.time()
                    self._uiCommand.emit("baglan_oto")
            except Exception:  # noqa: BLE001
                log.debug("PS5 keşfi başarısız", exc_info=True)
            finally:
                self._ps5_busy = False
        threading.Thread(target=run, daemon=True, name="ps5").start()

    def _auto_rp_tick(self) -> None:
        """TV günleri: PS5 açılınca çeviri kendiliğinden başlasın (kasada kimse yok). Elle durdurulduysa başlatma."""
        if self._ps5_busy or self.state == "calisiyor" or not self.ps5_paired():
            return

        def run() -> None:
            from . import remoteplay as rp
            self._ps5_busy = True
            try:
                found = rp.discover(self.cfg.ps5.ip, 1.5)
                mine = [c for c in found if not self.cfg.ps5.ad or c.name == self.cfg.ps5.ad] or found
                self.ps5_state = ("acik" if any(c.awake for c in mine) else "uykuda") if mine else ""
                if self.ps5_state == "uykuda":
                    self._user_stopped = False        # ertesi gün PS5 açılınca yine kendiliğinden başlasın
                if self.ps5_state == "acik" and self.cfg.ps5.acilinca_baslat:
                    self._uiCommand.emit("ps5_baslat")
            except Exception:  # noqa: BLE001
                log.debug("PS5 araması başarısız", exc_info=True)
            finally:
                self._ps5_busy = False
        threading.Thread(target=run, daemon=True, name="ps5-oto").start()

    def find_ps5(self, save: bool = False) -> None:
        """PS5'i ağda ara; save=True ise bulunanın adını ve IP'sini ayarlara yaz."""
        def run() -> None:
            from . import ps5
            try:
                consoles = ps5.discover(2.0)
                if save and consoles:
                    self._found_ps5 = consoles[0]
                    self._uiCommand.emit("ps5_kaydet")
                self.ps5Found.emit(consoles)
            except Exception as e:  # noqa: BLE001
                self._notice(f"PS5 aranamadı: {e}")
                self.ps5Found.emit([])
        threading.Thread(target=run, daemon=True, name="ps5-bul").start()

    def chiaki_path(self) -> str | None:
        return find_chiaki(getattr(self.cfg.kaynak, "chiaki_yolu", ""))

    def chiaki_args(self, stream: bool) -> list[str]:
        """chiaki-ng komut satırı: 'stream <PS5 adı> <ip>' doğrudan bağlanır (chiaki-ng gui/src/main.cpp)."""
        o = self.cfg.otomatik
        if not (stream and o.ps5_adi and o.ps5_ip):
            return []
        args = ["stream", o.ps5_adi, o.ps5_ip, "--exit-app-on-stream-exit"]
        if o.chiaki_tam_ekran:
            args.append("--fullscreen")
        return args

    def launch_chiaki(self, stream: bool = False) -> bool:
        path = self.chiaki_path()
        if not path:
            self._notice("chiaki-ng bulunamadı. Ayarlardan yerini seç ya da indir.")
            return False
        if winutil.CAN_FIND_WINDOWS and winutil.find_window(self.cfg.kaynak.pencere_adi):
            self._notice("chiaki-ng zaten açık")
            return True
        args = self.chiaki_args(stream)
        flags = getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen([path, *args], cwd=str(Path(path).parent), creationflags=flags, close_fds=True)
        self._last_launch = time.time()
        self._notice("chiaki-ng PS5'e bağlanıyor..." if args else
                     "chiaki-ng açılıyor... PS5'e ikinci hesapla bağlan.")
        return True

    # ------------------------------------------------------------------ TV
    def _tv(self, state: str, msg: str = "") -> None:
        self.tv_state = (state, msg)
        self.tvStatus.emit(state, msg)

    def tv_connect(self, host: str | None = None, force_install: bool = False) -> None:
        raw = (host or self.cfg.tv.ip or "").strip()
        host, _, cport = raw.partition(":")
        wport = int(cport) if cport.isdigit() else None       # Kablosuz hata ayıklama ekranındaki port (yazıldıysa)
        if not host:
            self._tv("yok", "TV adresi girilmedi")
            return
        if self.server is None:
            self._tv("hata", getattr(self, "server_problem", "") or
                     "TV'ye altyazı gönderen yerel sunucu kapalı (Ayarlar › Sunucu).")
            return
        if not hasattr(self, "_tv_lock"):
            self._tv_lock = threading.Lock()
        if not self._tv_lock.acquire(blocking=False):
            log.info("TV bağlantısı zaten sürüyor; ikinci istek yok sayıldı")
            return

        def run() -> None:
            try:
                self._tv_run(host, wport, force_install)
            finally:
                self._tv_lock.release()
        threading.Thread(target=run, daemon=True, name="tv").start()

    def _tv_wait_client(self, server: str, before: int, timeout: float = 30.0) -> None:
        """TV uygulaması açıldıktan sonra gerçekten bu bilgisayara bağlandı mı? Bağlanmadıysa sebebini söyle."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.server and self.server.tv_count > 0:
                return
            time.sleep(0.5)
        try:
            fw = self.firewall_status()
        except Exception:  # noqa: BLE001
            fw = "bilinmiyor"
        if fw == "ortak":
            raise RuntimeError("TV uygulaması açıldı ama bu bilgisayara bağlanamadı: Windows bu ağı 'Ortak' sayıyor ve "
                               "TV'yi engelliyor. Televizyon sayfasındaki '3 · Bağlantı izni' kısmında İzin ver'e bas "
                               "(ev ağını 'Özel' yapar; Windows soracak, Evet de), sonra yeniden Bağlan'a bas.")
        if fw == "eksik":
            raise RuntimeError("TV uygulaması açıldı ama bu bilgisayara bağlanamadı: Windows güvenlik duvarı engelliyor. "
                               "Televizyon sayfasındaki '3 · Bağlantı izni' kısmında İzin ver'e bas (Windows soracak, "
                               "Evet de), sonra yeniden Bağlan'a bas.")
        raise RuntimeError(f"TV uygulaması açıldı ama bu bilgisayara ({server}) bağlanamadı. TV ile bilgisayar aynı "
                           "modemde mi? Modemde 'misafir ağı / AP izolasyonu' açıksa kapat. Televizyon sayfasında "
                           "güvenlik duvarı iznini ver ve yeniden Bağlan'a bas.")

    def _tv_run(self, host: str, wport: int | None, force_install: bool) -> None:
        from . import tv
        t = self.cfg.tv
        before = self.server.tv_count if self.server else 0
        try:
            self._tv("baglaniyor", f"{host} adresine bağlanılıyor...")
            if t.marka == "lg":
                from . import tv_lg
                if not t.lg_parola:
                    raise RuntimeError("LG Developer Mode ekranındaki parolayı (passphrase) yaz.")
                server = tv_lg.setup(host, t.lg_parola, self.cfg.sunucu.port, force_install=force_install)
            elif t.marka == "samsung" and t.tizen_yolu:
                # Gelişmiş: Tizen Studio klasörü seçildiyse onun araçları ve sertifika profiliyle kur
                from . import tv_samsung
                self._tv("baglaniyor", "Samsung TV'ye bağlanılıyor, uygulama Tizen Studio ile imzalanıp kuruluyor "
                                       "(1-2 dk)...")
                server = tv_samsung.setup(host, t.samsung_profil, t.tizen_yolu)
            elif t.marka == "samsung":
                # Varsayılan: Tizen Studio'suz, doğrudan (sdb + Samsung sertifikası + imza Python'da)
                from .samsung import setup_direct

                def login_needed(_url: str) -> None:
                    if not force_install:    # kendiliğinden bağlanırken habersiz tarayıcı açma
                        raise RuntimeError("Samsung hesabıyla bir kez giriş gerekiyor: Televizyon sayfasında "
                                           "\"Bağlan, kur ve başlat\"a bas.")
                    self._tv("onay", "Tarayıcıda açılan Samsung sayfasında hesabına gir (yalnız ilk sefer, 5 dk "
                                     "içinde). Giriş bitince kurulum kendiliğinden sürer.")

                server = setup_direct(host, force_install=force_install,
                                      progress=lambda msg: self._tv("baglaniyor", msg),
                                      on_login_needed=login_needed, server_port=self.cfg.sunucu.port)
            else:
                server = tv.setup(host, self.cfg.sunucu.port, force_install=force_install, mode=t.mod, port=wport,
                                  progress=lambda msg: self._tv("baglaniyor", msg),
                                  on_prompt=lambda: self._tv("onay", "TV'ye bak: \"Hata ayıklamaya izin verilsin mi?\" "
                                                                    "sorusunda Her zaman izin ver + İzin ver"))
            self._tv("baglaniyor", f"TV uygulaması açıldı; bu bilgisayara ({server}) bağlanması bekleniyor...")
            self._tv_wait_client(server, before)
            self._tv("bagli", f"TV bağlandı ({host}). Altyazılar TV'de görünecek.")
        except Exception as e:  # noqa: BLE001
            log.exception("TV bağlantısı başarısız")
            self._tv("hata", str(e) or f"{type(e).__name__} (ayrıntı altyazi.log'da)")

    def tv_scan(self) -> None:
        def run() -> None:
            try:
                self._tv_scan()
            except Exception:  # noqa: BLE001
                log.exception("TV taraması başarısız")
                self.tvFound.emit([])
        threading.Thread(target=run, daemon=True, name="tv-tara").start()

    def _tv_scan(self) -> None:
        from . import tv
        marka = self.cfg.tv.marka
        if marka in ("lg", "samsung"):
            port = 9922 if marka == "lg" else 26101
            self.tvFound.emit([(h, marka.upper() if marka == "lg" else "Samsung") for h in tv.scan(port)])
            return
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

    def tv_pair(self, host_port: str, code: str) -> None:
        def run() -> None:
            from . import tv
            host = host_port.strip().split(":")[0] or self.cfg.tv.ip
            # USB hata ayıklama açıksa TV 5555'te bekler: eşleştirmeye hiç gerek yok, doğrudan bağlan
            if host and tv.port_open(host, tv.ADB_PORT, 1.5):
                self._tv("baglaniyor", "Eşleştirme gerekmiyor (USB hata ayıklama açık), doğrudan bağlanılıyor...")
                self.tv_connect(host, force_install=True)
                return
            try:
                tv.Adb().pair(host_port, code)
                self._tv("baglaniyor", "Eşleştirildi, bağlanılıyor...")
                self.tv_connect(host)
            except Exception as e:  # noqa: BLE001
                self._tv("hata", f"{e}\nEn kolayı: TV'de Geliştirici seçenekleri › USB hata ayıklama'yı aç ve "
                                 "eşleştirmeden Bağlan'a bas.")
        threading.Thread(target=run, daemon=True, name="tv-eslestir").start()

    def tv_test(self) -> None:
        """TV'de yerleşimi görmek için örnek altyazı gönder (3 sn)."""
        if not self.server:
            return
        it = DisplayItem("altyazi", (0.33, 0.86, 0.67, 0.93), (0.1, 0.76, 0.9, 0.97), 0.031,
                         "This is a test subtitle.", "Bu bir deneme altyazısı. Yazı burada görünecek.",
                         "orta", "alt", 255, self.cfg.bolgeler[0].yazi_olcek if self.cfg.bolgeler else 1.3)
        self.server.show(it)
        threading.Timer(4.0, lambda: self.server.clear("altyazi")).start()

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
                ev.wait(30 if self.cfg.kaynak.tur == "remoteplay" else 4)
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

    # ------------------------------------------------------------------ çeviri paketleri
    def pack_list(self) -> list:
        return list(self.engine.packs.packs) if self.engine else []

    def import_pack(self, src: str) -> str:
        import shutil
        from . import paths, packs
        pack = packs.load(Path(src))                      # önce geçerli mi bak
        dest = paths.data("paketler") / Path(src).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
        if self.engine:
            self.engine.packs.reload()
        return f"{pack.title}: {pack.count} satır eklendi"

    # ------------------------------------------------------------------ güvenlik duvarı
    def firewall_status(self) -> str:
        """'tamam' | 'eksik' | 'ortak' (ağ Ortak profilde) | 'bilinmiyor'"""
        if winutil.network_is_public():
            return "ortak"
        ok = winutil.firewall_ok()
        return "bilinmiyor" if ok is None else ("tamam" if ok else "eksik")

    def firewall_allow(self, done=None) -> None:  # noqa: ANN001
        """Yönetici izniyle güvenlik duvarı izni (ağ Ortak ise Özel de yapılır); sonuç done(metin) ile bildirilir."""
        def run() -> None:
            public = bool(winutil.network_is_public())
            self._notice("Windows yönetici izni soracak: Evet de.")
            res = winutil.firewall_allow(make_private=public)
            msg = {"tamam": "✓ İzin verildi" + (" ve ev ağı 'Özel' yapıldı." if public else ".") +
                            " TV artık bu bilgisayara bağlanabilir.",
                   "iptal": "İzin verilmedi: Windows'un sorusuna 'Evet' demen gerekiyor. Yeniden 'İzin ver'e bas.",
                   "hata": "Windows kuralı yazmadı. Bilgisayarda başka bir güvenlik programı (antivirüs güvenlik "
                           "duvarı) varsa GTA6 Altyazı'ya oradan izin ver.",
                   "desteklenmiyor": "Bu yalnız Windows'ta gerekir."}[res]
            log.info("Güvenlik duvarı izni: %s", res)
            self._notice(msg)
            if done:
                done(msg)
        threading.Thread(target=run, daemon=True, name="guvenlik-duvari").start()

    def load_pack_catalog(self) -> None:
        """CouchSubs paket sunucusunun listesini arka planda al (GTA 6 paketi burada)."""
        from . import packs

        def run() -> None:
            cat = packs.own_catalog()                # önce kendi GitHub sürümümüz
            if not cat:
                cat = packs.couchsubs_catalog()      # yanıt yoksa doğrudan CouchSubs
            self._cs_catalog = {p["id"]: p for p in cat}
            self.packCatalog.emit(cat)

        threading.Thread(target=run, daemon=True, name="paket-liste").start()

    def download_pack(self, pack_id: str) -> None:
        """pack_id: GameTranslator kataloğundaki kimlik ya da CouchSubs için 'cs:<kimlik>'."""
        from . import paths, packs

        def run() -> None:
            try:
                prog = lambda f: self.packProgress.emit(pack_id, min(f, 0.99))  # noqa: E731
                if pack_id.startswith("cs:"):
                    info = getattr(self, "_cs_catalog", {}).get(pack_id[3:])
                    if not info:
                        raise RuntimeError("CouchSubs paket listesi alınamadı; internet bağlantısını kontrol et.")
                    dl = packs.download_own if info.get("own") else packs.download_couchsubs
                    pack = dl(info, paths.data("paketler"), prog)
                else:
                    pack = packs.download(pack_id, paths.data("paketler"), prog)
                if self.engine:
                    self.engine.packs.reload()
                self.notice.emit(f"{pack.title}: {pack.count:,} satır hazır".replace(",", "."))
                self.packProgress.emit(pack_id, 1.0)
            except Exception as e:  # noqa: BLE001
                log.warning("Paket indirilemedi: %s", e)
                self.notice.emit(f"Paket indirilemedi: {e}")
                self.packProgress.emit(pack_id, -1.0)

        threading.Thread(target=run, daemon=True, name="paket").start()

    def export_pack(self, dest: str) -> int:
        from . import packs
        if not self.engine:
            return 0
        return packs.export_cache(self.engine.cache.rows(), Path(dest))

    def shutdown(self) -> None:
        if getattr(self, "_shut", False):
            return
        self._shut = True
        from .harcama import tracker
        tracker.save()
        self.stop()
        if self.hotkeys:
            self.hotkeys.stop()


def open_path(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
