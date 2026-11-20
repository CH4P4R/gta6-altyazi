"""macOS pencere yakalama: chiaki-ng penceresini ScreenCaptureKit ile yakalar.

Windows'taki gibi yalnız pencerenin kendi içeriği alınır; üstündeki Türkçe katman (bizim pencere) kareye girmez, Türkçe
yazı tekrar OCR'a girmez. macOS ilk seferde "Ekran Kaydı" izni ister (Sistem Ayarları › Gizlilik ve Güvenlik).
ScreenCaptureKit kullanılamazsa (eski macOS ya da hata) CGWindowListCreateImage ile saniyede ~15 kare alınır.
"""

from __future__ import annotations

import logging
import threading
import time

import numpy as np

from .capture import FrameCallback, Source

log = logging.getLogger(__name__)


def _pixel_buffer_to_array(pb) -> np.ndarray | None:  # noqa: ANN001
    import Quartz

    Quartz.CVPixelBufferLockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
    try:
        h = Quartz.CVPixelBufferGetHeight(pb)
        w = Quartz.CVPixelBufferGetWidth(pb)
        bpr = Quartz.CVPixelBufferGetBytesPerRow(pb)
        base = Quartz.CVPixelBufferGetBaseAddress(pb)
        if not base or not h or not w:
            return None
        buf = base.as_buffer(bpr * h)
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, bpr // 4, 4)[:, :w]
        return np.array(arr, copy=True)          # BGRA; tampon geri verilmeden kopyala
    finally:
        Quartz.CVPixelBufferUnlockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)


def _cgimage_to_array(img) -> np.ndarray | None:  # noqa: ANN001
    import Quartz

    if img is None:
        return None
    w, h = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
    bpr = Quartz.CGImageGetBytesPerRow(img)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    arr = np.frombuffer(bytes(data), dtype=np.uint8).reshape(h, bpr // 4, 4)[:, :w]
    return np.array(arr, copy=True)


class MacWindowSource(Source):
    def __init__(self, title_part: str):
        from . import macutil

        found = macutil.find_window(title_part)
        if not found:
            raise RuntimeError(f"'{title_part}' penceresi bulunamadı. chiaki-ng açık ve PS5'e bağlı mı?")
        self.hwnd, self.title = found
        if macutil.screen_capture_allowed() is False:
            macutil.request_screen_capture()
            raise RuntimeError("macOS 'Ekran Kaydı' izni gerekiyor: Sistem Ayarları › Gizlilik ve Güvenlik › Ekran ve "
                               "Sistem Ses Kaydı'nda GTA6 Altyazı'yı aç, sonra programı kapatıp yeniden aç.")
        self._stream = None
        self._output = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._crop: tuple[int, int, int, int] | None = None
        self._crop_at = 0.0
        self._crop_size = (0, 0)

    # --------------------------------------------------------------- kırpma (Windows'taki gibi)
    def _crop_box(self, fw: int, fh: int) -> tuple[int, int, int, int] | None:
        from . import macutil, winutil

        now = time.perf_counter()
        if now - self._crop_at < 0.5 and self._crop_size == (fw, fh):
            return self._crop
        self._crop_at, self._crop_size = now, (fw, fh)
        fb = macutil.frame_bounds(self.hwnd)
        inner = winutil.video_bounds(self.hwnd)
        self._crop = winutil.crop_in_frame(fw, fh, fb, inner) if fb and inner else None
        return self._crop

    def _emit(self, on_frame: FrameCallback, arr: np.ndarray) -> None:
        box = self._crop_box(arr.shape[1], arr.shape[0])
        if box:
            x0, y0, x1, y1 = box
            arr = arr[y0:y1, x0:x1]
        on_frame(arr, time.perf_counter())

    # --------------------------------------------------------------- başlat
    def start(self, on_frame: FrameCallback) -> None:
        try:
            self._start_sck(on_frame)
            log.info("Pencere yakalanıyor (ScreenCaptureKit): %s", self.title)
        except Exception as e:  # noqa: BLE001
            log.warning("ScreenCaptureKit kullanılamadı (%s); yedek yöntemle yakalanıyor", e)
            self._thread = threading.Thread(target=self._poll, args=(on_frame,), daemon=True, name="kaynak-mac")
            self._thread.start()

    def _start_sck(self, on_frame: FrameCallback) -> None:
        import objc
        import Quartz
        import ScreenCaptureKit as SCK
        from Foundation import NSObject

        try:
            import libdispatch
            queue = libdispatch.dispatch_queue_create(b"gta6altyazi.capture", None)
        except ImportError:
            queue = None

        got: dict = {}
        ready = threading.Event()

        def on_content(content, error):  # noqa: ANN001
            got["content"], got["error"] = content, error
            ready.set()

        SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            True, True, on_content)
        if not ready.wait(10) or got.get("content") is None:
            raise RuntimeError(f"ekran içeriği alınamadı: {got.get('error')}")
        window = next((w for w in got["content"].windows() if int(w.windowID()) == int(self.hwnd)), None)
        if window is None:
            raise RuntimeError("chiaki penceresi ScreenCaptureKit listesinde yok")

        flt = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
        cfg = SCK.SCStreamConfiguration.alloc().init()
        frame = window.frame()
        try:                                          # Retina: nokta başına piksel (genelde 2)
            import AppKit
            scale = max(float(s.backingScaleFactor()) for s in AppKit.NSScreen.screens())
        except Exception:  # noqa: BLE001
            scale = 2.0
        width, height = frame.size.width * scale, frame.size.height * scale
        if width > 1920:                              # OCR için 1920 genişlik yeter (CouchSubs da böyle)
            height *= 1920 / width
            width = 1920
        cfg.setWidth_(max(2, int(round(width))))
        cfg.setHeight_(max(2, int(round(height))))
        if hasattr(cfg, "setScalesToFit_"):
            cfg.setScalesToFit_(True)
        cfg.setPixelFormat_(Quartz.kCVPixelFormatType_32BGRA)
        cfg.setShowsCursor_(False)
        cfg.setQueueDepth_(3)
        import CoreMedia
        cfg.setMinimumFrameInterval_(CoreMedia.CMTimeMake(1, 30))

        source = self

        class Output(NSObject):
            def stream_didOutputSampleBuffer_ofType_(self, stream, sample, kind):  # noqa: N802, ANN001
                if source._stop.is_set() or kind != SCK.SCStreamOutputTypeScreen:
                    return
                try:
                    pb = CoreMedia.CMSampleBufferGetImageBuffer(sample)
                    if pb is None:
                        return
                    arr = _pixel_buffer_to_array(pb)
                    if arr is not None:
                        source._emit(on_frame, arr)
                except Exception:  # noqa: BLE001
                    log.exception("Kare işlenemedi")

        objc.registerMetaDataForSelector(b"NSObject", b"stream:didOutputSampleBuffer:ofType:",
                                         {"arguments": {4: {"type": b"q"}}})
        self._output = Output.alloc().init()
        self._stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(flt, cfg, None)
        ok, err = self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._output, SCK.SCStreamOutputTypeScreen, queue, None)
        if not ok:
            raise RuntimeError(f"yakalama çıktısı eklenemedi: {err}")
        started = threading.Event()
        result: dict = {}

        def on_start(error):  # noqa: ANN001
            result["error"] = error
            started.set()

        self._stream.startCaptureWithCompletionHandler_(on_start)
        if not started.wait(10) or result.get("error") is not None:
            raise RuntimeError(f"yakalama başlatılamadı: {result.get('error')}")

    def _poll(self, on_frame: FrameCallback) -> None:
        import Quartz

        opts = Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageBestResolution
        while not self._stop.is_set():
            t = time.perf_counter()
            img = Quartz.CGWindowListCreateImage(Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow,
                                                 int(self.hwnd), opts)
            arr = _cgimage_to_array(img)
            if arr is not None:
                self._emit(on_frame, arr)
            time.sleep(max(0.0, 1 / 15 - (time.perf_counter() - t)))

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stopCaptureWithCompletionHandler_(lambda _e: None)
            except Exception:  # noqa: BLE001
                pass
