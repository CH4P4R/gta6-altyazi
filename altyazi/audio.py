"""Capture kartın sesini düşük gecikmeyle hoparlöre/kulaklığa aktarır (pencere modunda gerekli)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def list_inputs() -> list[tuple[int, str]]:
    import sounddevice as sd

    return [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]


def start_passthrough(device_hint: str = ""):
    """Giriş cihazını bul ve varsayılan çıkışa aktar. Akış nesnesini döndürür (kapatmak için .close())."""
    import sounddevice as sd

    inputs = list_inputs()
    hints = [device_hint.lower()] if device_hint else ["capture", "elgato", "avermedia", "hd60", "live gamer",
                                                       "usb video", "hdmi", "cam link"]
    dev = next((i for i, n in inputs for h in hints if h and h in n.lower()), None)
    if dev is None:
        log.warning("Capture kart ses girişi bulunamadı. Mevcut girişler: %s", [n for _, n in inputs])
        return None
    info = sd.query_devices(dev)
    ch = min(2, info["max_input_channels"])
    rate = int(info["default_samplerate"]) or 48000

    def cb(indata, outdata, _frames, _time, status):  # noqa: ANN001
        outdata[:] = indata

    stream = sd.Stream(device=(dev, None), samplerate=rate, channels=ch, dtype="float32",
                       latency="low", callback=cb)
    stream.start()
    log.info("Ses aktarımı: %s → varsayılan çıkış (%.0f ms)", info["name"], stream.latency[1] * 1000)
    return stream
