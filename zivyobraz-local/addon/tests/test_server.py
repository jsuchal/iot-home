import http.client
import contextlib
import ssl
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Images, load_options, make_server


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.options = {"api_key": "test-key", "image_source": "test", "accent": "red", "sleep_seconds": 360}
        self.server = make_server(("127.0.0.1", 0), self.options)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, check, payload=None, key="test-key", path=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        body = json.dumps(payload if payload is not None else {
            "display": {"type": "GDEY075Z08", "width": 800, "height": 480, "colorType": "3C"}})
        connection.request("POST", path or f"/index.php?timestampCheck={check}", body,
                           {"Content-Type": "application/json", "X-API-Key": key})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def preview(self, path="/image.png"):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        connection.request("GET", path)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_direct_preview_opt_in_and_exact_frame_bytes(self):
        self.assertEqual(self.preview()[0], 404)
        self.options["preview_enabled"] = True
        self.assertEqual(self.preview()[0], 404)
        frame = self.request(1)
        with patch.object(self.server.images, "render", side_effect=AssertionError("GET must not regenerate")):
            status, headers, image = self.preview()
        self.assertEqual(status, 200)
        self.assertEqual(image, frame[2])
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("PreciseSleep", headers)
        self.assertNotIn("Timestamp", headers)
        self.assertEqual(self.preview("/data/options.json")[0], 404)
        self.options["preview_enabled"] = False
        self.assertEqual(self.preview()[0], 404)

    def test_failed_or_unauthenticated_requests_preserve_preview(self):
        self.options["preview_enabled"] = True
        image = self.request(0)[2]
        self.assertEqual(self.request(1, key="bad")[0], 401)
        with patch.object(self.server.images, "render", side_effect=OSError):
            self.assertEqual(self.request(1)[0], 502)
        self.assertEqual(self.preview()[2], image)

    def test_both_checks_return_same_complete_image_and_headers(self):
        first = self.request(1)
        second = self.request(0)
        for status, headers, data in (first, second):
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Length"], str(len(data)))
            self.assertEqual(headers["Content-Type"], "image/png")
            self.assertEqual(headers["PreciseSleep"], "360")
            self.assertTrue(0 < int(headers["Timestamp"]) <= 0x7FFFFFFF)
            self.assertEqual(headers["Connection"], "close")
            image = Image.open(io.BytesIO(data))
            image.load()
            self.assertEqual(image.size, (800, 480))
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(set(image.getdata()), {(0, 0, 0), (255, 255, 255), (255, 0, 0)})
        self.assertEqual(first[2], second[2])
        self.assertEqual(first[1]["Timestamp"], second[1]["Timestamp"])

    def test_authentication(self):
        self.assertEqual(self.request(1, key="bad")[0], 401)
        self.assertEqual(self.request(1, key="")[0], 401)

    def test_client_tls_and_reset_errors_have_no_traceback(self):
        for error in (ssl.SSLError(1, "certificate unknown"), BrokenPipeError(), ConnectionResetError()):
            with contextlib.redirect_stderr(io.StringIO()) as stderr, \
                 self.assertLogs("zivyobraz", level="DEBUG") as captured:
                try:
                    raise error
                except type(error):
                    self.server.handle_error(None, ("192.0.2.9", 5000))
            self.assertEqual(stderr.getvalue(), "")  # No socketserver traceback dump.
            self.assertFalse(any("failed:" in line for line in captured.output))
        with contextlib.redirect_stderr(io.StringIO()) as stderr, \
             self.assertLogs("zivyobraz", level="WARNING") as captured:
            try:
                raise ValueError("boom")
            except ValueError:
                self.server.handle_error(None, ("192.0.2.9", 5000))
        self.assertIn("request from 192.0.2.9 failed: ValueError", captured.output[0])
        self.assertEqual(stderr.getvalue(), "")

    def test_schedule_sleep_header_does_not_change_image_timestamp(self):
        first = self.request(1)
        self.options["update_mode"] = "daily"
        with patch("server.sleep_seconds", return_value=18000):
            second = self.request(1)
        self.assertEqual(second[1]["PreciseSleep"], "18000")
        self.assertEqual(first[1]["Timestamp"], second[1]["Timestamp"])
        self.assertEqual(first[2], second[2])

    def test_live_weather_both_checks_and_outage_timestamp(self):
        self.options.update(image_source="homeassistant", weather_entity="weather.forecast_home",
                            forecast_type="hourly", forecast_step_hours="1", rotation="90", timezone="Europe/Prague", update_mode="daily")
        self.server.images = Images(self.options)
        state = {"state": "sunny", "attributes": {"temperature": 11.1, "temperature_unit": "°C", "humidity": 80}}
        forecast = [{"datetime": (datetime.now(timezone.utc) + timedelta(hours=n)).isoformat(),
                     "temperature": 15, "condition": "sunny"} for n in (1, 2, 3)]
        response = {"service_response": {"weather.forecast_home": {"forecast": forecast}}}
        with patch("weather.api", side_effect=[state, response]):
            first, second = self.request(0), self.request(1)
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertEqual(first[2], second[2])
        self.assertEqual(Image.open(io.BytesIO(first[2])).size, (800, 480))
        self.assertNotIn("Rotate", first[1])
        self.assertTrue(60 <= int(first[1]["PreciseSleep"]) <= 86400)
        self.server.images.weather.checked = None
        with patch("weather.api", side_effect=OSError):
            stale = self.request(1)
        self.assertEqual(stale[0], 200)
        self.assertNotEqual(first[1]["Timestamp"], stale[1]["Timestamp"])

    def test_invalid_requests(self):
        for display in ({}, {"width": 0, "height": 480, "colorType": "3C"},
                        {"width": True, "height": 480, "colorType": "3C"},
                        {"width": 5000, "height": 480, "colorType": "3C"},
                        {"width": 800, "height": 480, "colorType": "BW"}):
            self.assertEqual(self.request(1, {"display": display})[0], 400)
        self.assertEqual(self.request(2)[0], 400)
        self.assertEqual(self.request(1, path="/bad")[0], 400)
        self.assertEqual(self.request(1, payload=[])[0], 400)

    def test_scaling_and_yellow(self):
        self.options["accent"] = "yellow"
        status, _, data = self.request(1, {"display": {"width": 400, "height": 300, "colorType": "3C"}})
        self.assertEqual(status, 200)
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (400, 300))
        self.assertEqual(set(image.getdata()), {(0, 0, 0), (255, 255, 255), (255, 255, 0)})

    def test_image_source_failure_is_not_a_successful_timestamp(self):
        with patch.object(self.server.images, "render", side_effect=OSError()):
            status, headers, _ = self.request(1)
        self.assertEqual(status, 502)
        self.assertNotIn("Timestamp", headers)

    def test_rotation_90_keeps_native_dimensions_and_changes_timestamp(self):
        _, first_headers, _ = self.request(1)
        self.options["rotation"] = "90"
        status, headers, data = self.request(1)
        self.assertEqual(status, 200)
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (800, 480))
        self.assertEqual(set(image.getdata()), {(0, 0, 0), (255, 255, 255), (255, 0, 0)})
        self.assertNotEqual(first_headers["Timestamp"], headers["Timestamp"])
        self.assertNotIn("Rotate", headers)  # Keep direct streaming, not firmware rotation.


class SourceTests(unittest.TestCase):
    def test_all_quarter_turns_are_lossless_and_counterclockwise(self):
        for angle in (0, 90, 180, 270):
            size = (8, 12) if angle in (90, 270) else (12, 8)
            source = Image.new("RGB", size, "white")
            source.putpixel((0, 0), (255, 0, 0))
            source.putpixel((size[0] - 1, 0), (0, 0, 0))
            images = Images({"image_source": "test", "accent": "red", "rotation": str(angle)})
            with patch.object(images, "source", return_value=source) as get_source:
                data, _ = images.render(12, 8)
                get_source.assert_called_once_with(size)
            result = Image.open(io.BytesIO(data))
            expected = source.rotate(angle, expand=True)
            self.assertEqual(result.size, (12, 8))
            self.assertEqual(list(result.getdata()), list(expected.getdata()))

    def test_file_restricted_to_share(self):
        images = Images({"image_source": "file", "image_file": "/etc/passwd", "accent": "red"})
        with self.assertRaises(ValueError):
            images.render(800, 480)

    def test_file_changes_timestamp_and_composites_transparency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            images = Images({"image_source": "file", "image_file": str(path), "accent": "red"})
            # Keep production path restriction; substitute /share only for this test.
            with patch("server.Path.is_relative_to", return_value=True):
                Image.new("RGBA", (200, 200), (0, 0, 0, 0)).save(path)
                first, ts1 = images.render(800, 480)
                self.assertEqual(set(Image.open(io.BytesIO(first)).getdata()), {(255, 255, 255)})
                Image.new("RGB", (200, 200), "red").save(path)
                _, ts2 = images.render(800, 480)
                self.assertNotEqual(ts1, ts2)

    def test_url_cached_and_no_key_forwarded(self):
        buffer = io.BytesIO()
        Image.new("RGB", (200, 200), "red").save(buffer, "PNG")
        response = io.BytesIO(buffer.getvalue())
        response.url = "https://example.invalid/image.png"
        images = Images({"image_source": "url", "image_url": response.url, "accent": "red", "api_key": "secret"})
        with patch("server.urlopen", return_value=response) as fetch:
            _, first = images.render(800, 480)
            _, second = images.render(800, 480)
            self.assertEqual(first, second)
            fetch.assert_called_once_with(response.url, timeout=10)

    def test_requires_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text('{"api_key": ""}')
            with self.assertRaises(ValueError):
                load_options(path)


if __name__ == "__main__":
    unittest.main()
