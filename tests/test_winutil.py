"""Güvenlik duvarı betikleri: Windows'ta PowerShell'in kendi ayrıştırıcısıyla denetlenir (çalıştırılmaz)."""

import base64
import subprocess
import sys

import pytest

from altyazi import winutil


def test_firewall_script_quotes_paths_and_scopes_rule():
    s = winutil.firewall_script(r"C:\Program Files\O'Brien\GTA6Altyazi.exe", make_private=True)
    assert r"$p = 'C:\Program Files\O''Brien\GTA6Altyazi.exe'" in s           # tek tırnak güvenle kaçırılır
    assert "-Profile Private -RemoteAddress LocalSubnet -Protocol TCP" in s
    assert "-Protocol UDP" in s and winutil.FIREWALL_GROUP in s
    assert "Set-NetConnectionProfile -NetworkCategory Private" in s
    assert "Set-NetConnectionProfile" not in winutil.firewall_script("C:\\x.exe", make_private=False)


def _parse_errors(script: str) -> int:
    check = ("$s = [System.Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($env:BETIK)); $e = $null; "
             "[System.Management.Automation.Language.Parser]::ParseInput($s, [ref]$null, [ref]$e) | Out-Null; "
             "exit $e.Count")
    env = {**__import__("os").environ, "BETIK": base64.b64encode(script.encode("utf-16-le")).decode()}
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", check], env=env,
                          capture_output=True, timeout=60).returncode


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell yalnız Windows'ta")
def test_firewall_scripts_parse_in_powershell():
    assert _parse_errors(winutil.firewall_script(r"C:\Program Files\GTA6 Altyazı\GTA6Altyazi.exe", True)) == 0
    assert _parse_errors(winutil.firewall_script(r"C:\x.exe", False)) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows'a özgü")
def test_firewall_status_reads_without_crashing():
    assert winutil.firewall_ok() in (True, False, None)
    assert winutil.network_is_public() in (True, False, None)
