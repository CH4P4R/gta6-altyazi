"""Testler için sahte adb: gerçek bir Android TV'nin cevaplarını taklit eder. Durum JSON dosyasında tutulur."""
import json
import os
import sys

path = os.environ["FAKE_ADB_STATE"]
st = json.load(open(path))
args = sys.argv[1:]
st["calls"].append(args)
serial = None
if args[:1] == ["-s"]:
    serial, args = args[1], args[2:]
out = ""
cmd = args[0]
if cmd == "connect":
    st["connected"] = args[1]
    out = f"connected to {args[1]}"
elif cmd == "devices":
    out = "List of devices attached\n"
    if st.get("connected"):
        st["polls"] = st.get("polls", 0) + 1
        state = "unauthorized" if st["polls"] <= st.get("unauth_polls", 0) else "device"
        out += f"{st['connected']}\t{state}\n"
elif cmd == "mdns":
    out = "List of discovered mdns services\n" + st.get("mdns", "")
elif cmd == "pair":
    want = st.get("pair_port")                     # gerçek TV: yalnız eşleştirme penceresinin portu kabul eder
    if st.get("stale_server") and not st.get("restarted"):   # eski adb sunucusu araya giriyor
        out = "error: protocol fault (couldn't read status message): No error"
    elif want and not args[1].endswith(f":{want}"):
        out = "error: protocol fault (couldn't read status message): No error"
    elif st.get("pair_code") and args[2] != st["pair_code"]:
        out = "Failed: Wrong password or connection was dropped."
    else:
        out = f"Successfully paired to {args[1]} [guid=adb-XYZ]"
elif cmd == "kill-server":
    st["restarted"] = True
elif cmd == "install":
    if st.get("incompatible") and not st.get("uninstalled"):
        out = "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]"
    else:
        st["installed"] = True
        out = "Performing Streamed Install\nSuccess"
elif cmd == "uninstall":
    st["uninstalled"] = True
    out = "Success"
elif cmd == "shell":
    sh = args[1]
    if sh.startswith("getprop"):
        out = "14"
    elif sh.startswith("dumpsys package"):
        out = f"    versionCode={st.get('version', 1000)} minSdk=24 targetSdk=35" if st.get("installed") else ""
    elif sh.startswith("appops get"):
        out = "SYSTEM_ALERT_WINDOW: ignore" if st.get("no_overlay") else "SYSTEM_ALERT_WINDOW: allow"
    elif sh.startswith("am start"):
        out = "Starting: Intent { cmp=com.gta6altyazi.tv/.MainActivity (has extras) }"
json.dump(st, open(path, "w"))
print(out)
