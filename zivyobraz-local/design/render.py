#!/usr/bin/env python3
"""Independent, white-background components inspired by Weatherman.

No source code, fonts or bitmap assets copied from Weatherman.
Input is a JSON snapshot; this does NOT fetch live Home Assistant data.
CC-BY-NC-SA-4.0; see ../addon/NOTICE.md.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)


class Components:
    def __init__(self, font_dir):
        self.image = Image.new("RGB", (800, 480), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.font_dir = Path(font_dir)
        self.fonts = {}

    def font(self, size, bold=False):
        key = size, bold
        if key not in self.fonts:
            filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            self.fonts[key] = ImageFont.truetype(str(self.font_dir / filename), size)
        return self.fonts[key]

    def text(self, x, y, value, size=18, bold=False, color=BLACK, max_width=None):
        value = str(value)
        font = self.font(size, bold)
        if max_width is not None:
            original = value
            while value and self.draw.textlength(value, font=font) > max_width:
                original = original[:-1]
                value = original + "…" if original else ""
        self.draw.text((x, y), value, font=font, fill=color, anchor="lt")

    def icon(self, kind, x, y, size=64):
        # Draw our own geometric line icons, independent of external icon packs.
        scale = size / 64
        def box(values):
            return tuple((x if i % 2 == 0 else y) + v * scale for i, v in enumerate(values))
        width = max(2, round(3 * scale))
        if kind == "sun":
            self.draw.ellipse(box((20, 20, 44, 44)), outline=BLACK, width=width)
            for angle in range(0, 360, 45):
                a = math.radians(angle)
                self.draw.line((x + (32 + 20 * math.cos(a)) * scale,
                                y + (32 + 20 * math.sin(a)) * scale,
                                x + (32 + 29 * math.cos(a)) * scale,
                                y + (32 + 29 * math.sin(a)) * scale), fill=BLACK, width=width)
        else:
            # Single continuous cloud outline, avoiding overlapping circle edges.
            points = [(5, 41), (5, 31), (10, 25), (18, 25), (20, 16), (27, 11),
                      (37, 11), (44, 17), (46, 25), (54, 25), (60, 31), (60, 41),
                      (55, 46), (10, 46), (5, 41)]
            self.draw.line([(x + px * scale, y + py * scale) for px, py in points],
                           fill=BLACK, width=width, joint="curve")
            if kind == "rain":
                for px in (18, 32, 46):
                    self.draw.line(box((px, 51, px - 3, 60)), fill=BLACK, width=width)

    def weather(self, x, y, data):
        self.icon(data.get("icon", "cloud"), x, y + 8, 84)
        self.text(x + 108, y, data.get("temperature", "—"), 88)
        self.text(x + 112, y + 100, data.get("description", "Údaje nedostupné"), 24, max_width=340)
        self.text(x, y + 147, data.get("detail", ""), 17, max_width=470)

    def forecast(self, x, y, entries):
        for index, entry in enumerate(entries[:3]):
            left = x + index * 168
            self.text(left, y, entry.get("label", ""), 13, bold=True, max_width=152)
            self.icon(entry.get("icon", "cloud"), left, y + 34, 44)
            self.text(left + 59, y + 32, entry.get("temperature", "—"), 31, max_width=96)
            self.text(left, y + 93, entry.get("detail", ""), 16, max_width=150)

    def metrics(self, x, y, entries):
        for index, entry in enumerate(entries[:2]):
            top = y + index * 108
            self.text(x, top, entry.get("label", ""), 13, bold=True, max_width=210)
            self.text(x, top + 29, entry.get("value", "—"), 42, max_width=214)
            self.text(x, top + 79, entry.get("unit", ""), 16, max_width=214)

    def notice(self, x, y, data):
        color = RED if data.get("warning") else BLACK
        self.draw.line((x, y, x + 28, y), fill=color, width=4)
        self.text(x, y + 19, data.get("title", ""), 14, bold=True, color=color, max_width=214)
        self.text(x, y + 47, data.get("text", ""), 17, max_width=214)

    def render(self, data):
        self.text(32, 27, data.get("heading", "DOMA"), 18, bold=True, max_width=480)
        self.text(32, 59, data.get("date", ""), 18, max_width=480)
        self.draw.line((552, 30, 552, 421), fill=BLACK, width=1)
        self.weather(32, 106, data.get("weather", {}))
        self.draw.line((32, 294, 520, 294), fill=BLACK, width=1)
        self.forecast(32, 319, data.get("forecast", []))
        self.metrics(584, 35, data.get("metrics", []))
        self.notice(584, 312, data.get("notice", {}))
        self.text(32, 452, "UKÁŽKA · NIE ŽIVÉ ÚDAJE" if data.get("demo") else "POSLEDNÁ AKTUALIZÁCIA", 12)
        self.text(584, 448, "Aktualizované " + data.get("updated", "—"), 12, max_width=214)
        # Anti-aliased fonts must be quantized to the physical three-color palette.
        palette = Image.new("P", (1, 1))
        palette.putpalette([*WHITE, *BLACK, *RED] + list(WHITE) * 253)
        return self.image.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(__file__).with_name("demo.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("preview.png"))
    parser.add_argument("--font-dir", default="/usr/share/fonts/truetype/dejavu")
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    Components(args.font_dir).render(data).save(args.output, "PNG")
    print(f"Saved {args.output} (800×480 RGB PNG; data source: {'DEMO' if data.get('demo') else 'JSON snapshot'})")


if __name__ == "__main__":
    main()
