"""Türkçe seslendirme (dublaj): gösterilen altyazının Türkçesini sesli okur.

- Ses: Microsoft'un doğal Türkçe sesleri (edge-tts; Ahmet erkek, Emel kadın), internet gerekir ve ücretsizdir.
  İnternet yoksa ya da hata olursa bilgisayarın kendi Türkçe sesi (Mac: say, Windows: SAPI) kullanılır.
- Konuşan adı biliniyorsa ("LUCIA: ...") sesi adına göre seçilir (Lucia kadın, Jason erkek); bilinmiyorsa anlatıcı.
- Yeni altyazı gelince okunmakta olan cümle kesilir (oyunun konuşmasının gerisinde kalmasın).
- Oyunun kendi diyalog sesini oyunun ses ayarlarından kısmak gerekir.

Nino Game Translator / CouchSubs dublajından esinlenildi (VoiceCast: ada göre ses, yeni satırda kesme).
"""

from __future__ import annotations

import logging
import queue
import re
import subprocess
import sys
import threading

log = logging.getLogger(__name__)

VOICES = {"erkek": "tr-TR-AhmetNeural", "kadin": "tr-TR-EmelNeural"}
SYSTEM_VOICES = {"darwin": {"erkek": "Yelda", "kadin": "Yelda"}}      # Mac'te Türkçe ses: Yelda (indirilmesi gerekebilir)
FEMALE = {"lucia", "cal's mom", "brianna", "boobie's wife", "jasmine", "nina", "maria", "sara", "sarah", "emma", "anna",
          "laura", "jessica", "ashley", "amanda", "michelle", "lisa", "karen", "linda", "nancy", "betty", "helen",
          "sandra", "donna", "carol", "ruth", "sharon", "kim", "tracey", "amanda", "lamar's girl", "she", "woman",
          "girl", "lady", "mom", "mother", "grandma", "sister", "officer jane", "dispatcher"}
MALE = {"jason", "cal", "boobie", "brian", "donnie", "dre'quan", "raul", "real dimez", "man", "guy", "dude", "cop",
        "officer", "dad", "father", "brother", "uncle", "grandpa"}
_SPEAKER = re.compile(r"^\s*([A-Za-zÇĞİÖŞÜçğıöşü'.\- ]{2,24})\s*[:：]\s*(.+)$")
_EMOJI = re.compile(r"[←-⯿-\U0001F000-\U0001FAFF]")


def split_speaker(text: str) -> tuple[str | None, str]:
    m = _SPEAKER.match(text)
    if m and len(m.group(1).split()) <= 3:
        return m.group(1).strip(), m.group(2).strip()
    return None, text.strip()


def gender_of(name: str | None) -> str:
    if not name:
        return "erkek"
    n = name.lower().strip()
    if n in FEMALE or n.split()[0] in FEMALE:
        return "kadin"
    return "erkek"


def speakable(text: str) -> str:
    """Okunacak hali: tuş simgeleri ve emoji atılır, birden çok boşluk teke iner."""
    text = _EMOJI.sub(" ", text).replace("…", ".").replace("\n", " ")
    return " ".join(text.split())


class Speaker:
    """Altyazıları sırayla okur; say(text) hemen döner. Yeni metin gelince okunan kesilir."""

    def __init__(self, rate: int = 10, enabled: bool = True):
        self.rate = rate
        self.enabled = enabled
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._device = None
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._last = ""
        self._edge_ok = True
        threading.Thread(target=self._run, daemon=True, name="seslendirme").start()

    def say(self, text: str) -> None:
        if not self.enabled:
            return
        name, body = split_speaker(text)
        body = speakable(body)
        if not body or body == self._last:
            return
        self._last = body
        self.interrupt()
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._q.put((body, gender_of(name)))

    def interrupt(self) -> None:
        with self._lock:
            if self._device is not None:
                try:
                    self._device.stop()
                except Exception:  # noqa: BLE001
                    pass
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()

    def close(self) -> None:
        self.enabled = False
        self.interrupt()
        self._q.put(None)

    # ------------------------------------------------------------------ iç
    def _run(self) -> None:
        while True:
            job = self._q.get()
            if job is None:
                return
            body, gender = job
            try:
                if self._edge_ok and self._speak_edge(body, gender):
                    continue
            except Exception as e:  # noqa: BLE001
                log.warning("Doğal ses kullanılamadı (%s); bilgisayarın sesi kullanılıyor", e)
                self._edge_ok = False
            try:
                self._speak_system(body, gender)
            except Exception as e:  # noqa: BLE001
                log.warning("Seslendirme yapılamadı: %s", e)

    def _speak_edge(self, body: str, gender: str) -> bool:
        import asyncio

        import edge_tts
        import miniaudio

        async def fetch() -> bytes:
            data = bytearray()
            com = edge_tts.Communicate(body, VOICES[gender], rate=f"{self.rate:+d}%")
            async for chunk in com.stream():
                if chunk.get("type") == "audio":
                    data += chunk["data"]
            return bytes(data)

        mp3 = asyncio.run(fetch())
        if not mp3 or self._q.qsize():          # bu arada yeni altyazı geldiyse eskisini hiç okuma
            return True
        decoded = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=24000)
        self._play(decoded.samples, 24000)
        return True

    def _play(self, samples, rate: int) -> None:  # noqa: ANN001
        import time

        import miniaudio
        total = len(samples)
        pos = {"i": 0}

        def gen():  # noqa: ANN202
            frames = yield b""
            while pos["i"] < total:
                chunk = samples[pos["i"]:pos["i"] + frames]
                pos["i"] += frames
                frames = yield chunk.tobytes() if hasattr(chunk, "tobytes") else bytes(chunk)

        dev = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=rate)
        stream = gen()
        next(stream)
        with self._lock:
            self._device = dev
        try:
            dev.start(stream)
            end = time.monotonic() + total / rate + 0.3
            while time.monotonic() < end and pos["i"] < total and dev.running:
                time.sleep(0.05)
        finally:
            with self._lock:
                self._device = None
            dev.close()

    def _speak_system(self, body: str, gender: str) -> None:
        if sys.platform == "darwin":
            voice = SYSTEM_VOICES["darwin"][gender]
            cmd = ["say", "-v", voice, "-r", str(175 + self.rate * 2), body]
        elif sys.platform == "win32":
            safe = body.replace("'", "''")
            script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                      "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'tr-TR' } | "
                      "Select-Object -First 1; if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
                      f"$s.Rate = {max(-10, min(10, self.rate // 10))}; $s.Speak('{safe}')")
            cmd = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script]
        else:
            cmd = ["espeak", "-v", "tr", body]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self._lock:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        self._proc.wait()
