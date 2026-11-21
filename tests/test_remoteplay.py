"""Yerleşik Remote Play: PSN girişi, PS5 eşleme kodu, hata eşlemeleri, yeniden bağlanma kuralları ve yerel kütüphane."""

import ctypes
import threading
import time
import types

import numpy as np
import pytest

from altyazi import remoteplay as rp

NATIVE = rp.available()
needs_native = pytest.mark.skipif(not NATIVE, reason="couchsubs_native derlenmemiş (native/build)")


# ------------------------------------------------------------------ PSN girişi
def test_login_url_has_remote_play_client():
    u = rp.PSN_LOGIN_URL
    assert u.startswith("https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/authorize?")
    assert "client_id=ba495a24-818c-472b-b12d-ff231c1b5745" in u
    assert "redirect_uri=https://remoteplay.dl.playstation.net/remoteplay/redirect" in u
    assert "scope=psn:clientapp%20referenceDataService:countryConfig.read" in u


def test_redirect_from_pasted_text():
    url = "https://remoteplay.dl.playstation.net/remoteplay/redirect?code=v3.AbC&cid=1"
    assert rp.redirect_from_text(f'  "{url}"\n') == url
    assert rp.redirect_from_text(f"adres: {url} tamam") == url
    assert rp.redirect_from_text("https://remoteplay.dl.playstation.net/remoteplay/redirect?x=1") is None
    assert rp.redirect_from_text("https://example.com/?code=1") is None
    err = "https://remoteplay.dl.playstation.net/remoteplay/redirect?error=access_denied&error_description=No+way"
    assert rp.redirect_from_text(err) == err


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, token_resp, info_resp):
        self.token_resp, self.info_resp, self.calls = token_resp, info_resp, []

    def post(self, url, **kw):
        self.calls.append(("post", url, kw))
        return self.token_resp

    def get(self, url, **kw):
        self.calls.append(("get", url, kw))
        return self.info_resp


def test_account_id_exchange():
    s = FakeSession(FakeResp(200, {"access_token": "tok/en"}), FakeResp(200, {"user_id": "1234567890123456789"}))
    acc = rp.account_id_from_redirect("https://remoteplay.dl.playstation.net/remoteplay/redirect?code=abc", s)
    assert acc == (1234567890123456789).to_bytes(8, "little")
    post = s.calls[0]
    assert post[2]["auth"] == (rp.PSN_CLIENT_ID, rp.PSN_CLIENT_SECRET)
    assert "grant_type=authorization_code" in post[2]["data"] and "code=abc" in post[2]["data"]
    assert s.calls[1][1].endswith("/tok%2Fen")
    assert rp.account_from_b64(rp.account_b64(acc)) == acc


def test_account_id_errors_are_turkish():
    with pytest.raises(rp.PsnError, match="access_denied"):
        rp.account_id_from_redirect("https://remoteplay.dl.playstation.net/remoteplay/redirect?error=access_denied")
    s = FakeSession(FakeResp(400, {"error": "invalid_grant", "error_description": "Invalid authorization code"}), None)
    with pytest.raises(rp.PsnError, match="invalid_grant.*yeniden giriş"):
        rp.account_id_from_redirect("https://remoteplay.dl.playstation.net/remoteplay/redirect?code=old", s)
    s = FakeSession(FakeResp(429, {}), None)
    with pytest.raises(rp.PsnError, match="çok fazla"):
        rp.account_id_from_redirect("https://remoteplay.dl.playstation.net/remoteplay/redirect?code=x", s)
    assert rp.account_from_b64("AbCdEfGhIjk=") is not None
    assert rp.account_from_b64("kısa") is None


# ------------------------------------------------------------------ eşleme
def test_parse_pin():
    assert rp.parse_pin("1234 5678") == 12345678
    assert rp.parse_pin("1234-5678") == 12345678
    assert rp.parse_pin("١٢٣٤٥٦٧٨") == 12345678          # başka yazı sistemlerinin rakamları
    assert rp.parse_pin("1234567") is None
    assert rp.parse_pin("1234a678") is None
    assert rp.parse_pin(None) is None


def test_registration_failures():
    f = rp.registration_failure
    assert f(0x80108B02, []) == "WrongAccount"
    assert f(0x80108B09, []) == "WrongCode"
    assert f(0x80108B10, []) == "InUse"
    assert f(None, ["Regist failed to receive search response: Connection refused"]) == "PairingClosed"
    assert f(None, ["Regist failed to connect for request"]) == "ConnectFailed"
    assert f(None, ["Regist search failed"]) == "NoAnswer"
    assert f(None, ["Regist failed to receive response HTTP header"]) == "NoReply"
    assert f(None, ["failed to send search: Can't assign requested address"]) == "NoFreePort"
    assert "kullanıcı olarak ekli" in str(rp.RegistrationError("WrongAccount"))


def test_registered_console_cfg_roundtrip():
    from altyazi.config import Ps5Cfg
    c = rp.RegisteredConsole("192.168.1.30", "PS5-123", b"0123abcd" + b"\0" * 8, bytes(range(16)))
    assert c.wake_credential == 0x0123ABCD
    cfg = Ps5Cfg(**c.to_cfg())
    back = rp.RegisteredConsole.from_cfg(cfg)
    assert back == c
    assert rp.RegisteredConsole.from_cfg(Ps5Cfg()) is None
    assert rp.RegisteredConsole.from_cfg(Ps5Cfg(ip="1.2.3.4", anahtar="zz", morning="00")) is None


# ------------------------------------------------------------------ oturum kuralları
def test_reconnect_policy():
    p = rp.ReconnectPolicy()
    assert [p.next_delay() for _ in range(7)] == [2, 4, 8, 16, 32, 60, 60]
    p.reset()
    assert p.next_delay(in_use=True) == 8
    p.reset()
    p.connected(0)
    p.ended(10)                       # kısa süren oturum: en az 8 sn
    assert p.next_delay() == 8
    p.connected(100)
    p.ended(100 + 400)                # uzun süren oturum: baştan (ama yine en az 8)
    assert p.next_delay() == 8


def test_wake_policy_and_quality_and_watchdog():
    w = rp.WakePolicy()
    assert w.decide(True) == "connect" and w.decide(None) == "connect" and w.decide(False) == "wake"
    w.streamed = True
    assert w.decide(False) == "wait"   # oyuncu PS5'i kapattı: yeniden açılmaz
    q = rp.QualityFallback()
    assert not q.dropped(0) and q.dropped(100) and q.lowered and not q.dropped(200)
    q2 = rp.QualityFallback()
    assert not q2.dropped(0) and not q2.dropped(700)
    d = rp.PictureWatchdog()
    assert d.stalled(100) is None
    d.connected(0)
    assert d.stalled(5) is None and d.stalled(9) is not None      # ilk görüntü 8 sn
    d.picture(10)
    assert d.stalled(20) is None and d.stalled(26) is not None    # sonra 15 sn


def test_disconnect_reasons():
    assert rp.from_native(rp.QUIT_IN_USE, None).kind == "in_use"
    assert rp.from_native(rp.QUIT_PSN_REGIST_FAILED, None).kind == "regist"
    hint = rp.session_request_hint("Reported Application Reason: 0x80108b12 (Remote Play disabled)")
    assert hint.kind == "rejected" and "Etkinleştir" in hint.message()
    assert rp.session_request_hint("Reported Application Reason: 0x80108b26").kind == "regist"
    assert rp.session_request_hint("Session request connect failed eventually.").kind == "network"
    assert rp.from_native(rp.QUIT_OTHER, "Unknown Session Request Error", hint).kind == "rejected"
    assert rp.from_native(rp.QUIT_OTHER, "Unknown Session Request Error").kind == "rejected"
    assert "başka bir cihazda" in rp.Disconnect("in_use").message()
    assert "tamamen kapatıp" in rp.Disconnect("crashed").message()
    assert rp.normalized_passcode(" 1234 ") == "1234" and rp.normalized_passcode("12") is None


def test_frame_conversion_bgra_with_stride():
    got = []
    s = rp.StreamSession.__new__(rp.StreamSession)
    s._watchdog = rp.PictureWatchdog()
    s.on_frame = lambda f, t: got.append(f)
    w, h, stride = 3, 2, 16                        # satır başına 4 piksel yer, 3'ü dolu
    raw = (ctypes.c_uint8 * (stride * h))(*range(stride * h))
    s._frame(ctypes.cast(raw, ctypes.POINTER(ctypes.c_uint8)), w, h, stride)
    f = got[0]
    assert f.shape == (2, 3, 4) and f.dtype == np.uint8
    assert list(f[1, 0]) == [16, 17, 18, 19]
    raw[16] = 99
    assert f[1, 0, 0] == 16                        # kopya: tampon değişince kare değişmez


# ------------------------------------------------------------------ yerel kütüphane
@needs_native
def test_native_discover_empty_and_register_refused():
    assert rp.discover("127.0.0.1", 0.5) == []
    with pytest.raises(rp.RegistrationError) as e:
        rp.register("127.0.0.1", b"\x01" * 8, 12345678)
    assert e.value.kind in ("PairingClosed", "NoAnswer", "ConnectFailed")


@needs_native
def test_native_session_reports_unreachable_and_retries():
    states = []
    ev = threading.Event()

    def on_state(s, m):
        states.append((s, m))
        if s == "kopuk":
            ev.set()

    c = rp.RegisteredConsole("127.0.0.1", "", b"0123abcd" + b"\0" * 8, bytes(16))
    s = rp.StreamSession(c, b"\x01" * 8, on_state=on_state)
    s.start()
    assert ev.wait(60), states        # macOS'ta libchiaki bağlantıyı birkaç kez dener (20 sn yetmedi)
    s.stop()
    assert states[0][0] == "baglaniyor"
    assert any(st == "kopuk" and "ulaşılamıyor" in m for st, m in states)


def test_source_requires_pairing():
    from altyazi.capture import make_source
    from altyazi.config import Config
    cfg = Config()
    cfg.kaynak.tur = "remoteplay"
    with pytest.raises(RuntimeError, match="eşlenmedi"):
        make_source(cfg)


def test_controller_pairing_flow(monkeypatch):
    """Eşleme bitince ayarlara yazılır, kaynak 'remoteplay', oyun yeri 'tv' olur."""
    from altyazi.app import AppController
    from altyazi.config import Config

    saved = []
    cfg = Config()
    cfg.ps5.hesap = rp.account_b64(b"\x02" * 8)
    fake = types.SimpleNamespace(cfg=cfg, results=[])
    fake.ps5Paired = types.SimpleNamespace(emit=lambda ok, m: fake.results.append((ok, m)))
    fake._uiCommand = types.SimpleNamespace(emit=lambda n: AppController._run_ui_command(fake, n))
    fake.edit_config = lambda: cfg
    fake.apply_config = lambda c: saved.append(c)
    fake._notice = lambda m: None
    fake._check_source = lambda: None
    monkeypatch.setattr(rp, "register", lambda host, acc, pin: rp.RegisteredConsole(
        host, "PS5-777", b"0123abcd" + b"\0" * 8, bytes(16)))
    AppController.ps5_pair(fake, "192.168.1.30", "1234 5678")
    end = time.time() + 5
    while not fake.results and time.time() < end:
        time.sleep(0.05)
    assert fake.results == [(True, "PS5 eşlendi: PS5-777")]
    assert cfg.ps5.ip == "192.168.1.30" and cfg.ps5.ad == "PS5-777"
    assert cfg.kaynak.tur == "remoteplay" and cfg.kaynak.oyun_yeri == "tv"
    fake.results.clear()
    AppController.ps5_pair(fake, "192.168.1.30", "123")
    assert fake.results and not fake.results[0][0] and "8 haneli" in fake.results[0][1]


def test_ps5_dialog_builds(monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from altyazi.config import Config
    from altyazi.ui.ps5_dialog import Ps5Dialog

    class Sig:
        def connect(self, f):
            pass

    calls = []
    cfg = Config()
    ctl = types.SimpleNamespace(cfg=cfg, ps5Paired=Sig(), ps5Consoles=Sig(), ps5_paired=lambda: False,
                                ps5_search=lambda: calls.append("ara"), psn_login_url=lambda: rp.PSN_LOGIN_URL,
                                psn_finish=lambda t: calls.append(("psn", t)))
    d = Ps5Dialog(ctl)
    assert "ara" in calls
    d._on_consoles([rp.ConsoleInfo("192.168.1.30", "PS5-777", True)])
    assert d._host() == "192.168.1.30"
    d.paste.setText("https://remoteplay.dl.playstation.net/remoteplay/redirect?code=abc")
    d._save_account()
    assert ("psn", "https://remoteplay.dl.playstation.net/remoteplay/redirect?code=abc") in calls
    d._on_result(False, "Sony girişi reddetti")
    assert "reddetti" in d.acc_state.text()
