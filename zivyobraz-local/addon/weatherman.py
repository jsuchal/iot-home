#!/usr/bin/env python3
"""Weatherman-style drawing from genuine hourly and daily weather snapshots.

Independent drawing code, CC-BY-NC-SA-4.0. See assets/NOTICE.md for fonts.
"""
import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from weather import Weather, number

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
SAFE_AREA = (30, 70, 450, 730)
# Explicit vertical rhythm: items inside one forecast column stay close
# together, and the gaps between the weather, hourly and daily blocks are
# deliberately larger. Do not replace these with one uniform grid gap.
LAYOUT_TOPS = (92, 174, 330, 365, 430, 473, 536, 578, 616, 670, 706)
SIZE_HEADING = 50
SIZE_VALUE = 32
SIZE_PAIR = 26
SIZE_DAY = 26
SIZE_LABEL = 22
SIZE_RAIN = 18
SIZE_ICON_HOURLY = 56
SIZE_ICON_DAILY = 50
SIZE_ICON_BIG = 100
SIZE_ICON_RAIN = 24
COLUMNS = (100, 240, 380)
COLUMN_WIDTH = 130
HOT_ABOVE_C = 28
COLD_BELOW_C = 0
# Below this speed the wind is not shown at all (like zero rain):
# Beaufort 0-1 (calm to light air) carries no information on this display.
SMALL_WIND_KMH = 6
MDI = {"cloudy": 0xF0590, "partlycloudy": 0xF0595, "sunny": 0xF0599,
       "clear-night": 0xF0594, "rainy": 0xF0597, "pouring": 0xF0596,
       "snowy": 0xF0598, "snowy-rainy": 0xF067F, "fog": 0xF0591,
       "windy": 0xF059D, "windy-variant": 0xF059E, "hail": 0xF0592,
       "lightning": 0xF0593, "lightning-rainy": 0xF067E, "water": 0xF058C}
ICON_CONDITIONS = {"sun": "sunny", "cloud": "cloudy", "rain": "rainy", "moon": "clear-night",
                   "snow": "snowy", "wind": "windy", "fog": "fog", "storm": "lightning"}


def rounded_temperature(value):
    match = re.fullmatch(r"([−+-]?\d+(?:[.,]\d+)?)(.*)", str(value))
    if not match:
        return str(value)
    number = float(match[1].replace("−", "-").replace(",", "."))
    return f"{number:.0f}" + match[2]


def temperature_color(value, cold=COLD_BELOW_C, hot=HOT_ABOVE_C):
    if isinstance(value, bool):
        return WHITE
    if isinstance(value, (int, float)):
        temperature = value
    else:
        match = re.fullmatch(r"([−+-]?\d+(?:[.,]\d+)?)(?:°C|°)?", str(value))
        if not match:
            return WHITE
        temperature = float(match[1].replace("−", "-").replace(",", "."))
    if math.isfinite(temperature) and (temperature > hot or temperature < cold):
        return RED
    return WHITE


def temperature_highlight(entry, key="temperature"):
    warning_key = key + "_warning"
    if warning_key in entry:
        return RED if entry[warning_key] else WHITE
    return temperature_color(entry.get(key + "_value", entry.get(key, "—")))


def visible_bounds(font, value):
    """Actual solid-pixel bounds, not font metrics that can include blank rows."""
    left, top, right, bottom = font.getbbox(value, anchor="lt")
    mask = Image.new("L", (max(1, right - left), max(1, bottom - top)))
    ImageDraw.Draw(mask).text((-left, -top), value, font=font, fill=255, anchor="lt")
    bounds = mask.point(lambda value: 255 if value >= 128 else 0).getbbox()
    if bounds is None:
        return left, top, right, bottom
    return left + bounds[0], top + bounds[1], left + bounds[2], top + bounds[3]


def celsius(value, unit):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if unit == "°C":
        return value
    if unit == "°F":
        return (value - 32) * 5 / 9
    return None


def above(value, unit, factors, threshold):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and unit in factors and value * factors[unit] > threshold)


def rain_amount(value, unit):
    """Human amount for any measurable rain; empty string when there is none."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return ""
    if round(value, 1) == 0:
        return "<0,1 " + unit
    return number(value, " " + unit, 1)


def small_wind(value, unit):
    """True when a real measurement exists but is too small to show."""
    factors = {"km/h": 1, "m/s": 3.6, "mph": 1.609344, "kn": 1.852}
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and unit in factors
            and 0 <= value * factors[unit] < SMALL_WIND_KMH)


def prepare_data(snapshot, daily_forecast, now=None, options=None, data=None):
    """Map genuine HA snapshots; optional already-composed data retains outage status."""
    options = options or {}
    now = now or datetime.fromisoformat(snapshot["fetched"])
    zone = ZoneInfo(options.get("timezone", "Europe/Prague"))
    if data is None:
        weather = Weather(options | {"weather_entity": snapshot["entity"], "forecast_type": "hourly",
                                    "forecast_step_hours": options.get("forecast_step_hours", "3")})
        weather.snapshot = snapshot
        data = weather.compose(now)
    attributes = snapshot["state"]["attributes"]
    data["weather"]["condition"] = snapshot["state"]["state"]
    data["weather"]["temperature_value"] = attributes.get("temperature")
    cold, hot = options.get("cold_below_c", 0), options.get("hot_above_c", 28)
    def temperature_warning(value):
        return temperature_color(celsius(value, attributes.get("temperature_unit")), cold, hot) == RED
    data["weather"]["temperature_warning"] = temperature_warning(attributes.get("temperature"))
    future = {}
    for entry in snapshot["forecast"]:
        dt = datetime.fromisoformat(entry["datetime"])
        if dt > now:
            future.setdefault(dt.astimezone(zone).strftime("%H:%M"), entry)
    for entry in data["forecast"]:
        raw = future[entry["label"]]
        entry["condition"] = raw.get("condition", "unknown")
        entry["temperature_value"] = raw.get("temperature")
        entry["temperature_warning"] = temperature_warning(raw.get("temperature"))
        entry["wind"] = number(raw.get("wind_speed"), " " + attributes.get("wind_speed_unit", ""))
        entry["wind_warning"] = above(raw.get("wind_speed"), attributes.get("wind_speed_unit"),
                                      {"km/h": 1, "m/s": 3.6, "mph": 1.609344, "kn": 1.852},
                                      options.get("wind_above_kmh", 40))
        entry["wind_small"] = small_wind(raw.get("wind_speed"), attributes.get("wind_speed_unit", ""))
        # Variant B: a slot shows the hourly precipitation instead of wind when
        # there is any, so a rainy hour is visible without adding a fourth line.
        precipitation = raw.get("precipitation")
        entry["rain"] = rain_amount(precipitation, attributes.get("precipitation_unit", ""))
        entry["rain_warning"] = bool(entry["rain"]) and above(
            precipitation, attributes.get("precipitation_unit"), {"mm": 1, "in": 25.4},
            options.get("rain_above_mm_hour", 4))
    data["daily"] = []
    today = now.astimezone(zone).date()
    weekdays = ("Pondelok", "Utorok", "Streda", "Štvrtok", "Piatok", "Sobota", "Nedeľa")
    for entry in daily_forecast:
        day = datetime.fromisoformat(entry["datetime"]).astimezone(zone)
        if day.date() <= today:
            continue
        precipitation = entry.get("precipitation")
        rain = rain_amount(precipitation, attributes.get("precipitation_unit", ""))
        data["daily"].append({"label": weekdays[day.weekday()],
                              "condition": entry.get("condition", "unknown"),
                              "low": number(entry.get("templow"), "°"),
                              "high": number(entry.get("temperature"), "°"),
                              "low_value": entry.get("templow"), "high_value": entry.get("temperature"),
                              "low_warning": temperature_warning(entry.get("templow")),
                              "high_warning": temperature_warning(entry.get("temperature")),
                              "wind": number(entry.get("wind_speed"),
                                            " " + attributes.get("wind_speed_unit", "")),
                              "wind_warning": above(entry.get("wind_speed"), attributes.get("wind_speed_unit"),
                                                    {"km/h": 1, "m/s": 3.6, "mph": 1.609344, "kn": 1.852},
                                                    options.get("wind_above_kmh", 40)),
                              "wind_small": small_wind(entry.get("wind_speed"),
                                                       attributes.get("wind_speed_unit", "")),
                              "rain_warning": above(precipitation, attributes.get("precipitation_unit"),
                                                    {"mm": 1, "in": 25.4}, options.get("rain_above_mm_day", 10)),
                              "rain": rain})
        if len(data["daily"]) == 3:
            break
    if not data["daily"] and not data["notice"].get("warning"):
        data["notice"] = {"warning": True, "title": "DENNÁ PREDPOVEĎ CHÝBA"}
    return data


class Weatherman:
    def __init__(self, assets=None, display_mode="dark"):
        if display_mode not in ("dark", "light"):
            raise ValueError("display_mode must be dark or light")
        self.display_mode = display_mode
        self.assets = Path(assets) if assets else Path(__file__).with_name("assets")
        self.image = Image.new("RGB", (480, 800), BLACK)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {}

    def font(self, size, weight=400, icons=False):
        key = size, weight, icons
        if key not in self.fonts:
            path = self.assets / ("materialdesignicons-webfont.ttf" if icons else "Nunito.ttf")
            font = ImageFont.truetype(str(path), size)
            if not icons:
                font.set_variation_by_axes([weight])
            self.fonts[key] = font
        return self.fonts[key]

    def text(self, cx, top, value, size, weight=400, width=420, color=WHITE):
        value = str(value)
        font = self.font(size, weight)
        original = value
        while value and self.draw.textlength(value, font=font) > width:
            original = original[:-1]
            value = original + "…" if original else ""
        left = cx - self.draw.textlength(value, font=font) / 2
        self.draw.text((left, top), value, font=font, fill=color, anchor="lt")

    def _icon_text_parts(self, icon, value):
        icon_font = self.font(24, icons=True)
        glyph = chr(MDI[icon])
        icon_bounds = visible_bounds(icon_font, glyph)
        text_font = self.font(SIZE_LABEL, 800)
        text_bounds = visible_bounds(text_font, value)
        return glyph, icon_font, icon_bounds, text_font, text_bounds

    def _icon_bounds(self, entry, size):
        condition = entry.get("condition", ICON_CONDITIONS.get(entry.get("icon"), ""))
        code = MDI.get(condition)
        if code is None:
            return visible_bounds(self.font(size), "?")
        return visible_bounds(self.font(size, icons=True), chr(code))

    def _draw_icon(self, cx, top, entry, size, color):
        condition = entry.get("condition", ICON_CONDITIONS.get(entry.get("icon"), ""))
        code = MDI.get(condition)
        font = self.font(size) if code is None else self.font(size, icons=True)
        glyph = "?" if code is None else chr(code)
        self.draw.text((cx - self.draw.textlength(glyph, font=font) / 2, top), glyph, font=font, fill=color, anchor="lt")

    def _text_cell(self, cx, value, size=SIZE_LABEL, weight=400, color=WHITE, width=COLUMN_WIDTH):
        return ("text", cx, str(value), size, weight, color, width)

    def _icon_cell(self, cx, entry, size=SIZE_ICON_HOURLY, color=WHITE):
        return ("icon", cx, entry, size, color)

    def _pair_cell(self, cx, entry):
        return ("pair", cx, entry)

    def _icon_text_cell(self, cx, icon, value, warning):
        return ("icontext", cx, icon, str(value), RED if warning else WHITE)

    def _detail_cell(self, cx, entry):
        """Hourly and daily detail line: droplet + amount when raining,
        wind icon + speed when windy, otherwise empty. Measurements are
        always present in real snapshots, so no placeholder is drawn."""
        if entry.get("rain"):
            return self._icon_text_cell(cx, "water", entry["rain"], entry.get("rain_warning"))
        if entry.get("wind_small"):
            return self._text_cell(cx, "")
        wind = entry.get("wind", "")
        if not wind or wind == "—":
            return self._text_cell(cx, "")
        return self._icon_text_cell(cx, "windy", wind, entry.get("wind_warning"))

    def _clipped(self, value, size, weight, width):
        value = str(value)
        original = value
        while value and self.draw.textlength(value, font=self.font(size, weight)) > width:
            original = original[:-1]
            value = original + "…" if original else ""
        return value

    def _pair_size(self, value):
        size = SIZE_PAIR
        while size > 18 and self.draw.textlength(value, font=self.font(size, 800)) > COLUMN_WIDTH:
            size -= 1
        return size

    def measure(self, cell):
        """Visible ink height of one cell, independent of its position."""
        kind = cell[0]
        if kind == "text":
            _, _, value, size, weight, _, width = cell
            bounds = visible_bounds(self.font(size, weight), self._clipped(value, size, weight, width))
        elif kind == "icon":
            bounds = self._icon_bounds(cell[2], cell[3])
        elif kind == "pair":
            value = str(cell[2].get("low", "—")) + " / " + str(cell[2].get("high", "—"))
            bounds = visible_bounds(self.font(self._pair_size(value), 800), value)
        else:
            _, _, icon, value, _ = cell
            _, _, icon_bounds, _, text_bounds = self._icon_text_parts(icon, value)
            return max(icon_bounds[3] - icon_bounds[1], text_bounds[3] - text_bounds[1])
        return bounds[3] - bounds[1]

    def draw_cell(self, cell, ink_top):
        """Draw one cell with the top of its visible ink at ink_top."""
        kind = cell[0]
        if kind == "text":
            _, cx, value, size, weight, color, width = cell
            value = self._clipped(value, size, weight, width)
            bounds = visible_bounds(self.font(size, weight), value)
            self.text(cx, ink_top - bounds[1], value, size=size, weight=weight, width=width, color=color)
        elif kind == "icon":
            _, cx, entry, size, color = cell
            bounds = self._icon_bounds(entry, size)
            self._draw_icon(cx, ink_top - bounds[1], entry, size, color)
        elif kind == "pair":
            _, cx, entry = cell
            value = str(entry.get("low", "—")) + " / " + str(entry.get("high", "—"))
            bounds = visible_bounds(self.font(self._pair_size(value), 800), value)
            self.temperature_pair(cx, ink_top - bounds[1], entry)
        else:
            _, cx, icon, value, color = cell
            glyph, icon_font, icon_bounds, _, text_bounds = self._icon_text_parts(icon, value)
            icon_height = icon_bounds[3] - icon_bounds[1]
            text_height = text_bounds[3] - text_bounds[1]
            height = max(icon_height, text_height)
            icon_width = icon_bounds[2] - icon_bounds[0]
            text_width = text_bounds[2] - text_bounds[0]
            gap = 8
            left = cx - (icon_width + gap + text_width) / 2
            self.draw.text((left - icon_bounds[0], ink_top + (height - icon_height) / 2 - icon_bounds[1]),
                           glyph, font=icon_font, fill=color, anchor="lt")
            text_cx = left + icon_width + gap + text_width / 2
            adv = self.draw.textlength(value, font=self.font(SIZE_LABEL, 800))
            self.text(text_cx, ink_top + (height - text_height) / 2 - text_bounds[1],
                      value, size=SIZE_LABEL, weight=800, width=adv + 1, color=color)

    def temperature_pair(self, cx, top, entry):
        low, high = entry.get("low", "—"), entry.get("high", "—")
        value = low + " / " + high
        size = self._pair_size(value)
        font = self.font(size, 800)
        left = cx - self.draw.textlength(value, font=font) / 2
        for text, color in ((low, temperature_highlight(entry, "low")), (" / ", WHITE),
                            (high, temperature_highlight(entry, "high"))):
            width = self.draw.textlength(text, font=font)
            self.text(left + width / 2, top, text, size, weight=800, width=width + 1, color=color)
            left += width

    def _three(self, entries):
        entries = list(entries or [])[:3]
        while len(entries) < 3:
            entries.append({})
        return entries

    def layout(self, data):
        """Compose rows of cells without drawing, so spacing can be inspected."""
        weather = data.get("weather", {})
        temperature = rounded_temperature(weather.get("temperature", "—"))
        big_size = SIZE_ICON_BIG + 8
        while big_size > 40 and self.draw.textlength(temperature, font=self.font(big_size, 800)) > 280:
            big_size -= 1
        heading = "UKÁŽKA" if data.get("demo") else data.get("heading", "POČASIE")
        notice = data.get("notice", {})
        hourly, daily = self._three(data.get("forecast")), self._three(data.get("daily"))
        rows = [
            [self._text_cell(240, heading, SIZE_HEADING, 800, WHITE, 440)],
            [self._icon_cell(108, weather, SIZE_ICON_BIG),
             self._text_cell(307, temperature, big_size, 800, temperature_highlight(weather), 280)],
            [self._text_cell(cx, entry.get("label", "")) for cx, entry in zip(COLUMNS, hourly)],
            [self._icon_cell(cx, entry, SIZE_ICON_HOURLY, RED if entry.get("rain_warning") else WHITE)
             for cx, entry in zip(COLUMNS, hourly)],
            [self._text_cell(cx, rounded_temperature(entry.get("temperature", "—")), SIZE_VALUE, 800,
                             temperature_highlight(entry))
             for cx, entry in zip(COLUMNS, hourly)],
        ]
        detail = [self._detail_cell(cx, entry) for cx, entry in zip(COLUMNS, hourly)]
        rows.append(detail)
        rows.append([self._text_cell(240, notice.get("title", "ZASTARANÉ ÚDAJE") if notice.get("warning")
                                     else "NAJBLIŽŠIE DNI", SIZE_LABEL, 800,
                                     RED if notice.get("warning") else WHITE, 440)])
        rows.append([self._text_cell(cx, entry.get("label", ""), SIZE_DAY) for cx, entry in zip(COLUMNS, daily)])
        rows.append([self._icon_cell(cx, entry, SIZE_ICON_DAILY, RED if entry.get("rain_warning") else WHITE)
                     for cx, entry in zip(COLUMNS, daily)])
        rows.append([self._pair_cell(cx, entry) for cx, entry in zip(COLUMNS, daily)])
        # Same rule as the hourly row: droplet + amount when raining,
        # wind icon + speed when windy, empty when the wind is negligible.
        rows.append([self._detail_cell(cx, entry) for cx, entry in zip(COLUMNS, daily)])
        return rows

    def place(self, data):
        """Rows at the explicit rhythm; each row is centred on its tallest cell."""
        rows = self.layout(data)
        heights = [max(self.measure(cell) for cell in row) for row in rows]
        return rows, heights, list(LAYOUT_TOPS[:len(rows)])

    def render(self, data):
        rows, heights, tops = self.place(data)
        for row, height, top in zip(rows, heights, tops):
            for cell in row:
                self.draw_cell(cell, top + (height - self.measure(cell)) / 2)
        palette = Image.new("P", (1, 1))
        palette.putpalette([*WHITE, *BLACK, *RED] + list(WHITE) * 253)
        result = self.image.quantize(palette=palette, dither=Image.Dither.NONE)
        if self.display_mode == "light":
            colors = result.getpalette()
            for index in range(0, len(colors), 3):
                color = tuple(colors[index:index + 3])
                if color == BLACK:
                    colors[index:index + 3] = WHITE
                elif color == WHITE:
                    colors[index:index + 3] = BLACK
            result.putpalette(colors)  # Red stays red; no RGB inversion to cyan.
        else:
            # Red pigment has poor contrast on this panel's dark background.
            colors = result.getpalette()
            for index in range(0, len(colors), 3):
                if tuple(colors[index:index + 3]) == RED:
                    colors[index:index + 3] = WHITE
            result.putpalette(colors)
        return result.convert("RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("dark", "light"), default="dark")
    args = parser.parse_args()
    Weatherman(display_mode=args.mode).render(json.loads(args.data.read_text())).save(args.output)


if __name__ == "__main__":
    main()
