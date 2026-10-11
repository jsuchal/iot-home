"""Živý obraz 3.2 HTTPS endpoint. CC-BY-NC-SA-4.0; see NOTICE.md."""

import argparse
import hashlib
import hmac
import io
import json
import logging
import os
import math
import re
from pathlib import Path
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageOps
from components import Components
from schedule import sleep_seconds, validate as validate_schedule
from weather import Weather
from weatherman import Weatherman, prepare_data

LOG = logging.getLogger("zivyobraz")
MAX_SOURCE_BYTES = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 16_000_000


class Images:
    def __init__(self, options, data_dir=None):
        self.options = options
        self.lock = threading.Lock()
        self.cached_url = None
        self.cached_at = 0
        self.weather = Weather(options, Path(data_dir) / "weather-cache.json" if data_dir else None) if options["image_source"] == "homeassistant" else None

    def source(self, size):
        kind = self.options["image_source"]
        if kind == "homeassistant":
            if self.options.get("layout", "classic") == "weatherman":
                data = self.weather.read()
                data = prepare_data(self.weather.snapshot, self.weather.snapshot["daily_forecast"],
                                    now=datetime.now(timezone.utc), options=self.options, data=data)
                return Weatherman(display_mode=self.options.get("display_mode", "dark")).render(data)
            return Components(self.options.get("font_dir", "/usr/share/fonts/truetype/dejavu"),
                              portrait=size[1] > size[0]).render(self.weather.read())
        if kind == "test":
            if size[1] > size[0]:
                # Dedicated portrait test, not a shrunken landscape composition.
                image = Image.new("RGB", (480, 800), "white")
                draw = ImageDraw.Draw(image)
                draw.rectangle((10, 10, 469, 789), outline="black", width=6)
                text = Image.new("RGB", (220, 70), "white")
                ImageDraw.Draw(text).text((8, 8), "ZIVY OBRAZ - LOCAL\nPORTRAIT 480 x 800\nTOP / HORE", fill="black")
                image.paste(text.resize((440, 140), Image.Resampling.NEAREST), (20, 40))
                accent = "red" if self.options["accent"] == "red" else "yellow"
                draw.rectangle((60, 230, 419, 370), fill="black")
                draw.rectangle((60, 400, 419, 540), fill="white", outline="black", width=4)
                draw.rectangle((60, 570, 419, 710), fill=accent)
                return image
            image = Image.new("RGB", (800, 480), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 10, 789, 469), outline="black", width=6)
            # Default Pillow font scaled up without host font dependencies.
            text = Image.new("RGB", (380, 60), "white")
            ImageDraw.Draw(text).text((8, 8), "ZIVY OBRAZ - LOCAL\n800 x 480 / BLACK WHITE RED", fill="black")
            image.paste(text.resize((760, 120), Image.Resampling.NEAREST), (20, 30))
            accent = "red" if self.options["accent"] == "red" else "yellow"
            draw.rectangle((40, 190, 245, 410), fill="black")
            draw.rectangle((295, 190, 500, 410), fill="white", outline="black", width=4)
            draw.rectangle((550, 190, 755, 410), fill=accent)
            return image
        if kind == "file":
            path = Path(self.options["image_file"]).resolve()
            if not path.is_relative_to(Path("/share")):
                raise ValueError("image_file must be inside /share")
            with path.open("rb") as source:
                data = source.read(MAX_SOURCE_BYTES + 1)
        else:
            if urlsplit(self.options["image_url"]).scheme not in ("http", "https"):
                raise ValueError("image_url must use http or https")
            if self.cached_url is not None and time.monotonic() - self.cached_at < 60:
                data = self.cached_url
            else:
                # Never send the frame's X-API-Key to image providers.
                with urlopen(self.options["image_url"], timeout=10) as source:
                    if urlsplit(source.url).scheme not in ("http", "https"):
                        raise ValueError("invalid redirect scheme")
                    data = source.read(MAX_SOURCE_BYTES + 1)
                if len(data) > MAX_SOURCE_BYTES:
                    raise ValueError("source image too large")
                self.cached_url = data
                self.cached_at = time.monotonic()
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError("source image too large")
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return ImageOps.exif_transpose(image).convert("RGBA")

    def render(self, width, height):
        # Serialize URL cache updates and image rendering to bound memory use.
        with self.lock:
            rotation = int(self.options.get("rotation", "0"))
            # Firmware keeps its native dimensions/direct-streaming path. Compose
            # portrait content first, then rotate losslessly into physical pixels.
            size = (height, width) if rotation in (90, 270) else (width, height)
            image = self.source(size).convert("RGBA")
            background = Image.new("RGBA", image.size, "white")
            background.alpha_composite(image)
            scaled = ImageOps.contain(background.convert("RGB"), size, Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", size, "white")
            canvas.paste(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
            turns = {90: Image.Transpose.ROTATE_90, 180: Image.Transpose.ROTATE_180,
                     270: Image.Transpose.ROTATE_270}
            if rotation:
                canvas = canvas.transpose(turns[rotation])
            palette = Image.new("P", (1, 1))
            accent = (255, 0, 0) if self.options["accent"] == "red" else (255, 255, 0)
            palette.putpalette(([255, 255, 255, 0, 0, 0, *accent] + [255, 255, 255] * 253))
            # RGB, non-interlaced, opaque PNG: sequential pixels for upstream pngle.
            result = canvas.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
            output = io.BytesIO()
            result.save(output, format="PNG", compress_level=6)
            data = output.getvalue()
            # Upstream parses Timestamp with signed String::toInt(). Nonzero 31-bit.
            timestamp = (int.from_bytes(hashlib.sha256(data).digest()[:4], "big") & 0x7FFFFFFF) or 1
            return data, timestamp


class Server(ThreadingHTTPServer):
    def shutdown_request(self, request):
        if isinstance(request, ssl.SSLSocket):
            try:
                # Send TLS close_notify rather than an abrupt TCP FIN. The ESP32
                # decoder reads until EOF; a raw close logs a misleading TLS error.
                request.settimeout(1)
                request = request.unwrap()
            except (OSError, ValueError):
                pass
        super().shutdown_request(request)

    def handle_error(self, request, client_address):
        # socketserver prints a full traceback for every failed connection. Most
        # here are clients that speak plain HTTP to this TLS port or refuse the
        # self-signed certificate; that is a client decision, not a server fault.
        error = sys.exc_info()[1]
        host = client_address[0] if client_address else "unknown"
        if isinstance(error, ssl.SSLError):
            LOG.debug("TLS connection from %s closed by client: %s", host, getattr(error, "reason", type(error).__name__))
        elif isinstance(error, (BrokenPipeError, ConnectionResetError, TimeoutError)):
            LOG.debug("connection from %s ended early: %s", host, type(error).__name__)
        else:
            LOG.warning("request from %s failed: %s", host, type(error).__name__)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        self.request.settimeout(15)
        super().setup()

    def log_message(self, *_):
        # Do not log request headers, API keys, Wi-Fi credentials or JSON telemetry.
        pass

    def respond(self, status, body=b"", content_type="text/plain", timestamp=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if timestamp is not None:
            # Case matters: upstream header parsing is case sensitive.
            self.send_header("Timestamp", str(timestamp))
            self.send_header("PreciseSleep", str(sleep_seconds(self.server.options)))
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/image.png" or not self.server.options.get("preview_enabled", False):
            self.respond(404, b"Not found\n")
            return
        with self.server.preview_lock:
            data = self.server.last_image
        if data is None:
            self.respond(404, b"No image yet. Wait for the next authenticated frame request.\n")
            return
        # Deliberately unauthenticated, opt-in LAN preview. Never fetch weather
        # or regenerate on GET: show the exact latest frame-response PNG bytes.
        self.respond(200, data, "image/png")

    def do_POST(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        if url.path != "/index.php" or query.get("timestampCheck") not in (["0"], ["1"]):
            self.respond(400, b"Expected /index.php?timestampCheck=0|1\n")
            return
        key = self.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key.encode(), self.server.options["api_key"].encode()):
            LOG.warning("request rejected: invalid API key")
            self.respond(401, b"Unauthorized\n")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384 or self.headers.get("Transfer-Encoding"):
                raise ValueError("invalid request length")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("expected application/json")
            payload = json.loads(self.rfile.read(length))
            display = payload["display"]
            width, height = display["width"], display["height"]
            if type(width) is not int or type(height) is not int:
                raise ValueError("integer dimensions required")
            if not (1 <= width <= 1600 and 1 <= height <= 1600 and width * height <= 1_600_000):
                raise ValueError("unsupported dimensions")
            if display["colorType"] != "3C":
                raise ValueError("v1 supports 3C displays only")
        except (ValueError, TypeError, KeyError):
            self.respond(400, b"Invalid JSON display configuration\n")
            return
        try:
            data, timestamp = self.server.images.render(width, height)
        except Exception as error:
            # Exception strings can contain private URLs; log only their type.
            LOG.error("image generation failed: %s", type(error).__name__)
            self.respond(502, b"Image source unavailable\n")
            return
        LOG.info("POST /index.php timestampCheck=%s display=%sx%s 3C Timestamp=%s bytes=%s status=200",
                  query["timestampCheck"][0], width, height, timestamp, len(data))
        with self.server.preview_lock:
            self.server.last_image = data
        try:
            # Firmware 3.2 reuses timestampCheck=1 connection for image streaming.
            # BOTH query values must return an image, never an empty check response.
            self.respond(200, data, "image/png", timestamp)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Unchanged timestamp: the frame intentionally closes early.


def load_options(path):
    options = json.loads(Path(path).read_text())
    defaults = {"image_source": "test", "image_url": "", "image_file": "/share/zivyobraz/image.png",
                "accent": "red", "sleep_seconds": 360, "rotation": "0",
                "weather_entity": "weather.forecast_home", "forecast_type": "hourly",
                "forecast_step_hours": "3",
                "weather_stale_minutes": 120, "timezone": "Europe/Prague",
                "update_mode": "interval", "update_times": ["07:00", "12:00", "18:00"],
                "window_start": "07:00", "window_end": "22:00", "window_interval_minutes": 30,
                "preview_enabled": False, "layout": "classic", "cold_below_c": 0, "hot_above_c": 28,
                "wind_above_kmh": 40, "rain_above_mm_day": 10, "rain_above_mm_hour": 4,
                "display_mode": "light"}
    options = defaults | options
    if not isinstance(options.get("api_key"), str) or not options["api_key"]:
        raise ValueError("set api_key to the existing frame PIN before starting")
    if options["image_source"] not in ("test", "file", "url", "homeassistant") or options["accent"] not in ("red", "yellow"):
        raise ValueError("invalid image_source/accent")
    if type(options["sleep_seconds"]) is not int or not 60 <= options["sleep_seconds"] <= 86400:
        raise ValueError("sleep_seconds must be 60..86400")
    if options["rotation"] not in ("0", "90", "180", "270"):
        raise ValueError("rotation must be 0, 90, 180 or 270 degrees counterclockwise")
    if not isinstance(options["weather_entity"], str) or not re.fullmatch(r"weather\.[a-z0-9_]+", options["weather_entity"]):
        raise ValueError("weather_entity must be a weather entity_id")
    if options["forecast_type"] not in ("hourly", "daily"):
        raise ValueError("forecast_type must be hourly or daily")
    if options["forecast_step_hours"] not in ("1", "3"):
        raise ValueError("forecast_step_hours must be 1 or 3")
    if type(options["weather_stale_minutes"]) is not int or not 1 <= options["weather_stale_minutes"] <= 10080:
        raise ValueError("weather_stale_minutes must be 1..10080")
    validate_schedule(options)
    if type(options["preview_enabled"]) is not bool:
        raise ValueError("preview_enabled must be true or false")
    if options["layout"] not in ("classic", "weatherman"):
        raise ValueError("layout must be classic or weatherman")
    if options["display_mode"] not in ("dark", "light"):
        raise ValueError("display_mode must be dark or light")
    if options["layout"] == "weatherman" and (options["forecast_type"] != "hourly" or options["rotation"] not in ("90", "270")):
        raise ValueError("weatherman requires hourly forecast and portrait rotation 90/270")
    for key, low, high in (("cold_below_c", -80, 60), ("hot_above_c", -80, 60),
                           ("wind_above_kmh", 0, 300), ("rain_above_mm_day", 0, 1000),
                           ("rain_above_mm_hour", 0, 100)):
        if type(options[key]) not in (int, float) or not math.isfinite(options[key]) or not low <= options[key] <= high:
            raise ValueError("invalid threshold: " + key)
    if options["cold_below_c"] >= options["hot_above_c"]:
        raise ValueError("cold_below_c must be less than hot_above_c")
    return options


def make_server(address, options, data_dir=None):
    server = Server(address, Handler)
    server.daemon_threads = True
    server.options = options
    server.images = Images(options, data_dir)
    server.preview_lock = threading.Lock()
    server.last_image = None
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--options", default="/data/options.json")
    parser.add_argument("--data-dir", default="/data")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    options = load_options(args.options)
    directory = Path(args.data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    cert, key = directory / "server-cert.pem", directory / "server-key.pem"
    if not cert.exists() or not key.exists():
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
                        "-subj", "/CN=zivyobraz-local", "-keyout", str(key), "-out", str(cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(key, 0o600)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    server = make_server(("0.0.0.0", args.port), options, directory)
    server.socket = context.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
    LOG.info("Živý obraz local listening on HTTPS :%s; source=%s", args.port, options["image_source"])
    server.serve_forever()


if __name__ == "__main__":
    main()
