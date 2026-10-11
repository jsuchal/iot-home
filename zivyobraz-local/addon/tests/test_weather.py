import json
import tempfile
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Images
from weather import Weather, api, number, NoRedirect


class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 11, 8, 15, tzinfo=timezone.utc)
        self.options = {"weather_entity": "weather.forecast_home", "forecast_type": "hourly", "forecast_step_hours": "1", "timezone": "Europe/Prague"}
        self.state = {"state": "sunny", "attributes": {"temperature": 11.1, "temperature_unit": "°C",
                      "humidity": 80, "wind_speed": 10.8, "wind_speed_unit": "km/h", "precipitation_unit": "mm"}}
        self.forecast = [{"datetime": (self.now + timedelta(hours=n)).isoformat(), "condition": "rainy",
                          "temperature": 12 + n, "precipitation": .2} for n in range(4)]

    def response(self):
        return {"service_response": {"weather.forecast_home": {"forecast": json.loads(json.dumps(self.forecast))}}}

    def test_real_fields_future_only_timezone_and_cache(self):
        weather = Weather(self.options)
        with patch("weather.api", side_effect=[self.state, self.response()]) as read:
            data = weather.read(self.now)
            weather.read(self.now)
            self.assertEqual(read.call_count, 2)
            self.assertEqual(read.call_args_list[1].args[1], {"entity_id": "weather.forecast_home", "type": "hourly"})
        self.assertFalse(data["demo"])
        self.assertEqual(data["weather"]["temperature"], "11,1°C")
        self.assertEqual(len(data["forecast"]), 3)
        self.assertEqual(data["forecast"][0]["label"], "11:15")
        self.assertEqual(data["forecast"][0]["detail"], "Zrážky 0,2 mm")

    def test_weatherman_fetches_both_forecasts_and_preserves_good_cache_on_failure(self):
        options = self.options | {"layout": "weatherman"}
        weather = Weather(options)
        daily = {"service_response": {"weather.forecast_home": {"forecast": [
            {"datetime": "2026-10-12T10:00:00+00:00", "temperature": 16, "templow": 7}]}}}
        with patch("weather.api", side_effect=[self.state, self.response(), daily]) as read:
            weather.read(self.now)
        self.assertEqual(read.call_count, 3)
        self.assertEqual(read.call_args_list[2].args[1]["type"], "daily")
        previous = weather.snapshot
        weather.checked = None
        with patch("weather.api", side_effect=[self.state, self.response(), OSError]):
            data = weather.read(self.now)
        self.assertIs(weather.snapshot, previous)
        self.assertTrue(data["notice"]["warning"])
        self.assertEqual(len(weather.snapshot["daily_forecast"]), 1)

    def test_classic_cache_is_not_used_for_missing_weatherman_daily_forecast(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            with patch("weather.api", side_effect=[self.state, self.response()]):
                Weather(self.options, path).read(self.now)
            self.assertIsNone(Weather(self.options | {"layout": "weatherman"}, path).snapshot)

    def test_three_hour_forecasts_use_local_clock_slots(self):
        self.options["forecast_step_hours"] = "3"
        self.forecast = [{"datetime": f"2026-10-11T{hour:02d}:00:00+00:00", "temperature": hour}
                         for hour in range(8, 22)]
        with patch("weather.api", side_effect=[self.state, self.response()]):
            data = Weather(self.options).read(self.now)
        self.assertEqual([f["label"] for f in data["forecast"]], ["12:00", "15:00", "18:00"])
        self.assertEqual([f["temperature"] for f in data["forecast"]], ["10°", "13°", "16°"])
        self.assertEqual(data["weather"]["detail"], "Predpoveď každé 3 hodiny")

    def test_three_hour_slots_across_midnight(self):
        self.options["forecast_step_hours"] = "3"
        now = datetime(2026, 10, 11, 20, 15, tzinfo=timezone.utc)
        self.forecast = [{"datetime": (now.replace(minute=0) + timedelta(hours=n)).isoformat()}
                         for n in range(1, 13)]
        with patch("weather.api", side_effect=[self.state, self.response()]):
            data = Weather(self.options).read(now)
        self.assertEqual([f["label"] for f in data["forecast"]], ["00:00", "03:00", "06:00"])

    def test_outage_uses_persistent_cache_and_marks_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            weather = Weather(self.options, path)
            with patch("weather.api", side_effect=[self.state, self.response()]):
                weather.read(self.now)
            restored = Weather(self.options, path)
            with patch("weather.api", side_effect=OSError("private message")):
                data = restored.read(self.now + timedelta(minutes=5))
            self.assertTrue(data["notice"]["warning"])
            self.assertEqual(data["notice"]["title"], "ZASTARANÉ ÚDAJE")
            self.assertEqual(data["updated"], "11.10. 10:15")
            self.assertEqual(data["weather"]["temperature"], "11,1°C")
            self.assertIsNone(Weather(self.options | {"forecast_type": "daily"}, path).snapshot)

    def test_no_cache_no_fabricated_weather(self):
        with patch("weather.api", side_effect=OSError), self.assertRaises(ValueError):
            Weather(self.options).read(self.now)

    def test_corrupt_cache_and_forecast_do_not_replace_good_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            path.write_text('{"entity":"weather.forecast_home","kind":"hourly"}')
            self.assertIsNone(Weather(self.options, path).snapshot)
            weather = Weather(self.options, path)
            with patch("weather.api", side_effect=[self.state, self.response()]):
                weather.read(self.now)
            previous = weather.snapshot
            weather.checked = None
            self.forecast[0]["datetime"] = "invalid"
            with patch("weather.api", side_effect=[self.state, self.response()]):
                data = weather.read(self.now)
            self.assertIs(weather.snapshot, previous)
            self.assertTrue(data["notice"]["warning"])

    def test_unavailable_and_missing_forecast(self):
        for state, response in ((self.state | {"state": "unavailable"}, self.response()),
                                (self.state, {"service_response": {"weather.forecast_home": {"forecast": []}}})):
            with patch("weather.api", side_effect=[state, response]), self.assertRaises(ValueError):
                Weather(self.options).read(self.now)

    def test_recovery_changes_stale_notice_back_to_live(self):
        weather = Weather(self.options)
        with patch("weather.api", side_effect=[self.state, self.response()]):
            weather.read(self.now)
        weather.checked = None
        with patch("weather.api", side_effect=OSError):
            self.assertTrue(weather.read(self.now)["notice"]["warning"])
        weather.checked = None
        with patch("weather.api", side_effect=[self.state, self.response()]):
            self.assertFalse(weather.read(self.now)["notice"]["warning"])

    def test_expired_forecast_is_not_presented_as_future(self):
        weather = Weather(self.options)
        with patch("weather.api", side_effect=[self.state, self.response()]):
            weather.read(self.now)
        data = weather.compose(self.now + timedelta(hours=5))
        self.assertEqual(data["forecast"], [])
        self.assertTrue(data["notice"]["warning"])

    def test_absent_values_are_not_zero(self):
        self.state["attributes"] = {}
        with patch("weather.api", side_effect=[self.state, self.response()]):
            data = Weather(self.options).read(self.now)
        self.assertEqual(data["weather"]["temperature"], "—")
        self.assertEqual(data["metrics"][0]["value"], "—")
        for value in (None, True, float("nan"), float("inf"), "12"):
            self.assertEqual(number(value), "—")

    def test_portrait_live_source_and_native_rotation(self):
        options = self.options | {"image_source": "homeassistant", "rotation": "90", "accent": "red"}
        images = Images(options)
        with patch.object(images.weather, "read", return_value={"demo": False, "weather": {"temperature": "11,1°C"}}):
            logical = images.source((480, 800))
            data, timestamp = images.render(800, 480)
        from PIL import Image
        import io
        physical = Image.open(io.BytesIO(data))
        self.assertEqual(logical.size, (480, 800))
        self.assertEqual(physical.size, (800, 480))
        self.assertGreater(timestamp, 0)

    def test_daily_minimum_and_unknown_condition(self):
        self.options["forecast_type"] = "daily"
        self.forecast[1]["templow"] = 7
        self.forecast[1]["condition"] = "unknown"
        with patch("weather.api", side_effect=[self.state, self.response()]):
            data = Weather(self.options).read(self.now)
        self.assertIn("Min 7°C", data["forecast"][0]["detail"])
        self.assertEqual(data["forecast"][0]["icon"], "unknown")

    def test_token_uses_fixed_proxy_and_cannot_redirect(self):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "private-test-token"}), patch("weather.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b"{}"
            api("states/weather.forecast_home")
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://supervisor/core/api/states/weather.forecast_home")
            self.assertEqual(request.get_header("Authorization"), "Bearer private-test-token")
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, None, None, None, None)


if __name__ == "__main__":
    unittest.main()
