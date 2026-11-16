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
        if "appInstallService" in cmd:
            if "installed" in self.install_reply:
                self.version = self.version_after
            return None, FakeOut(self.install_reply), FakeOut("")
        if "appinfo.json" in cmd:
            return None, FakeOut(json.dumps({"version": self.version}) if self.version else ""), FakeOut("")
        if "applicationManager/launch" in cmd:
            return None, FakeOut('{"returnValue": true}'), FakeOut("")
        return None, FakeOut(""), FakeOut("")

    def open_sftp(self):
        ssh = self

        class S:
            def put(self, local, remote):
                ssh.uploads.append(remote)

            def close(self):
                pass
        return S()

    def close(self):
        pass


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
    assert '"ipkUrl": "/media/developer/temp/com.gta6altyazi.tv_0.3.1_all.ipk"' in install
    launch = next(c for c in fake.cmds if "applicationManager/launch" in c)
    assert f'"host": "{server}"' in launch and server.endswith(":8787")


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
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    EventServer(port).start()
    time.sleep(0.2)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/kim", timeout=3) as r:
        assert json.loads(r.read()) == {"app": "gta6-altyazi"}
        assert r.headers["Access-Control-Allow-Origin"] == "*"
