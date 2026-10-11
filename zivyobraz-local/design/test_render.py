import json
from pathlib import Path
import unittest

from render import Components


class DesignTests(unittest.TestCase):
    def test_demo_geometry_and_palette(self):
        data = json.loads(Path(__file__).with_name("demo.json").read_text())
        self.assertTrue(data["demo"])
        image = Components("/usr/share/fonts/truetype/dejavu").render(data)
        self.assertEqual(image.size, (800, 480))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(set(image.getdata()), {(255, 255, 255), (0, 0, 0), (255, 0, 0)})

    def test_missing_and_long_values_render_without_failure(self):
        components = Components("/usr/share/fonts/truetype/dejavu")
        components.text(0, 0, "Long description " * 100, max_width=10)
        image = components.render({"demo": True})
        self.assertEqual(image.size, (800, 480))


if __name__ == "__main__":
    unittest.main()
