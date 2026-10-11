#!/usr/bin/env python3
"""Open the USB-initiated WiFiManager portal without erasing Wi-Fi or API key.

Requires pyserial (installed with PlatformIO). Logs are sanitized before writing.
CC-BY-NC-SA-4.0; see ../addon/NOTICE.md.
"""
import argparse
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import urlopen

import serial


def sanitize(line):
    if re.search(r"api.?key|password|ssid|\"mac\"|SAVED AP|SN:", line, re.I):
        return "[redacted private configuration line]"
    return line


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="hostname or IPv4[:port], e.g. 192.168.1.10:8443")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--log", default="/tmp/opencode/zivyobraz-configure.log")
    parser.add_argument("--seconds", type=int, default=90)
    parser.add_argument("--cycles", type=int, default=1, help="number of sleep cycles to record (keep USB open)")
    args = parser.parse_args()
    connection = serial.Serial()
    connection.port = args.port
    connection.baudrate = 115200
    connection.timeout = 0.5
    connection.dtr = False
    connection.rts = False
    connection.open()
    # Reset ESP32 via EN only, with BOOT high. Do not enter the ROM loader.
    connection.rts = True
    time.sleep(0.1)
    connection.rts = False
    pending = b""
    configured = False
    confirmed = False
    slept = False
    sleep_count = 0
    end = time.monotonic() + args.seconds
    try:
        with Path(args.log).open("w") as log:
            while time.monotonic() < end:
                pending += connection.read(4096)
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    text = line.decode("utf-8", "replace").rstrip("\r")
                    safe = sanitize(text)
                    print(safe, flush=True)
                    log.write(safe + "\n")
                    log.flush()
                    if "Send c over USB" in text and not configured:
                        connection.write(b"c")
                    match = re.search(r"Server portal: (http://[^/]+/param)", text)
                    if match and not configured:
                        url = match.group(1)
                        with urlopen(url, timeout=5) as response:
                            html = response.read().decode()
                        if 'serverHost' not in html:
                            raise RuntimeError("serverHost field missing from WiFiManager portal")
                        with urlopen(url + "save", urlencode({"serverHost": args.host}).encode(), timeout=5) as response:
                            response.read()
                        configured = True
                        print("WiFiManager host field submitted (no Wi-Fi credential changes)", flush=True)
                    if "Connecting to:" in text and args.host in text:
                        confirmed = True
                    if "Going to sleep for" in text:
                        sleep_count += 1
                        if sleep_count >= args.cycles:
                            slept = True
                            break
                if slept:
                    break
    finally:
        connection.close()
    if not (configured and confirmed and slept):
        raise SystemExit("Configuration not verified; inspect the sanitized log and USB/network access")
    print("Configured endpoint confirmed; device entered deep sleep. Inspect image/refresh logs.")


if __name__ == "__main__":
    main()
