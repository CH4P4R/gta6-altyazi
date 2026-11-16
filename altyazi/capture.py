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

    def start(self, on_frame: FrameCallback) -> None:
        from windows_capture import WindowsCapture

        kwargs = dict(cursor_capture=False, window_name=self.title)
        try:
            cap = WindowsCapture(draw_border=False, **kwargs)  # Windows 11: sarı çerçeve yok
        except Exception:  # noqa: BLE001  (Windows 10 çerçeveyi kapatmaya izin vermez)
            cap = WindowsCapture(**kwargs)

        @cap.event
        def on_frame_arrived(frame, control):  # noqa: ANN001
            # Kütüphane tamponu yeniden kullanır, bu yüzden kopyalıyoruz (~1 ms)
            on_frame(np.array(frame.frame_buffer, copy=True), time.perf_counter())

        @cap.event
        def on_closed():
            log.warning("Yakalanan pencere kapandı")

        self._control = cap.start_free_threaded()
        log.info("Pencere yakalanıyor: %s", self.title)

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
        backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            raise RuntimeError(f"Capture kart açılamadı (cihaz {index}). Liste: python -m altyazi kameralar")
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


def make_source(cfg) -> Source:  # noqa: ANN001
    k = cfg.kaynak
    if k.tur == "pencere":
        return WindowSource(k.pencere_adi)
    if k.tur == "capture":
        return CaptureCardSource(k.capture_cihaz, k.capture_genislik, k.capture_yukseklik, k.capture_fps)
    if k.tur == "video":
        return VideoSource(k.dosya)
    if k.tur == "resim":
        return ImageSource(k.dosya)
    raise ValueError(f"Bilinmeyen kaynak türü: {k.tur}")
