"""Görüntü kaynakları. Hepsi her karede on_frame(frame_bgr_veya_bgra, zaman) çağırır.

- WindowSource: chiaki-ng / PS Remote Play penceresini Windows Graphics Capture ile
  yakalar. Pencerenin üstünde başka pencere (bizim overlay dahil) olsa bile sadece
  pencerenin kendi içeriğini alır, bu yüzden Türkçe yazımız tekrar OCR'a girmez.
- CaptureCardSource: USB capture kart (UVC). Tampon 1 kareye indirilir, gecikme ~1 kare.
- VideoSource / ImageSource: kayıttan test ve ayar yapmak için.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import cv2
import numpy as np

log = logging.getLogger(__name__)

FrameCallback = Callable[[np.ndarray, float], None]


class Source:
    hwnd: int | None = None  # overlay konumlandırma için (sadece pencere kaynağı)

    def start(self, on_frame: FrameCallback) -> None: ...
    def stop(self) -> None: ...


class WindowSource(Source):
    def __init__(self, title_part: str):
        from . import winutil

        found = winutil.find_window(title_part)
        if not found:
            raise RuntimeError(f"Başlığında '{title_part}' geçen pencere bulunamadı. "
                               "Açık pencereleri görmek için: python -m altyazi pencereler")
        self.hwnd, self.title = found
        self._control = None
        self._crop: tuple[int, int, int, int] | None = None
        self._crop_at = 0.0
        self._crop_size = (0, 0)

    def start(self, on_frame: FrameCallback) -> None:
        from windows_capture import WindowsCapture

        def build(target: dict, border: bool | None):  # noqa: ANN202
            cap = WindowsCapture(cursor_capture=False, draw_border=border, **target)

            @cap.event
            def on_frame_arrived(frame, control):  # noqa: ANN001
                buf = frame.frame_buffer
                box = self._crop_box(buf.shape[1], buf.shape[0])
                if box:
                    x0, y0, x1, y1 = box
                    buf = buf[y0:y1, x0:x1]
                # Kütüphane tamponu yeniden kullanır, bu yüzden kopyalıyoruz (~1 ms)
                on_frame(np.array(buf, copy=True), time.perf_counter())

            @cap.event
            def on_closed():
                log.warning("Yakalanan pencere kapandı")

            return cap.start_free_threaded()

        # Pencere kimliği (HWND) başlık değişse de doğru pencereyi tutar; eski sürümlerde başlıkla dene.
        # Windows 10 sarı çerçeveyi kapatmaya izin vermeyebilir; o zaman çerçeveli yakala.
        last_error = None
        for target in ({"window_hwnd": self.hwnd}, {"window_name": self.title}):
            for border in (False, None):
                try:
                    self._control = build(target, border)
                    log.info("Pencere yakalanıyor: %s", self.title)
                    return
                except TypeError as e:      # bu sürümde window_hwnd yok
                    last_error = e
                    break
                except Exception as e:  # noqa: BLE001
                    last_error = e
        raise RuntimeError(f"Pencere yakalanamadı: {last_error}")

    def _crop_box(self, fw: int, fh: int) -> tuple[int, int, int, int] | None:
        """chiaki pencere modundaysa karede başlık çubuğu ve siyah bantlar da olur. Okuma alanları ve TV'deki yazının
        yeri oyun görüntüsüne göre hesaplandığı için kare yalnız oyun görüntüsüne kırpılır (yarım saniyede bir hesap)."""
        from . import winutil

        now = time.perf_counter()
        if now - self._crop_at < 0.5 and self._crop_size == (fw, fh):
            return self._crop
        self._crop_at, self._crop_size = now, (fw, fh)
        fb, cb = winutil.frame_bounds(self.hwnd), winutil.client_bounds(self.hwnd)
        if not fb:
            self._crop = None
            return None
        # Kare pencerenin tamamını mı (başlık çubuğu dahil) yoksa yalnız iç alanı mı kapsıyor? Orana bakarak seç.
        captured = fb
        if cb and cb[3] > cb[1] and fb[3] > fb[1]:
            ar = fw / fh
            if abs(ar - (cb[2] - cb[0]) / (cb[3] - cb[1])) < abs(ar - (fb[2] - fb[0]) / (fb[3] - fb[1])):
                captured = cb
        inner = winutil.video_bounds(self.hwnd)
        self._crop = winutil.crop_in_frame(fw, fh, captured, inner) if inner else None
        return self._crop

    def stop(self) -> None:
        if self._control is not None:
            try:
                self._control.stop()
            except Exception:  # noqa: BLE001
                pass


class _ThreadSource(Source):
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, on_frame: FrameCallback) -> None:
        self._thread = threading.Thread(target=self._run, args=(on_frame,), daemon=True, name="kaynak")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self, on_frame: FrameCallback) -> None:
        raise NotImplementedError


class CaptureCardSource(_ThreadSource):
    def __init__(self, index: int, width: int, height: int, fps: int):
        super().__init__()
        import sys
        backend = (cv2.CAP_DSHOW if sys.platform == "win32" else
                   cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY)
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            raise RuntimeError(f"Capture kart açılamadı (cihaz {index}). Liste: python -m altyazi kameralar")
        if sys.platform == "win32":
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"NV12"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) != width:
            # NV12 desteklenmiyorsa MJPG dene (çoğu ucuz kart 1080p60'ı sadece MJPG ile verir)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap = cap
        log.info("Capture kart: %dx%d @ %.0f fps", cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                 cap.get(cv2.CAP_PROP_FRAME_HEIGHT), cap.get(cv2.CAP_PROP_FPS))

    def _run(self, on_frame: FrameCallback) -> None:
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.005)
                continue
            on_frame(frame, time.perf_counter())
        self.cap.release()


class VideoSource(_ThreadSource):
    """Kaydedilmiş oyun videosunu gerçek zamanlı hızında oynatır (ayar ve test için)."""

    def __init__(self, path: str, loop: bool = True):
        super().__init__()
        self.path, self.loop = path, loop

    def _run(self, on_frame: FrameCallback) -> None:
        cap = cv2.VideoCapture(self.path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        period = 1.0 / fps
        nxt = time.perf_counter()
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                if not self.loop:
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            nxt += period
            delay = nxt - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            on_frame(frame, time.perf_counter())


class ImageSource(_ThreadSource):
    def __init__(self, path: str, fps: int = 30):
        super().__init__()
        self.frame = cv2.imread(path)
        if self.frame is None:
            raise RuntimeError(f"Resim açılamadı: {path}")
        self.period = 1.0 / fps

    def _run(self, on_frame: FrameCallback) -> None:
        while not self._stop.is_set():
            on_frame(self.frame, time.perf_counter())
            time.sleep(self.period)


DEMO_LINES = [
    "Lucia: We need to get out of Vice City. Now!",
    "Jason: Stay close to me and keep your voice down.",
    "The bridge is gone. We need another way across.",
    "Lucia: You said this would be easy.",
    "Jason: I never said that. Get in the car!",
    "We should reach the lighthouse before dark.",
]


class DemoSource(_ThreadSource):
    """Deneme modu (CouchSubs): konsol olmadan, gün batımı sahnesi üstünde sırayla İngilizce altyazılar. Program bunları
    gerçek oyundaki gibi okur, çevirir, bilgisayar ekranında ve TV bağlıysa TV'de gösterir."""

    title = "Deneme modu"

    def __init__(self, lines: list[str] | None = None, fps: int = 15, hold: float = 4.0, gap: float = 1.0,
                 size: tuple[int, int] = (1280, 720)):
        super().__init__()
        self.lines = lines or DEMO_LINES
        self.period, self.hold, self.gap = 1.0 / fps, hold, gap
        self.w, self.h = size
        self.background = self._scene()

    def _scene(self) -> np.ndarray:
        w, h = self.w, self.h
        y = np.linspace(0, 1, h)[:, None]
        top, mid, low = np.array([56, 19, 29.]), np.array([94, 42, 107.]), np.array([63, 96, 200.])   # BGR
        rows = np.where(y < 0.55, top + (mid - top) * (y / 0.55), mid + (low - mid) * ((y - 0.55) / 0.45))
        img = np.ascontiguousarray(np.broadcast_to(rows[:, None, :], (h, w, 3)), dtype=np.uint8)
        cv2.circle(img, (int(w * 0.68), int(h * 0.6)), int(h * 0.16), (120, 190, 255), -1)
        cv2.rectangle(img, (0, int(h * 0.74)), (w, h), (26, 12, 20), -1)
        for i in range(6):                               # palmiyeler
            x = int(w * (0.07 + i * 0.17))
            cv2.line(img, (x, int(h * 0.75)), (x + 8, int(h * 0.42)), (22, 10, 16), 6)
            for dx, dy in ((-60, 20), (-35, -10), (35, -10), (60, 20), (0, -25)):
                cv2.line(img, (x + 8, int(h * 0.42)), (x + 8 + dx, int(h * 0.42) + dy + 12), (22, 10, 16), 4)
        return img

    def frame_at(self, t: float) -> np.ndarray:
        img = self.background.copy()
        cycle = self.hold + self.gap
        i = int(t // cycle) % len(self.lines)
        if (t % cycle) < self.hold:
            text = self.lines[i]
            font, scale, th = cv2.FONT_HERSHEY_DUPLEX, 1.05 * self.w / 1280, max(2, int(2 * self.w / 1280))
            (tw, tht), _ = cv2.getTextSize(text, font, scale, th)
            x, y = (self.w - tw) // 2, int(self.h * 0.9)
            cv2.putText(img, text, (x, y), font, scale, (0, 0, 0), th + 5, cv2.LINE_AA)       # oyun yazısı gibi kontur
            cv2.putText(img, text, (x, y), font, scale, (255, 255, 255), th, cv2.LINE_AA)
        return img

    def _run(self, on_frame: FrameCallback) -> None:
        t0 = time.perf_counter()
        while not self._stop.is_set():
            now = time.perf_counter()
            on_frame(self.frame_at(now - t0), now)
            time.sleep(self.period)


class RemotePlaySource(Source):
    """PS5 görüntüsü yerleşik Remote Play ile (ikinci PSN hesabı, chiaki penceresi gerekmez)."""

    def __init__(self, ps5_cfg, on_state=None, on_moved=None):  # noqa: ANN001
        from . import remoteplay as rp
        console = rp.RegisteredConsole.from_cfg(ps5_cfg)
        account = rp.account_from_b64(ps5_cfg.hesap)
        if console is None or account is None:
            raise RuntimeError("PS5 henüz eşlenmedi. Ana ekranda PS5 kartındaki 'PS5'i bağla' düğmesine bas.")
        if not rp.available():
            raise RuntimeError("Remote Play bileşeni bu kurulumda yok. Programı yeniden kur.")
        self.title = console.name or console.host
        self.session = rp.StreamSession(console, account, ps5_cfg.giris_sifresi, on_state=on_state, on_moved=on_moved)

    def start(self, on_frame: FrameCallback) -> None:
        self.session.on_frame = on_frame
        self.session.start()

    def stop(self) -> None:
        self.session.on_frame = None
        self.session.stop()


def make_source(cfg, on_state=None, on_moved=None) -> Source:  # noqa: ANN001
    k = cfg.kaynak
    if k.tur == "remoteplay":
        return RemotePlaySource(cfg.ps5, on_state, on_moved)
    if k.tur == "pencere":
        import sys
        if sys.platform == "darwin":
            from .capture_mac import MacWindowSource
            return MacWindowSource(k.pencere_adi)
        return WindowSource(k.pencere_adi)
    if k.tur == "capture":
        return CaptureCardSource(k.capture_cihaz, k.capture_genislik, k.capture_yukseklik, k.capture_fps)
    if k.tur == "video":
        return VideoSource(k.dosya)
    if k.tur == "resim":
        return ImageSource(k.dosya)
    raise ValueError(f"Bilinmeyen kaynak türü: {k.tur}")
