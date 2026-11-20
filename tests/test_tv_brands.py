import io
import json

import pytest

from altyazi import tv_lg, tv_samsung


# ------------------------------------------------------------------ LG
class FakeOut:
    def __init__(self, text):
        self.buf = io.StringIO(text)
        self.channel = type("C", (), {"close": lambda self: None})()

    def readline(self):
        return self.buf.readline()

    def read(self):
        return self.buf.read().encode()


class FakeSSH:
    def __init__(self, install_reply, version_after="0.3.1"):
        self.cmds, self.uploads = [], []
        self.install_reply = install_reply
        self.version = None
        self.version_after = version_after

    def exec_command(self, cmd, timeout=None):
        self.cmds.append(cmd)
        if "luna-send-pub -i" in cmd and "appInstallService" in cmd:
            # tek komut: başlat, bekle, kurulum günlüğünü bas (CouchSubs InstallCommand)
            if "installed" in self.install_reply:
                self.version = self.version_after
            return None, FakeOut(self.install_reply), FakeOut("")
        if cmd.startswith("wc -c"):
            return None, FakeOut(str(self.uploaded_size)), FakeOut("")
        if "appinfo.json" in cmd:
            return None, FakeOut(json.dumps({"version": self.version}) if self.version else ""), FakeOut("")
        if "applicationManager/launch" in cmd:
            return None, FakeOut('{"returnValue": true}'), FakeOut("")
        return None, FakeOut(""), FakeOut("")

    uploaded_size = 0

    def get_transport(self):
        ssh = self

        class Ch:
            def settimeout(self, t):
                pass

            def exec_command(self, cmd):
                self.remote = cmd.split("'")[1]

            def sendall(self, data):
                ssh.uploaded_size = len(data)

            def shutdown_write(self):
                ssh.uploads.append(self.remote)

            def recv_exit_status(self):
                return 0

            def close(self):
                pass

        return type("T", (), {"open_session": lambda self: Ch()})()

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fast_lg(monkeypatch):
    monkeypatch.setattr(tv_lg.time, "sleep", lambda s: None)
    monkeypatch.setattr(tv_lg.LgTv, "renew_devmode", lambda self: None)


@pytest.fixture
def ipk(tmp_path, monkeypatch):
    p = tmp_path / "com.gta6altyazi.tv_0.3.1_all.ipk"
    p.write_bytes(b"ipk")
    monkeypatch.setattr(tv_lg, "ipk_path", lambda: p)
    return p


def test_lg_ipk_version(ipk):
    assert tv_lg.ipk_version(ipk) == "0.3.1"


def test_lg_wrong_passphrase(tmp_path):
    import paramiko
    key = paramiko.RSAKey.generate(1024)
    buf = io.StringIO()
    key.write_private_key(buf, password="ABC123")
    data = buf.getvalue().encode()
    assert tv_lg.load_key("ABC123", data).get_bits() == 1024
    with pytest.raises(tv_lg.LgError, match="parola"):
        tv_lg.load_key("YANLIS", data)


def test_lg_key_server_unreachable():
    with pytest.raises(tv_lg.LgError, match="Key Server"):
        tv_lg.fetch_key("127.0.0.1")


def test_lg_setup_installs_and_launches_with_host(ipk, monkeypatch):
    fake = FakeSSH('{"returnValue":true}\n{"details":{"state":"installing"}}\n{"details":{"state":"installed"}}\n')
    monkeypatch.setattr(tv_lg.LgTv, "connect", lambda self: setattr(self, "ssh", fake))
    server = tv_lg.setup("127.0.0.1", "ABC123", 8787)
    assert fake.uploads == ["/media/developer/temp/com.gta6altyazi.tv_0.3.1_all.ipk"]
    install = next(c for c in fake.cmds if "appInstallService/dev/install" in c)
    assert '"ipkUrl":"/media/developer/temp/com.gta6altyazi.tv_0.3.1_all.ipk"' in install
    assert "sleep 150 </dev/null 2>/dev/null |" in install and "kill $L" in install
    launch = next(c for c in fake.cmds if "applicationManager/launch" in c)
    assert f'"server": "http://{server}"' in launch and server.endswith(":8787")


def test_lg_same_version_skips_install(ipk, monkeypatch):
    fake = FakeSSH("")
    fake.version = "0.3.1"
    monkeypatch.setattr(tv_lg.LgTv, "connect", lambda self: setattr(self, "ssh", fake))
    tv_lg.setup("127.0.0.1", "ABC123", 8787)
    assert not fake.uploads


def test_lg_install_failure_is_reported(ipk, monkeypatch):
    fake = FakeSSH('{"returnValue":false,"errorText":"FAILED_IPKG_INSTALL"}\n')
    monkeypatch.setattr(tv_lg.LgTv, "connect", lambda self: setattr(self, "ssh", fake))
    with pytest.raises(tv_lg.LgError, match="kurulamadı"):
        tv_lg.setup("127.0.0.1", "ABC123", 8787)


def test_lg_install_command_returns_promptly_in_a_real_shell(tmp_path):
    """Gerçek sh ile: kurulum bitince komut hemen döner (eski hali 'sleep' yüzünden SSH kanalını 120 sn açık tutuyordu)."""
    import shutil
    import subprocess
    import time
    if not shutil.which("sh"):
        pytest.skip("sh yok")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    luna = fake_bin / "luna-send-pub"
    luna.write_text('#!/bin/sh\necho \'{"returnValue":true}\'\nsleep 1\necho \'{"details":{"state":"installed"}}\'\n'
                    'cat >/dev/null\n')
    luna.chmod(0o755)
    cmd = tv_lg.install_command("/tmp/x.ipk", 20).replace("/usr/bin/luna-send-pub", str(luna)) \
        .replace(tv_lg.REMOTE_DIR, str(tmp_path))
    t = time.time()
    p = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=30)
    assert time.time() - t < 8
    assert tv_lg.install_verdict(p.stdout) == "installed"


# ------------------------------------------------------------------ Samsung
def test_samsung_missing_tizen_studio(tmp_path, monkeypatch):
    monkeypatch.setattr(tv_samsung, "CANDIDATES", [str(tmp_path / "yok")])
    with pytest.raises(tv_samsung.SamsungError, match="Tizen Studio"):
        tv_samsung.find_tizen()


def test_samsung_setup_signs_installs_and_runs(tmp_path, monkeypatch):
    src = tmp_path / "tizen"
    src.mkdir()
    (src / "config.xml").write_text("<widget/>")
    monkeypatch.setattr(tv_samsung.paths, "resource", lambda rel: src)
    monkeypatch.setattr(tv_samsung, "find_tizen", lambda root="": ("tizen", "sdb"))
    calls = []

    def fake_run(args, timeout=180):
        calls.append(args)
        if args[:2] == ["sdb", "connect"]:
            return "connected to 127.0.0.1:26101"
        if args[1] == "package":
            (tmp_path / "x").mkdir(exist_ok=True)
            from pathlib import Path
            (Path(args[-1]) / "GTA6Altyazi.wgt").write_bytes(b"wgt")
            return "Package File Location: GTA6Altyazi.wgt"
        if args[1] == "install":
            return "Installed the package: Id(GTA6Altyzi)"
        return "Launched the application"
    monkeypatch.setattr(tv_samsung, "_run", fake_run)
    tv_samsung.setup("127.0.0.1", "gta6")
    kinds = [c[1] for c in calls]
    assert kinds == ["connect", "package", "install", "run"]
    assert calls[1][:5] == ["tizen", "package", "-t", "wgt", "-s"] and calls[1][5] == "gta6"
    assert calls[2][2:6] == ["-n", "GTA6Altyazi.wgt", "-s", "127.0.0.1:26101"]
    assert calls[3][2:4] == ["-p", "GTA6Altyzi.GTA6Altyazi"]


def test_samsung_missing_certificate_hint(tmp_path, monkeypatch):
    src = tmp_path / "tizen"
    src.mkdir()
    (src / "config.xml").write_text("<widget/>")
    monkeypatch.setattr(tv_samsung.paths, "resource", lambda rel: src)
    monkeypatch.setattr(tv_samsung, "find_tizen", lambda root="": ("tizen", "sdb"))
    monkeypatch.setattr(tv_samsung, "_run", lambda args, timeout=180: "connected" if args[1] == "connect"
                        else "[ERROR] Signing profile 'gta6' is not found in profiles.xml")
    with pytest.raises(tv_samsung.SamsungError, match="Certificate Manager"):
        tv_samsung.setup("127.0.0.1", "gta6")


def test_server_discovery_endpoint_has_cors():
    import socket
    import time
    import urllib.request

    from altyazi.server import EventServer
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    s.close()
    EventServer(port).start()
    time.sleep(0.2)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/hello", timeout=3) as r:
        assert json.loads(r.read())["app"] == "gta6altyazi"
        assert r.headers["Access-Control-Allow-Origin"] == "*"


def test_lg_install_verdict():
    assert tv_lg.install_verdict('{"details":{"state":"installed"}}') == "installed"
    assert tv_lg.install_verdict('{"returnValue":false,"errorText":"FAILED_IPKG_INSTALL"}') == "FAILED_IPKG_INSTALL"
    assert tv_lg.install_verdict('{"returnValue":true}') is None


def test_lg_passphrase_upper_retry():
    import paramiko
    key = paramiko.RSAKey.generate(1024)
    buf = io.StringIO()
    key.write_private_key(buf, password="ABC123")
    assert tv_lg.load_key("abc123", buf.getvalue().encode()).get_bits() == 1024
