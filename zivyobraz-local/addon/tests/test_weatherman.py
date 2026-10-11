import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Images, load_options
from weatherman import LAYOUT_TOPS, SAFE_AREA, SIZE_DAY, SIZE_LABEL, Weatherman, prepare_data


class LiveWeathermanTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 11, 8, 30, tzinfo=timezone.utc)
        self.options = {"image_source": "homeassistant", "layout": "weatherman", "rotation": "90",
                        "accent": "red", "weather_entity": "weather.forecast_home", "forecast_type": "hourly",
                        "forecast_step_hours": "3", "timezone": "Europe/Prague", "cold_below_c": 0,
                        "hot_above_c": 28, "wind_above_kmh": 40, "rain_above_mm_day": 10}
        self.state = {"state": "sunny", "attributes": {"temperature": 30, "temperature_unit": "°C",
                      "wind_speed_unit": "km/h", "precipitation_unit": "mm"}}
        self.hourly = [{"datetime": f"2026-10-11T{h:02d}:00:00+00:00", "condition": "sunny",
                        "temperature": 30, "wind_speed": 45} for h in (10, 13, 16)]
        self.daily = [{"datetime": f"2026-10-{d:02d}T10:00:00+00:00", "condition": "rainy",
                       "temperature": 29, "templow": -2, "precipitation": 12} for d in (12, 13, 14)]

    def response(self, forecast):
        return {"service_response": {"weather.forecast_home": {"forecast": forecast}}}

    def snapshot(self):
        return {"entity": "weather.forecast_home", "kind": "hourly", "state": self.state,
                "forecast": self.hourly, "fetched": self.now.isoformat(), "daily_forecast": self.daily}

    def test_live_hourly_daily_renderer_native_png_and_no_demo(self):
        images = Images(self.options)
        with patch("weather.api", side_effect=[self.state, self.response(self.hourly), self.response(self.daily)]), \
             patch("server.datetime") as clock:
            clock.now.return_value = self.now
            # Align Weather's fetch/compose time too, without replacing datetime parsing.
            with patch.object(images.weather, "read", wraps=lambda: images.weather.__class__.read(images.weather, self.now)):
                data, timestamp = images.render(800, 480)
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (800, 480))
        self.assertEqual(set(image.getdata()), {(0, 0, 0), (255, 255, 255)})
        logical = image.transpose(Image.Transpose.ROTATE_270)
        bounds = ImageChops.difference(logical, Image.new("RGB", logical.size, "black")).getbbox()
        self.assertGreaterEqual(bounds[0], 30)
        self.assertGreaterEqual(bounds[1], 70)
        self.assertLessEqual(bounds[2], 450)
        self.assertLessEqual(bounds[3], 730)
        self.assertGreater(timestamp, 0)
        composed = prepare_data(images.weather.snapshot, self.daily, self.now, self.options)
        self.assertFalse(composed["demo"])
        self.assertTrue(composed["forecast"][0]["wind_warning"])
        self.assertTrue(composed["daily"][0]["rain_warning"])

    def test_day_names_are_larger_than_labels_without_truncation(self):
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        preview = Weatherman(display_mode="light")
        with patch.object(preview, "text", wraps=preview.text) as text:
            preview.render(data)
        calls = [(str(call.args[2]), call.args[3] if len(call.args) > 3 else call.kwargs["size"])
                 for call in text.call_args_list]
        by_value = {value: size for value, size in calls}
        self.assertEqual(by_value["Pondelok"], SIZE_DAY)
        self.assertEqual(by_value["45 km/h"], SIZE_LABEL)
        self.assertGreater(SIZE_DAY, SIZE_LABEL)
        self.assertFalse(any("…" in value for value, _ in calls))

    def test_explicit_rhythm_keeps_column_items_grouped(self):
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        preview = Weatherman()
        for payload in (data, {"demo": True}, {"weather": {"temperature": "−123,9°C"}}):
            _, heights, tops = preview.place(payload)
            self.assertEqual(tops, list(LAYOUT_TOPS[:len(tops)]))
            self.assertGreaterEqual(tops[0], SAFE_AREA[1])
            self.assertLessEqual(round(tops[-1] + heights[-1], 6), SAFE_AREA[3])
            # Items in one hourly column sit closer together than the block gap.
            within_hourly = tops[4] - (tops[3] + heights[3])
            before_section = tops[6] - (tops[5] + heights[5])
            self.assertLess(within_hourly, before_section)

    def test_condition_description_is_not_drawn(self):
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        preview = Weatherman()
        with patch.object(preview, "text", wraps=preview.text) as text:
            preview.render(data)
        values = [str(call.args[2]) for call in text.call_args_list]
        self.assertNotIn("Slnečno", values)

    def test_units_and_configured_thresholds_use_raw_values(self):
        self.state["attributes"].update(temperature=86, temperature_unit="°F", wind_speed_unit="m/s", precipitation_unit="in")
        self.hourly[0].update(temperature=86, wind_speed=12)
        self.daily[0].update(temperature=86, templow=30, precipitation=.5)
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        self.assertTrue(data["weather"]["temperature_warning"])
        self.assertTrue(data["forecast"][0]["wind_warning"])
        self.assertTrue(data["daily"][0]["rain_warning"])
        self.assertTrue(data["daily"][0]["low_warning"])
        data = prepare_data(self.snapshot(), self.daily, self.now,
                            self.options | {"hot_above_c": 35, "wind_above_kmh": 50, "rain_above_mm_day": 20})
        self.assertFalse(data["weather"]["temperature_warning"])
        self.assertFalse(data["forecast"][0]["wind_warning"])
        self.assertFalse(data["daily"][0]["rain_warning"])

    def test_missing_units_and_zero_rain_do_not_create_warnings(self):
        self.state["attributes"] = {"temperature": 30}
        self.daily[0]["precipitation"] = 0
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        self.assertFalse(data["weather"]["temperature_warning"])
        self.assertFalse(data["forecast"][0]["wind_warning"])
        self.assertFalse(data["daily"][0]["rain_warning"])
        self.assertEqual(data["daily"][0]["rain"], "")

    def test_hourly_rain_replaces_wind_only_when_measurable(self):
        self.hourly[0]["precipitation"] = 0.4
        self.hourly[1]["wind_speed"] = 3
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        self.assertEqual(data["forecast"][0]["rain"], "0,4 mm")
        self.assertFalse(data["forecast"][0]["rain_warning"])
        self.assertEqual(data["forecast"][1]["rain"], "")
        self.assertTrue(data["forecast"][1]["wind_small"])
        rows = Weatherman().layout(data)
        kinds = [cell[0] for cell in rows[5]]
        self.assertEqual(kinds, ["icontext", "text", "icontext"])
        icons = [cell[2] for cell in rows[5] if cell[0] == "icontext"]
        self.assertEqual(icons, ["water", "windy"])
        self.assertEqual(rows[5][1][2], "")
        image = Weatherman().render(data)
        self.assertEqual(image.size, (480, 800))

    def test_negligible_and_missing_wind_stay_empty(self):
        self.hourly[0]["wind_speed"] = 5.9
        self.hourly[1]["wind_speed"] = 6
        self.hourly[2].pop("wind_speed")
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        rows = Weatherman().layout(data)
        self.assertEqual(rows[5][0][2], "")
        self.assertEqual(rows[5][1][0], "icontext")
        self.assertEqual(rows[5][2], ("text", 380, "", 22, 400, (255, 255, 255), 130))

    def test_daily_detail_mirrors_hourly_rain_wind_and_calm(self):
        self.daily[0]["precipitation"] = 14
        self.daily[0]["wind_speed"] = 45
        self.daily[1]["precipitation"] = 0
        self.daily[1]["wind_speed"] = 4
        self.daily[2]["precipitation"] = 0
        self.daily[2]["wind_speed"] = 20
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        rows = Weatherman().layout(data)
        daily_row = rows[10]
        self.assertEqual(daily_row[0][0], "icontext")
        self.assertEqual(daily_row[0][2], "water")
        self.assertEqual(daily_row[1][2], "")
        self.assertEqual(daily_row[2][2], "windy")
        _, heights, tops = Weatherman().place(data)
        self.assertLessEqual(round(tops[-1] + heights[-1], 6), 730)

    def test_hourly_rain_threshold_is_strict_and_unit_aware(self):
        self.state["attributes"]["precipitation_unit"] = "in"
        self.hourly[0]["precipitation"] = 0.16  # Just over 4 mm/h.
        self.hourly[1]["precipitation"] = 4 / 25.4  # Exactly 4 mm/h: stays white.
        self.hourly[2]["precipitation"] = 0.04  # Trace amount.
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        self.assertTrue(data["forecast"][0]["rain_warning"])
        self.assertFalse(data["forecast"][1]["rain_warning"])
        self.assertEqual(data["forecast"][2]["rain"], "<0,1 in")

    def test_hourly_rain_icon_matches_detail_threshold(self):
        for entry, amount in zip(self.hourly, (4.1, 4, 0.5)):
            entry.update(condition="rainy", precipitation=amount)
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        rows = Weatherman().layout(data)
        expected = [(255, 0, 0), (255, 255, 255), (255, 255, 255)]
        self.assertEqual([cell[-1] for cell in rows[3]], expected)
        self.assertEqual([cell[-1] for cell in rows[5]], expected)
        for mode in ("light", "dark"):
            image = Weatherman(display_mode=mode).render(data)
            if mode == "light":
                self.assertIn((255, 0, 0), set(image.crop((35, 365, 165, 425)).getdata()))
            else:
                self.assertNotIn((255, 0, 0), set(image.getdata()))
            self.assertNotIn((255, 0, 0), set(image.crop((175, 365, 305, 425)).getdata()))

    def test_stale_notice_is_kept_when_data_is_enriched(self):
        data = {"weather": {}, "forecast": [], "notice": {"warning": True, "title": "ZASTARANÉ ÚDAJE"}}
        enriched = prepare_data(self.snapshot(), self.daily, self.now, self.options, data=data)
        self.assertEqual(enriched["notice"]["title"], "ZASTARANÉ ÚDAJE")

    def test_threshold_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            for change in ({"cold_below_c": 30}, {"wind_above_kmh": -1}, {"hot_above_c": True},
                           {"rain_above_mm_day": float("nan")}, {"rotation": "0"}, {"display_mode": "invalid"},
                           {"rain_above_mm_hour": "4"}):
                path.write_text(json.dumps(self.options | {"api_key": "test-key"} | change))
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_options(path)

    def test_dark_mode_is_monochrome_and_light_preserves_highlights(self):
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        dark = Weatherman().render(data)
        light = Weatherman(display_mode="light").render(data)
        self.assertEqual(light.size, dark.size)
        self.assertIn((255, 0, 0), set(light.getdata()))
        self.assertEqual(set(dark.getdata()), {(0, 0, 0), (255, 255, 255)})
        swaps = {(255, 255, 255): (0, 0, 0), (0, 0, 0): (255, 255, 255), (255, 0, 0): (255, 255, 255)}
        self.assertEqual(list(dark.getdata()), [swaps[pixel] for pixel in light.getdata()])

    def test_explicit_dark_mode_is_pixel_identical_to_default(self):
        data = prepare_data(self.snapshot(), self.daily, self.now, self.options)
        self.assertEqual(Weatherman().render(data).tobytes(), Weatherman(display_mode="dark").render(data).tobytes())


if __name__ == "__main__":
    unittest.main()
