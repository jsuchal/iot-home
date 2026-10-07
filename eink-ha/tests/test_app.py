import io
import json
import sys
import threading
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import (
    Display,
    HomeAssistant,
    Metric,
    Server,
    Settings,
    SourceError,
    schedule_slot,
    sleep_until_update,
)


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class Source:
    def __init__(self):
        self.data = ["12,4 °C", "22,1 °C", "742 ppm"]
        self.calls = 0
        self.fail = False

    def values(self):
        self.calls += 1
        if self.fail:
            raise SourceError("Test outage")
        return self.data


def settings(**kwargs):
    defaults = {
        "device_key": "12345678",
        "metrics": (
            Metric("sensor.outdoor", "Vonku"),
            Metric("sensor.indoor", "Doma"),
            Metric("sensor.co2", "CO₂"),
        ),
        "refresh_seconds": 1,
    }
    return Settings(**(defaults | kwargs))


PAYLOAD = {
    "apiVersion": "3.2",
    "display": {"width": 800, "height": 480, "colorType": "3C"},
    "network": {"ssid": "not-rendered"},
}


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.source = Source()
        self.server = Server(("127.0.0.1", 0), settings(), self.source)
        self.context = running(self.server)
        self.port = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def request(
        self,
        payload=PAYLOAD,
        path="/index.php?timestampCheck=1",
        key="12345678",
        raw=None,
    ):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(
            "POST",
            path,
            json.dumps(payload) if raw is None else raw,
            {"Content-Type": "application/json", "X-API-Key": key},
        )
        response = conn.getresponse()
        result = response.status, response.getheaders(), response.read()
        conn.close()
        return result

    def test_firmware_response_and_three_color_png(self):
        status, headers, body = self.request()
        headers = dict(headers)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(int(headers["Content-Length"]), len(body))
        self.assertEqual(headers["Connection"], "close")
        self.assertEqual(headers["PreciseSleep"], "1800")
        self.assertTrue(0 < int(headers["Timestamp"]) <= 0x7FFFFFFF)
        self.assertNotIn("X-OTA-Update", headers)
        self.assertNotIn("Rotate", headers)
        self.assertNotIn("Transfer-Encoding", headers)
        with Image.open(io.BytesIO(body)) as image:
            self.assertEqual(image.size, (800, 480))
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(
                {color for _, color in image.getcolors()},
                {(0, 0, 0), (255, 255, 255), (255, 0, 0)},
            )

    def test_snapshot_is_stable_for_repeated_page_downloads(self):
        _, headers, original = self.request()
        display = Display.from_payload(PAYLOAD)
        self.server.frames.cached[display] = replace(
            self.server.frames.cached[display], created=0
        )
        self.source.data = ["99 °C", "99 °C", "9999 ppm"]
        for _ in range(3):
            status, repeated_headers, body = self.request(
                path="/index.php?timestampCheck=0"
            )
            self.assertEqual(status, 200)
            self.assertEqual(body, original)
            self.assertEqual(
                dict(repeated_headers)["Timestamp"], dict(headers)["Timestamp"]
            )
        self.assertEqual(self.source.calls, 1)
        _, new_headers, new_body = self.request()
        self.assertNotEqual(new_body, original)
        self.assertNotEqual(dict(new_headers)["Timestamp"], dict(headers)["Timestamp"])

    def test_cached_frame_survives_ha_outage(self):
        first = self.request()
        display = Display.from_payload(PAYLOAD)
        self.server.frames.cached[display] = replace(
            self.server.frames.cached[display], created=0
        )
        self.source.fail = True
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body, first[2])
        self.assertEqual(dict(headers)["Timestamp"], dict(first[1])["Timestamp"])

    def test_first_ha_failure_is_not_an_image(self):
        self.source.fail = True
        status, headers, _ = self.request()
        self.assertEqual(status, 503)
        self.assertNotIn("Timestamp", dict(headers))

    def test_wrong_key_does_not_fetch_ha(self):
        self.assertEqual(self.request(key="wrong")[0], 401)
        self.assertEqual(self.source.calls, 0)

    def test_invalid_requests_do_not_render(self):
        for payload in (
            {},
            [],
            {"display": {"width": True, "height": 480}},
            {"display": {"width": 99999, "height": 480}},
            {"display": {"width": 800, "height": 480, "colorType": "invalid"}},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.request(payload=payload)[0], 400)
        self.assertEqual(self.request(raw="{broken")[0], 400)
        self.assertEqual(self.request(raw="x" * 32769)[0], 413)
        self.assertEqual(
            self.request(path="/index.php?timestampCheck=1&timestampCheck=0")[0], 400
        )
        self.assertEqual(self.request(path="/elsewhere?timestampCheck=1")[0], 404)
        self.assertEqual(self.source.calls, 0)

    def test_bw_does_not_have_red_pixels(self):
        payload = {"display": {"width": 800, "height": 480, "colorType": "BW"}}
        status, _, body = self.request(payload=payload)
        self.assertEqual(status, 200)
        with Image.open(io.BytesIO(body)) as image:
            self.assertEqual(
                {color for _, color in image.getcolors()}, {(0, 0, 0), (255, 255, 255)}
            )

    def test_health_is_a_process_check(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/health")
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"status": "ok"})
        conn.close()
        self.assertEqual(self.source.calls, 0)

    def test_schedule_is_sent_in_precise_sleep_header(self):
        with patch("app.sleep_until_update", return_value=123):
            status, headers, _ = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(dict(headers)["PreciseSleep"], "123")

    def test_schedule_refreshes_at_slot_even_with_long_cache_interval(self):
        self.server.frames.settings = settings(
            update_times=("07:00",), refresh_seconds=86400
        )
        with patch("app.schedule_slot", side_effect=[100, 100, 200]):
            first = self.request()
            self.source.data = ["99 °C", "99 °C", "9999 ppm"]
            second = self.request()
            third = self.request()
        self.assertEqual(first[2], second[2])
        self.assertNotEqual(first[2], third[2])
        self.assertEqual(self.source.calls, 2)


class HAHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append((self.path, self.headers.get("Authorization")))
        status = self.server.status
        if status == 200:
            body = json.dumps(
                {
                    "state": self.server.state,
                    "attributes": {"unit_of_measurement": "°C"},
                }
            ).encode()
        else:
            body = b"{}"
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "/redirect-target")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class HomeAssistantTests(unittest.TestCase):
    def setUp(self):
        self.ha = ThreadingHTTPServer(("127.0.0.1", 0), HAHandler)
        self.ha.requests = []
        self.ha.status = 200
        self.ha.state = "22.10"
        self.context = running(self.ha)
        port = self.context.__enter__()
        self.source = HomeAssistant(
            settings(
                ha_url=f"http://127.0.0.1:{port}",
                metrics=(Metric("sensor.indoor", "Doma"),),
            ),
            "test-ha-token",
        )

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_rest_api_auth_and_numeric_value(self):
        self.assertEqual(self.source.values(), ["22,1 °C"])
        self.assertEqual(
            self.ha.requests, [("/api/states/sensor.indoor", "Bearer test-ha-token")]
        )

    def test_device_to_ha_to_png_over_http(self):
        server = Server(("127.0.0.1", 0), self.source.settings, self.source)
        with running(server) as port:
            conn = HTTPConnection("127.0.0.1", port, timeout=3)
            conn.request(
                "POST",
                "/index.php?timestampCheck=1",
                json.dumps(PAYLOAD),
                {"Content-Type": "application/json", "X-API-Key": "12345678"},
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            with Image.open(io.BytesIO(response.read())) as image:
                self.assertEqual(image.size, (800, 480))
            conn.close()
        self.assertEqual(
            self.ha.requests,
            [("/api/states/sensor.indoor", "Bearer test-ha-token")],
        )

    def test_missing_entity_is_unavailable(self):
        self.ha.status = 404
        self.assertEqual(self.source.values(), ["Nedostupné"])

    def test_unavailable_and_nonfinite_values(self):
        for state in ("unknown", "unavailable", "NaN", "Infinity"):
            with self.subTest(state=state):
                self.ha.state = state
                self.assertEqual(self.source.values(), ["Nedostupné"])

    def test_auth_failure_is_not_a_successful_value(self):
        self.ha.status = 401
        with self.assertRaises(SourceError):
            self.source.values()

    def test_redirect_does_not_forward_token(self):
        self.ha.status = 302
        with self.assertRaises(SourceError):
            self.source.values()
        self.assertEqual(len(self.ha.requests), 1)


class ScheduleTests(unittest.TestCase):
    def test_empty_schedule_preserves_interval(self):
        self.assertEqual(sleep_until_update(settings()), 1800)
        self.assertIsNone(schedule_slot(settings()))

    def test_next_time_and_midnight(self):
        config = settings(update_times=("07:00", "12:30", "19:00"))
        zone = ZoneInfo(config.timezone)
        self.assertEqual(
            sleep_until_update(config, datetime(2026, 10, 7, 6, 59, tzinfo=zone)), 60
        )
        self.assertEqual(
            sleep_until_update(config, datetime(2026, 10, 7, 12, 30, tzinfo=zone)),
            23400,
        )
        self.assertEqual(
            sleep_until_update(config, datetime(2026, 10, 7, 23, 0, tzinfo=zone)), 28800
        )

    def test_configured_timezone_and_subminute_delay(self):
        config = settings(update_times=("07:00",))
        self.assertEqual(
            sleep_until_update(
                config, datetime(2026, 7, 1, 4, 50, tzinfo=ZoneInfo("UTC"))
            ),
            600,
        )
        self.assertEqual(
            sleep_until_update(
                config,
                datetime(
                    2026, 7, 1, 6, 59, 59, 500000, tzinfo=ZoneInfo(config.timezone)
                ),
            ),
            1,
        )

    def test_spring_nonexistent_time_is_skipped(self):
        config = settings(update_times=("02:30", "03:30"))
        now = datetime(2026, 3, 29, 1, 30, tzinfo=ZoneInfo(config.timezone))
        self.assertEqual(sleep_until_update(config, now), 3600)
        self.assertEqual(
            sleep_until_update(settings(update_times=("02:30",)), now), 86400
        )

    def test_autumn_ambiguous_time_runs_only_at_first_occurrence(self):
        config = settings(update_times=("02:30",))
        zone = ZoneInfo(config.timezone)
        self.assertEqual(
            sleep_until_update(config, datetime(2026, 10, 25, 1, 30, tzinfo=zone)), 3600
        )
        self.assertEqual(
            sleep_until_update(
                config, datetime(2026, 10, 25, 2, 0, tzinfo=zone, fold=1)
            ),
            88200,
        )

    def test_daily_sleep_can_span_25_hour_day(self):
        config = settings(update_times=("07:00",))
        self.assertEqual(
            sleep_until_update(
                config, datetime(2026, 10, 24, 7, 0, tzinfo=ZoneInfo(config.timezone))
            ),
            90000,
        )

    def test_schedule_config_validation_and_normalization(self):
        example = Path(__file__).resolve().parents[1] / "config.example.json"
        options = json.loads(example.read_text())
        with TemporaryDirectory() as directory:
            config = Path(directory) / "options.json"
            for invalid in (
                ["7:00"],
                ["24:00"],
                ["12:60"],
                ["12:30:00"],
                "07:00",
                [None],
            ):
                options["update_times"] = invalid
                config.write_text(json.dumps(options))
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    Settings.load(config)
            options["update_times"] = ["19:00", "07:00", "07:00"]
            config.write_text(json.dumps(options))
            self.assertEqual(Settings.load(config).update_times, ("07:00", "19:00"))


class ConfigurationTests(unittest.TestCase):
    def test_example_loads_without_a_real_token_in_demo(self):
        filename = Path(__file__).resolve().parents[1] / "config.example.json"
        config = Settings.load(filename, demo=True)
        self.assertEqual(len(HomeAssistant(config, None).values()), 3)

    def test_live_mode_requires_a_token(self):
        with self.assertRaises(ValueError):
            HomeAssistant(settings(), None)


if __name__ == "__main__":
    unittest.main()
