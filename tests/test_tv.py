import json
import socket
import sys
import threading

import pytest

from altyazi import tv


@pytest.fixture
def fake(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    wrapper = tmp_path / "adb"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {tv.ROOT / 'tests' / 'fake_adb.py'} \"$@\"\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("ALTYAZI_ADB", str(wrapper))
    monkeypatch.setenv("FAKE_ADB_STATE", str(state))
    monkeypatch.setattr(tv.time, "sleep", lambda s: None)

    def set_state(**kw):
        state.write_text(json.dumps({"calls": [], **kw}))

    def get_state():
        return json.loads(state.read_text())
    return set_state, get_state


@pytest.fixture
def adb_port(monkeypatch):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    threading.Thread(target=lambda: [srv.accept() for _ in range(8)], daemon=True).start()
    monkeypatch.setattr(tv, "ADB_PORT", srv.getsockname()[1])
    return srv.getsockname()[1]


def test_classic_first_time_install_waits_for_approval(fake, adb_port):
    set_state, get_state = fake
    set_state(unauth_polls=2)
    prompts = []
    server = tv.setup("127.0.0.1", 8787, on_prompt=lambda: prompts.append(1))
    st = get_state()
    assert prompts == [1]                                   # kullanıcıya TV'ye bakması söylendi
    assert st["installed"]
    serial = f"127.0.0.1:{adb_port}"
    assert ["connect", serial] in st["calls"]
    assert any(c[:3] == ["-s", serial, "install"] for c in st["calls"])
    assert ["-s", serial, "shell", "appops set com.gta6altyazi.tv SYSTEM_ALERT_WINDOW allow"] in st["calls"]
    params = '{"server":"http://' + server + '"}'
    assert ["-s", serial, "shell",
            f"am start -n com.gta6altyazi.tv/.MainActivity --es params '{params}' --es displayMode inApp "
            f"--es host {server} --es mod katman"] in st["calls"]
    assert server.endswith(":8787")


def test_already_installed_same_version_skips_install(fake, adb_port):
    set_state, get_state = fake
    set_state(installed=True)
    tv.setup("127.0.0.1", 8787)
    assert not any("install" in c for c in get_state()["calls"])


def test_signature_mismatch_reinstalls(fake, adb_port):
    set_state, get_state = fake
    set_state(incompatible=True)
    tv.setup("127.0.0.1", 8787, force_install=True)
    st = get_state()
    assert st["uninstalled"] and st["installed"]


def test_wireless_debugging_found_via_mdns(fake, monkeypatch):
    set_state, get_state = fake
    monkeypatch.setattr(tv, "port_open", lambda *a, **k: False)   # 5555 kapalı (yeni Google TV)
    set_state(mdns="adb-XYZ\t_adb-tls-connect._tcp\t127.0.0.1:37001\n")
    tv.setup("127.0.0.1", 8787)
    assert ["connect", "127.0.0.1:37001"] in get_state()["calls"]


def test_unreachable_tv_gives_clear_error(fake, monkeypatch):
    set_state, _ = fake
    monkeypatch.setattr(tv, "port_open", lambda *a, **k: False)
    set_state()
    with pytest.raises(tv.TvError, match="Kablosuz hata ayıklama"):
        tv.setup("127.0.0.1", 8787)


def test_pair(fake):
    set_state, get_state = fake
    set_state()
    assert "Successfully paired" in tv.Adb().pair("127.0.0.1:41234", "123456")


def test_pair_finds_pairing_port_and_explains_errors(fake):
    """Ana ekrandaki port yazılsa da eşleştirme penceresinin portu ağdan bulunur; olmazsa ne yapılacağı söylenir."""
    set_state, get_state = fake
    set_state(pair_port=37123, mdns="adb-XYZ\t_adb-tls-pairing._tcp\t127.0.0.1:37123\n")
    assert "Successfully paired" in tv.Adb().pair("127.0.0.1:41234", "123 456")
    assert ["pair", "127.0.0.1:37123", "123456"] in get_state()["calls"]
    # pencere kapalı (mdns'te yok) ve yanlış port: "protocol fault" Türkçe açıklamaya çevrilir
    set_state(pair_port=37123)
    with pytest.raises(tv.TvError, match="küçük penceredeki adres:port"):
        tv.Adb().pair("127.0.0.1:41234", "123456")
    set_state(pair_code="111111")
    with pytest.raises(tv.TvError, match="kodu yanlış"):
        tv.Adb().pair("127.0.0.1:41234", "123456")
    with pytest.raises(tv.TvError, match="6 haneli"):
        tv.Adb().pair("127.0.0.1:41234", "12")
    # doğru port ama araya eski bir adb sunucusu girmiş: sunucu baştan başlatılıp yeniden denenir
    set_state(stale_server=True)
    assert "Successfully paired" in tv.Adb().pair("127.0.0.1:37123", "123456")
    assert ["kill-server"] in get_state()["calls"]


def test_no_overlay_permission_falls_back_to_hdmi_mode(fake, adb_port):
    set_state, get_state = fake
    set_state(installed=True, no_overlay=True)
    tv.setup("127.0.0.1", 8787)
    assert any("--es displayMode inApp" in c[-1] and c[-1].endswith("--es mod hdmi")
               for c in get_state()["calls"] if "shell" in c)


def test_older_tv_app_gets_updated(fake, adb_port):
    set_state, get_state = fake
    set_state(installed=True, version=1)
    tv.setup("127.0.0.1", 8787)
    assert any("install" in c for c in get_state()["calls"])
