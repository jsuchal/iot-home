#!/usr/bin/env python3
"""Independent, white-background components inspired by Weatherman.

No source code, fonts or bitmap assets copied from Weatherman.
Input is a JSON snapshot; this does NOT fetch live Home Assistant data.
CC-BY-NC-SA-4.0; see NOTICE.md.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
PORTRAIT_SAFE_AREA = (30, 70, 450, 730)


class Components:
    def __init__(self, font_dir, portrait=False):
        self.portrait = portrait
        self.image = Image.new("RGB", (480, 800) if portrait else (800, 480), WHITE)
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
        if kind == "unknown":
            self.text(x + 12 * scale, y + 8 * scale, "?", round(size * .7))
        elif kind == "moon":
            self.draw.ellipse(box((12, 8, 54, 52)), outline=BLACK, width=width)
            self.draw.ellipse(box((28, 4, 58, 38)), fill=WHITE)
        elif kind in ("wind", "fog"):
            for index in range(3):
                self.draw.line(box((5 + index * 4, 18 + index * 13, 59 - index * 4, 18 + index * 13)), fill=BLACK, width=width)
        elif kind == "sun":
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
            elif kind == "snow":
                for px in (18, 32, 46):
                    self.draw.line(box((px - 3, 55, px + 3, 55)), fill=BLACK, width=width)
                    self.draw.line(box((px, 52, px, 58)), fill=BLACK, width=width)
            elif kind == "storm":
                self.draw.line([box((33, 48)), box((25, 57)), box((35, 57)), box((27, 64))], fill=BLACK, width=width)

    def weather(self, x, y, data, max_width=470, show_detail=True):
        self.icon(data.get("icon", "cloud"), x, y + 8, 84)
        temperature = str(data.get("temperature", "—"))
        font_size = 88
        while font_size > 24 and self.draw.textlength(temperature, font=self.font(font_size)) > max_width - 108:
            font_size -= 1
        self.text(x + 108, y, temperature, font_size, max_width=max_width - 108)
        self.text(x + 112, y + 100, data.get("description", "Údaje nedostupné"), 28 if self.portrait else 24, max_width=min(340, max_width - 112))
        if show_detail:
            self.text(x, y + 147, data.get("detail", ""), 22 if self.portrait else 17, max_width=max_width)

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
        if self.portrait:
            self.render_portrait(data)
            return self.quantize()
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
        return self.quantize()

    def render_portrait(self, data):
        # Measured mat: roughly X20..460/Y60..740. Keep another 10px
        # inside that aperture, without scaling down text or native PNG.
        self.text(32, 76, data.get("heading", "POČASIE"), 26, bold=True, max_width=210)
        self.text(266, 76, data.get("date", ""), 24, max_width=182)
        self.weather(32, 124, data.get("weather", {}), max_width=416, show_detail=False)
        self.draw.line((32, 265, 448, 265), fill=BLACK, width=1)
        for index, entry in enumerate(data.get("metrics", [])[:2]):
            left = 32 + index * 224
            self.text(left, 282, entry.get("label", ""), 20, bold=True, max_width=192)
            self.text(left, 314, entry.get("value", "—"), 50, max_width=192)
            self.text(left, 371, entry.get("unit", ""), 22, max_width=192)
        self.draw.line((32, 414, 448, 414), fill=BLACK, width=1)
        for index, entry in enumerate(data.get("forecast", [])[:3]):
            top = 435 + index * 73
            self.icon(entry.get("icon", "cloud"), 32, top + 4, 52)
            self.text(104, top, entry.get("label", ""), 22, bold=True, max_width=220)
            self.text(104, top + 32, entry.get("detail", ""), 20, max_width=220)
            self.text(351, top + 8, entry.get("temperature", "—"), 40, max_width=97)
        notice = data.get("notice", {})
        color = RED if notice.get("warning") else BLACK
        self.draw.line((32, 654, 60, 654), fill=color, width=4)
        self.text(32, 669, notice.get("title", ""), 20, bold=True, color=color, max_width=416)
        footer = "UKÁŽKA · NIE ŽIVÉ ÚDAJE" if data.get("demo") else "Aktualizované " + data.get("updated", "—")
        self.text(32, 706, footer, 18, max_width=416)

    def quantize(self):
        # Anti-aliased fonts must be quantized to the physical three-color palette.
        # Reserve the full 10px perimeter, also for future layout changes.
        width, height = self.image.size
        for box in ((0, 0, width - 1, 9), (0, height - 10, width - 1, height - 1),
                    (0, 0, 9, height - 1), (width - 10, 0, width - 1, height - 1)):
            self.draw.rectangle(box, fill=WHITE)
        if self.portrait:
            left, top, right, bottom = PORTRAIT_SAFE_AREA
            for box in ((0, 0, width - 1, top - 1), (0, bottom, width - 1, height - 1),
                        (0, 0, left - 1, height - 1), (right, 0, width - 1, height - 1)):
                self.draw.rectangle(box, fill=WHITE)
        palette = Image.new("P", (1, 1))
        palette.putpalette([*WHITE, *BLACK, *RED] + list(WHITE) * 253)
        return self.image.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(__file__).with_name("demo.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("preview.png"))
    parser.add_argument("--font-dir", default="/usr/share/fonts/truetype/dejavu")
    parser.add_argument("--portrait", action="store_true", help="compose 480×800 for a vertical frame")
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    image = Components(args.font_dir, portrait=args.portrait).render(data)
    image.save(args.output, "PNG")
    print(f"Saved {args.output} ({image.width}×{image.height} RGB PNG; data source: {'DEMO' if data.get('demo') else 'JSON snapshot'})")


if __name__ == "__main__":
    main()
