import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components import Components, PORTRAIT_SAFE_AREA
from server import Images


class ReadabilityTests(unittest.TestCase):
    def data(self):
        return {"heading": "POČASIE", "date": "11.10.2026", "updated": "11.10. 10:41",
                "weather": {"temperature": "11,1°C", "description": "Polojasno", "detail": "Najbližšie hodiny"},
                "metrics": [{"label": "VLHKOSŤ", "value": "80", "unit": "%"},
                            {"label": "VIETOR", "value": "10,8", "unit": "km/h"}],
                "forecast": [{"label": "11:00", "temperature": "15°", "detail": "Zrážky 0,0 mm"}] * 3,
                "notice": {"warning": True, "title": "ZASTARANÉ ÚDAJE", "text": "Zdroj nedostupný"}}

    def assert_safe(self, image):
        bounds = ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox()
        self.assertIsNotNone(bounds)
        self.assertGreaterEqual(bounds[0], 10)
        self.assertGreaterEqual(bounds[1], 10)
        self.assertLessEqual(bounds[2], image.width - 10)
        self.assertLessEqual(bounds[3], image.height - 10)

    def test_portrait_raw_layout_fits_without_border_clipping(self):
        for demo in (True, False):
            components = Components("/usr/share/fonts/truetype/dejavu", portrait=True)
            components.render_portrait(self.data() | {"demo": demo})
            self.assert_safe(components.image)
            bounds = ImageChops.difference(components.image, Image.new("RGB", components.image.size, "white")).getbbox()
            self.assertGreaterEqual(bounds[0], PORTRAIT_SAFE_AREA[0])
            self.assertGreaterEqual(bounds[1], PORTRAIT_SAFE_AREA[1])
            self.assertLessEqual(bounds[2], PORTRAIT_SAFE_AREA[2])
            self.assertLessEqual(bounds[3], PORTRAIT_SAFE_AREA[3])
            for size in (18, 20, 22, 24, 26, 28, 40, 50):
                self.assertTrue(any(key[0] == size for key in components.fonts))

    def test_all_edges_remain_white_after_physical_rotation(self):
        for angle in ("0", "90", "180", "270"):
            components = Components("/usr/share/fonts/truetype/dejavu", portrait=angle in ("90", "270"))
            logical = components.render(self.data())
            images = Images({"image_source": "test", "accent": "red", "rotation": angle})
            with patch.object(images, "source", return_value=logical):
                data, _ = images.render(800, 480)
            physical = Image.open(io.BytesIO(data))
            self.assertEqual(physical.size, (800, 480))
            self.assert_safe(physical)
            if angle in ("90", "270"):
                bounds = ImageChops.difference(physical, Image.new("RGB", physical.size, "white")).getbbox()
                self.assertGreaterEqual(bounds[0], 70)
                self.assertGreaterEqual(bounds[1], 30)
                self.assertLessEqual(bounds[2], 730)
                self.assertLessEqual(bounds[3], 450)

    def test_long_labels_still_fit_safe_area(self):
        data = self.data()
        data["notice"]["title"] *= 20
        data["notice"]["text"] *= 20
        data["updated"] *= 20
        data["weather"]["temperature"] = "−1234,5°C"
        data["weather"]["description"] *= 20
        components = Components("/usr/share/fonts/truetype/dejavu", portrait=True)
        components.render_portrait(data)
        self.assert_safe(components.image)


if __name__ == "__main__":
    unittest.main()
