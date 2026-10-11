import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from PIL import Image, ImageChops
from weatherman_preview import WeathermanPreview, rounded_temperature, prepare_data, temperature_color


class WeathermanPreviewTests(unittest.TestCase):
    def data(self):
        return {"weather": {"temperature": "12,9°C", "condition": "partlycloudy", "description": "Polojasno"},
                "forecast": [{"label": "12:00", "temperature": "16°", "condition": "sunny", "detail": "Zrážky 0,0 mm"},
                             {"label": "15:00", "temperature": "17°", "condition": "partlycloudy"},
                             {"label": "18:00", "temperature": "15°", "condition": "cloudy"}],
                "daily": [{"label": "Pondelok", "condition": "sunny", "low": "7°", "high": "16°", "rain": ""},
                          {"label": "Utorok", "condition": "rainy", "low": "5°", "high": "15°", "rain": "0,7 mm"},
                          {"label": "Streda", "condition": "cloudy", "low": "4°", "high": "13°", "rain": ""}],
                "updated": "11.10. 11:13"}

    def test_dark_palette_and_safe_content_area(self):
        for notice in ({}, {"warning": True, "title": "ZASTARANÉ ÚDAJE"}):
            image = WeathermanPreview().render(self.data() | {"notice": notice})
            self.assertEqual(image.size, (480, 800))
            self.assertTrue(set(image.getdata()) <= {(0, 0, 0), (255, 255, 255), (255, 0, 0)})
            bounds = ImageChops.difference(image, Image.new("RGB", image.size, "black")).getbbox()
            self.assertGreaterEqual(bounds[0], 30)
            self.assertGreaterEqual(bounds[1], 70)
            self.assertLessEqual(bounds[2], 450)
            self.assertLessEqual(bounds[3], 730)

    def test_negative_and_missing_temperatures(self):
        self.assertEqual(rounded_temperature("−12,9°C"), "-13°C")
        self.assertEqual(rounded_temperature("12,9°C"), "13°C")
        self.assertEqual(rounded_temperature("—"), "—")
        image = WeathermanPreview().render({"weather": {"temperature": "−123,9°C"}})
        self.assertEqual(image.size, (480, 800))

    def test_real_hourly_wind_and_future_daily_values(self):
        now = datetime(2026, 10, 11, 8, 30, tzinfo=timezone.utc)
        snapshot = {"entity": "weather.forecast_home", "kind": "hourly", "fetched": now.isoformat(),
                    "state": {"state": "partlycloudy", "attributes": {"temperature": 12.9,
                              "temperature_unit": "°C", "wind_speed_unit": "km/h", "precipitation_unit": "mm"}},
                    "forecast": [{"datetime": f"2026-10-11T{hour:02d}:00:00+00:00", "condition": "sunny",
                                  "temperature": 16, "wind_speed": hour + 1} for hour in (10, 13, 16)]}
        daily = [{"datetime": (now + timedelta(days=n)).isoformat(), "condition": "rainy",
                  "temperature": 16 - n, "templow": 7 - n, "precipitation": 0 if n != 2 else .7}
                 for n in range(4)]
        data = prepare_data(snapshot, daily)
        self.assertEqual([entry["wind"] for entry in data["forecast"]], ["11 km/h", "14 km/h", "17 km/h"])
        self.assertEqual([entry["label"] for entry in data["daily"]], ["Pondelok", "Utorok", "Streda"])
        self.assertEqual([entry["rain"] for entry in data["daily"]], ["", "0,7 mm", ""])
        self.assertEqual(data["daily"][0]["low"], "6°")
        self.assertEqual(data["daily"][0]["high"], "15°")

    def test_render_omits_zero_rain_and_conditions_heading(self):
        preview = WeathermanPreview()
        with patch.object(preview, "text", wraps=preview.text) as text:
            preview.render(self.data())
        labels = [call.args[2] for call in text.call_args_list]
        self.assertNotIn("PODMIENKY", labels)
        self.assertNotIn("0,0 mm", labels)
        self.assertIn("0,7 mm", labels)
        self.assertIn("NAJBLIŽŠIE DNI", labels)
        self.assertFalse(any(str(label).startswith("Aktualizované") for label in labels))

    def test_large_icon_and_temperature_visible_centers_align(self):
        for condition in ("sunny", "partlycloudy", "cloudy", "clear-night", "rainy", "unknown"):
            for temperature in ("15°C", "−13°C", "−123°C"):
                data = self.data()
                data["weather"].update(condition=condition, temperature=temperature)
                _, heights, tops = WeathermanPreview().place(data)
                image = WeathermanPreview().render(data)
                top, height = tops[1], heights[1]
                centers = []
                for x0, x1 in ((30, 160), (165, 450)):
                    box = (x0, round(top) - 8, x1, round(top + height) + 8)
                    region = image.crop(box)
                    bounds = ImageChops.difference(region, Image.new("RGB", region.size, "black")).getbbox()
                    self.assertIsNotNone(bounds)
                    centers.append(box[1] + (bounds[1] + bounds[3]) / 2)
                with self.subTest(condition=condition, temperature=temperature):
                    self.assertLessEqual(abs(centers[0] - centers[1]), 1)

    def test_demo_red_highlights_are_explicit_and_scoped(self):
        data = self.data() | {"demo": True}
        data["forecast"][0].update(wind="45 km/h", wind_warning=True)
        data["forecast"][1].update(wind="20 km/h")
        data["daily"][2].update(condition="rainy", rain="12 mm", rain_warning=True)
        preview = WeathermanPreview()
        with patch.object(preview, "text", wraps=preview.text) as text:
            image = preview.render(data)
        calls = {call.args[2]: call.kwargs for call in text.call_args_list}
        self.assertIn("UKÁŽKA", calls)
        self.assertEqual(calls["45 km/h"]["color"], (255, 0, 0))
        self.assertEqual(calls["20 km/h"]["color"], (255, 255, 255))
        self.assertEqual(calls["12 mm"]["color"], (255, 0, 0))
        self.assertEqual(set(image.getdata()), {(0, 0, 0), (255, 255, 255)})

    def test_temperature_thresholds_are_strict_and_missing_is_not_cold(self):
        for value in (0, 14.9, 15, 28, "0°C", "15°C", "28°", None, True, float("nan"), float("inf"), "—", "40°F"):
            self.assertEqual(temperature_color(value), (255, 255, 255))
        for value in (-0.1, 28.1, -5, "-0,1°C", "28,1°", "−5°C"):
            self.assertEqual(temperature_color(value), (255, 0, 0))

    def test_daily_minimum_and_maximum_are_colored_independently(self):
        preview = WeathermanPreview()
        with patch.object(preview, "text", wraps=preview.text) as text:
            preview.temperature_pair(240, 674, {"low": "-1°", "high": "25°"})
        self.assertEqual(text.call_args_list[0].kwargs["color"], (255, 0, 0))
        self.assertEqual(text.call_args_list[1].kwargs["color"], (255, 255, 255))
        self.assertEqual(text.call_args_list[2].kwargs["color"], (255, 255, 255))

    def test_thresholds_use_raw_values_before_rounding(self):
        preview = WeathermanPreview()
        with patch.object(preview, "text", wraps=preview.text) as text:
            preview.temperature_pair(240, 674, {"low": "0°", "high": "28°", "low_value": -0.2, "high_value": 28.2})
        self.assertEqual(text.call_args_list[0].kwargs["color"], (255, 0, 0))
        self.assertEqual(text.call_args_list[2].kwargs["color"], (255, 0, 0))


if __name__ == "__main__":
    unittest.main()
