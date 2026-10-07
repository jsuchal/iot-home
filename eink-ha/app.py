"""Local image endpoint for MultiTricker/zivyobraz-fw (PNG protocol)."""

import argparse
import hashlib
import hmac
import io
import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from PIL import Image, ImageChops, ImageDraw, ImageFont

LOG = logging.getLogger("eink")
ENTITY_PATTERN = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+\Z")
MAX_BODY = 32768


@dataclass(frozen=True)
class Metric:
    entity_id: str
    label: str


@dataclass(frozen=True)
class Settings:
    device_key: str
    metrics: tuple[Metric, ...]
    title: str = "IoT doma"
    timezone: str = "Europe/Bratislava"
    sleep_seconds: int = 1800
    refresh_seconds: int = 300
    update_times: tuple[str, ...] = ()
    ha_url: str = "http://supervisor/core"
    demo: bool = False

    @classmethod
    def load(cls, filename, demo=False):
        options = json.loads(Path(filename).read_text())
        key = options.get("device_key", "")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key):
            raise ValueError("Nastavte device_key podľa X-API-Key/PIN zariadenia.")
        metrics = tuple(Metric(**item) for item in options.get("metrics", []))
        if not 1 <= len(metrics) <= 8:
            raise ValueError("Nastavte 1 až 8 metrík.")
        for metric in metrics:
            if (
                not ENTITY_PATTERN.fullmatch(metric.entity_id)
                or not isinstance(metric.label, str)
                or not 1 <= len(metric.label) <= 64
            ):
                raise ValueError("Neplatná entita alebo názov metriky.")
        values = {
            name: options[name]
            for name in (
                "title",
                "timezone",
                "sleep_seconds",
                "refresh_seconds",
                "ha_url",
            )
            if name in options
        }
        update_times = options.get("update_times", [])
        if not isinstance(update_times, list) or any(
            not isinstance(value, str)
            or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value)
            for value in update_times
        ):
            raise ValueError("update_times musí byť zoznam časov HH:MM.")
        settings = cls(
            device_key=key,
            metrics=metrics,
            demo=demo,
            update_times=tuple(sorted(set(update_times))),
            **values,
        )
        if not isinstance(settings.title, str) or not 1 <= len(settings.title) <= 64:
            raise ValueError("Neplatný názov dashboardu.")
        ZoneInfo(settings.timezone)
        for name, minimum in (("sleep_seconds", 60), ("refresh_seconds", 1)):
            value = getattr(settings, name)
            if type(value) is not int or not minimum <= value <= 86400:
                raise ValueError(f"Neplatné {name}.")
        url = urlsplit(settings.ha_url)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "ha_url musí byť HTTP(S) adresa HA bez prihlasovacích údajov."
            )
        return settings


def schedule_occurrences(settings, now):
    """Daily local wall times; skip nonexistent times, use first autumn occurrence."""
    zone = ZoneInfo(settings.timezone)
    today = now.astimezone(zone).date()
    for offset in range(-2, 3):
        day = today + timedelta(days=offset)
        for value in settings.update_times:
            hour, minute = map(int, value.split(":"))
            candidate = datetime(
                day.year, day.month, day.day, hour, minute, tzinfo=zone
            )
            # A spring-forward wall time may not exist. Round-trip to detect it.
            if datetime.fromtimestamp(candidate.timestamp(), zone) == candidate:
                yield candidate.timestamp()


def schedule_slot(settings, now=None):
    if not settings.update_times:
        return None
    now = now or datetime.now(ZoneInfo(settings.timezone))
    return max(
        value
        for value in schedule_occurrences(settings, now)
        if value <= now.timestamp()
    )


def sleep_until_update(settings, now=None):
    if not settings.update_times:
        return settings.sleep_seconds
    now = now or datetime.now(ZoneInfo(settings.timezone))
    upcoming = min(
        value
        for value in schedule_occurrences(settings, now)
        if value > now.timestamp()
    )
    return max(1, math.ceil(upcoming - now.timestamp()))


class SourceError(Exception):
    """HA data could not be fetched; never expose upstream error bodies/tokens."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HomeAssistant:
    def __init__(self, settings, token):
        self.settings = settings
        self.token = token
        self.opener = build_opener(NoRedirect())
        if not settings.demo and not token:
            raise ValueError(
                "Chýba SUPERVISOR_TOKEN (add-on) alebo HA_TOKEN (samostatný server)."
            )

    def values(self):
        if self.settings.demo:
            return ["12,4 °C", "22,1 °C", "742 ppm"][: len(self.settings.metrics)] + [
                "—"
            ] * max(0, len(self.settings.metrics) - 3)
        values = []
        deadline = time.monotonic() + 7
        for metric in self.settings.metrics:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourceError("HA timeout")
            request = Request(
                f"{self.settings.ha_url.rstrip('/')}/api/states/{metric.entity_id}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
            )
            try:
                with self.opener.open(request, timeout=min(3, remaining)) as response:
                    raw = response.read(MAX_BODY + 1)
                    if len(raw) > MAX_BODY:
                        raise SourceError("HA response too large")
                    state = json.loads(raw)
                if not isinstance(state, dict) or not isinstance(
                    state.get("attributes", {}), dict
                ):
                    raise SourceError("Invalid HA state")
            except HTTPError as exc:
                if exc.code == 404:
                    values.append("Nedostupné")
                    continue
                raise SourceError(f"HA HTTP {exc.code}") from None
            except (URLError, TimeoutError, OSError, ValueError):
                raise SourceError("HA unavailable") from None
            value = str(state.get("state", "unavailable"))
            if value in ("unknown", "unavailable"):
                values.append("Nedostupné")
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    values.append("Nedostupné")
                    continue
                value = f"{number:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            except ValueError:
                pass
            unit = str(state.get("attributes", {}).get("unit_of_measurement", ""))
            values.append(f"{value} {unit}".strip()[:96])
        return values


@dataclass(frozen=True)
class Display:
    width: int
    height: int
    color: str

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, dict) or not isinstance(
            payload.get("display"), dict
        ):
            raise TypeError("Chýba display.")
        data = payload["display"]
        width, height = data.get("width"), data.get("height")
        if (
            type(width) is not int
            or type(height) is not int
            or not (122 <= width <= 1600 and 122 <= height <= 1200)
            or width * height > 1920000
        ):
            raise ValueError("Neplatné rozmery displeja.")
        color = data.get("colorType", "BW")
        if color not in ("BW", "3C", "4C", "7C", "4G", "8G", "16G"):
            raise ValueError("Nepodporovaný colorType.")
        return cls(width, height, color)


def render(settings, display, values, updated):
    image = Image.new("RGB", (display.width, display.height), "white")
    draw = ImageDraw.Draw(image)
    scale = min(display.width / 800, display.height / 480)
    margin = max(8, round(24 * scale))
    font_dir = Path(os.environ.get("EINK_FONT_DIR", "/usr/share/fonts/truetype/dejavu"))

    def font(size, bold=False):
        return ImageFont.truetype(
            str(font_dir / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")),
            max(10, round(size * scale)),
        )

    def text_fit(text, x, y, size, bold=False, fill="black", max_width=None):
        maximum = max_width or display.width - x - margin
        face = font(size, bold)
        while draw.textlength(text, font=face) > maximum and face.size > 10:
            face = ImageFont.truetype(face.path, face.size - 1)
        while text and draw.textlength(text, font=face) > maximum:
            text = text[:-2] + "…" if len(text) > 2 else ""
        draw.text((x, y), text, font=face, fill=fill)

    accent = "red" if display.color in ("3C", "4C", "7C") else "black"
    text_fit(settings.title, margin, margin, 38, True, accent)
    header_bottom = margin + max(32, round(82 * scale))
    text_fit(
        updated.strftime("%d. %m. %Y"), margin, margin + max(16, round(49 * scale)), 20
    )
    draw.line(
        (margin, header_bottom, display.width - margin, header_bottom),
        fill=accent,
        width=max(1, round(2 * scale)),
    )
    columns = 2 if display.width >= 400 else 1
    rows = math.ceil(len(settings.metrics) / columns)
    footer_height = max(26, round(45 * scale))
    cell_height = (display.height - header_bottom - footer_height - margin) / rows
    cell_width = (display.width - 2 * margin) / columns
    for index, (metric, value) in enumerate(zip(settings.metrics, values)):
        x = round(margin + (index % columns) * cell_width)
        y = round(header_bottom + 8 + (index // columns) * cell_height)
        text_fit(
            metric.label,
            x,
            y,
            min(22, cell_height / max(scale, 0.01) * 0.24),
            max_width=cell_width - margin,
        )
        text_fit(
            value,
            x,
            y + max(14, round(min(30 * scale, cell_height * 0.3))),
            min(46, cell_height / max(scale, 0.01) * 0.45),
            True,
            max_width=cell_width - margin,
        )
    footer = (
        ("DEMO · " if settings.demo else "")
        + "Aktualizované "
        + updated.strftime("%H:%M")
    )
    text_fit(footer, margin, display.height - footer_height, 18)
    # Hard palette avoids anti-aliased gray pixels on three-color panels.
    red, green, blue = image.split()
    red_mask = ImageChops.multiply(
        red.point(lambda p: 255 if p >= 128 else 0),
        ImageChops.multiply(
            ImageChops.subtract(red, green).point(lambda p: 255 if p > 80 else 0),
            ImageChops.subtract(red, blue).point(lambda p: 255 if p > 80 else 0),
        ),
    )
    image = image.convert("L").point(lambda p: 0 if p <= 160 else 255).convert("RGB")
    image.paste((255, 0, 0), mask=red_mask)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


@dataclass(frozen=True)
class Frame:
    png: bytes
    timestamp: int
    created: float
    schedule_slot: float | None = None


class Frames:
    def __init__(self, settings, source):
        self.settings = settings
        self.source = source
        self.cached = {}
        self.lock = threading.Lock()

    def get(self, display, timestamp_check):
        with self.lock:
            frame = self.cached.get(display)
            now = time.monotonic()
            slot = schedule_slot(self.settings)
            fresh = (
                frame.schedule_slot == slot
                if frame and self.settings.update_times
                else frame is not None
                and now - frame.created < self.settings.refresh_seconds
            )
            # Image/page requests reuse the frame advertised by the last check.
            if frame and (not timestamp_check or fresh):
                return frame
            try:
                values = self.source.values()
            except SourceError:
                if frame:
                    LOG.warning("HA nedostupný; ponechávam posledný obrázok.")
                    return frame
                raise
            updated = datetime.now(ZoneInfo(self.settings.timezone)).replace(
                second=0, microsecond=0
            )
            png = render(self.settings, display, values, updated)
            # Firmware uses signed 32-bit String::toInt and compares equality.
            timestamp = (
                int.from_bytes(hashlib.sha256(png).digest()[:4], "big") & 0x7FFFFFFF
            ) or 1
            frame = Frame(png, timestamp, time.monotonic(), slot)
            if len(self.cached) >= 16 and display not in self.cached:
                self.cached.pop(next(iter(self.cached)))
            self.cached[display] = frame
            return frame


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, settings, source):
        self.settings = settings
        self.frames = Frames(settings, source)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # Do not log device keys, telemetry, or upstream response bodies.

    def reply(self, status, body, content_type="application/json", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, str(value))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, b'{"status":"ok"}')
        else:
            self.reply(404, b'{"error":"not found"}')

    def do_POST(self):
        self.connection.settimeout(10)
        key = self.headers.get("X-API-Key", "")
        if not hmac.compare_digest(
            key.encode(), self.server.settings.device_key.encode()
        ):
            self.reply(401, b'{"error":"unauthorized"}')
            return
        url = urlsplit(self.path)
        if url.path != "/index.php":
            self.reply(404, b'{"error":"not found"}')
            return
        query = parse_qs(url.query, keep_blank_values=True)
        if query not in ({"timestampCheck": ["0"]}, {"timestampCheck": ["1"]}):
            self.reply(400, b'{"error":"invalid timestampCheck"}')
            return
        try:
            if (
                self.headers.get("Transfer-Encoding")
                or self.headers.get_content_type() != "application/json"
            ):
                raise ValueError("Expected JSON with Content-Length")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.reply(413, b'{"error":"invalid body size"}')
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete JSON")
            display = Display.from_payload(json.loads(raw))
        except (ValueError, TypeError, TimeoutError, OSError):
            self.reply(400, b'{"error":"invalid device payload"}')
            return
        try:
            frame = self.server.frames.get(display, query["timestampCheck"] == ["1"])
        except SourceError:
            self.reply(503, b'{"error":"Home Assistant unavailable"}')
            return
        self.reply(
            200,
            frame.png,
            "image/png",
            {
                "Timestamp": frame.timestamp,
                "PreciseSleep": sleep_until_update(self.server.settings),
                "ShowNoWifiError": 0,
            },
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", default=os.environ.get("EINK_CONFIG", "/data/options.json")
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings = Settings.load(args.config, demo=args.demo)
        source = HomeAssistant(
            settings, os.environ.get("HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN")
        )
        # Fail early if the font package is missing.
        ImageFont.truetype(
            str(
                Path(
                    os.environ.get("EINK_FONT_DIR", "/usr/share/fonts/truetype/dejavu")
                )
                / "DejaVuSans.ttf"
            ),
            12,
        )
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(
            1,
            "Neplatná konfigurácia alebo chýbajúce lokálne závislosti. Skontrolujte nastavenia add-onu.\n",
        )
    server = Server((args.host, args.port), settings, source)
    LOG.info(
        "E-ink endpoint spustený na porte %d (%s).",
        args.port,
        "DEMO" if settings.demo else "Home Assistant",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
