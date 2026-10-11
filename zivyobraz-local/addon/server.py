"""Živý obraz 3.2 HTTPS endpoint. CC-BY-NC-SA-4.0; see NOTICE.md."""

import argparse
import hashlib
import hmac
import io
import json
import logging
import os
from pathlib import Path
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageOps

LOG = logging.getLogger("zivyobraz")
MAX_SOURCE_BYTES = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 16_000_000


class Images:
    def __init__(self, options):
        self.options = options
        self.lock = threading.Lock()
        self.cached_url = None
        self.cached_at = 0

    def source(self):
        kind = self.options["image_source"]
        if kind == "test":
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
            image = self.source().convert("RGBA")
            background = Image.new("RGBA", image.size, "white")
            background.alpha_composite(image)
            scaled = ImageOps.contain(background.convert("RGB"), (width, height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (width, height), "white")
            canvas.paste(scaled, ((width - scaled.width) // 2, (height - scaled.height) // 2))
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
        if timestamp is not None:
            # Case matters: upstream header parsing is case sensitive.
            self.send_header("Timestamp", str(timestamp))
            self.send_header("PreciseSleep", str(self.server.options["sleep_seconds"]))
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

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
        try:
            # Firmware 3.2 reuses timestampCheck=1 connection for image streaming.
            # BOTH query values must return an image, never an empty check response.
            self.respond(200, data, "image/png", timestamp)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Unchanged timestamp: the frame intentionally closes early.


def load_options(path):
    options = json.loads(Path(path).read_text())
    defaults = {"image_source": "test", "image_url": "", "image_file": "/share/zivyobraz/image.png",
                "accent": "red", "sleep_seconds": 360}
    options = defaults | options
    if not isinstance(options.get("api_key"), str) or not options["api_key"]:
        raise ValueError("set api_key to the existing frame PIN before starting")
    if options["image_source"] not in ("test", "file", "url") or options["accent"] not in ("red", "yellow"):
        raise ValueError("invalid image_source/accent")
    if type(options["sleep_seconds"]) is not int or not 60 <= options["sleep_seconds"] <= 86400:
        raise ValueError("sleep_seconds must be 60..86400")
    return options


def make_server(address, options):
    server = Server(address, Handler)
    server.daemon_threads = True
    server.options = options
    server.images = Images(options)
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
    server = make_server(("0.0.0.0", args.port), options)
    server.socket = context.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
    LOG.info("Živý obraz local listening on HTTPS :%s; source=%s", args.port, options["image_source"])
    server.serve_forever()


if __name__ == "__main__":
    main()
