"""Read-only weather snapshot via the add-on's Supervisor Core proxy."""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

CONDITIONS = {
    "sunny": ("Slnečno", "sun"), "clear-night": ("Jasná noc", "moon"),
    "partlycloudy": ("Polojasno", "cloud"), "cloudy": ("Oblačno", "cloud"),
    "rainy": ("Dážď", "rain"), "pouring": ("Silný dážď", "rain"),
    "snowy": ("Sneženie", "snow"), "snowy-rainy": ("Dážď so snehom", "snow"),
    "fog": ("Hmla", "fog"), "windy": ("Veterno", "wind"),
    "windy-variant": ("Veterno", "wind"), "lightning": ("Búrka", "storm"),
    "lightning-rainy": ("Búrka s dažďom", "storm"), "hail": ("Krúpy", "snow"),
    "exceptional": ("Neobvyklé počasie", "unknown"),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("HA API redirects are not allowed")


def api(path, payload=None):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise ValueError("Home Assistant API permission/token missing")
    request = Request("http://supervisor/core/api/" + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with build_opener(NoRedirect()).open(request, timeout=10) as response:
        data = response.read(1_000_001)
    if len(data) > 1_000_000:
        raise ValueError("HA response too large")
    return json.loads(data)


def number(value, suffix="", decimals=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",") + suffix


def validate_snapshot(snapshot):
    if not isinstance(snapshot["state"]["attributes"], dict) or not isinstance(snapshot["state"]["state"], str):
        raise ValueError("invalid weather state")
    if datetime.fromisoformat(snapshot["fetched"]).tzinfo is None:
        raise ValueError("snapshot timestamp needs timezone")
    if not isinstance(snapshot["forecast"], list) or not snapshot["forecast"]:
        raise ValueError("forecast unavailable")
    for entry in snapshot["forecast"]:
        if datetime.fromisoformat(entry["datetime"]).tzinfo is None:
            raise ValueError("forecast timestamp needs timezone")
    if snapshot.get("layout") == "weatherman":
        if not isinstance(snapshot.get("daily_forecast"), list) or not snapshot["daily_forecast"]:
            raise ValueError("daily forecast unavailable")
        for entry in snapshot["daily_forecast"]:
            if datetime.fromisoformat(entry["datetime"]).tzinfo is None:
                raise ValueError("daily forecast timestamp needs timezone")


class Weather:
    def __init__(self, options, cache_path=None):
        self.options = options
        self.cache_path = Path(cache_path) if cache_path else None
        self.snapshot = None
        self.checked = None
        self.failed = False
        if self.cache_path and self.cache_path.exists():
            try:
                snapshot = json.loads(self.cache_path.read_text())
                validate_snapshot(snapshot)
                if (snapshot["entity"] == options["weather_entity"] and snapshot["kind"] == options["forecast_type"]
                        and snapshot.get("layout", "classic") == options.get("layout", "classic")):
                    self.snapshot = snapshot
            except (ValueError, KeyError, OSError, TypeError):
                pass

    def read(self, now=None):
        now = now or datetime.now(timezone.utc)
        if self.checked is None or time.monotonic() - self.checked >= 60:
            self.checked = time.monotonic()
            try:
                entity = self.options["weather_entity"]
                state = api("states/" + entity)
                if state["state"] in ("unknown", "unavailable"):
                    raise ValueError("weather unavailable")
                response = api("services/weather/get_forecasts?return_response",
                               {"entity_id": entity, "type": self.options["forecast_type"]})
                forecast = response["service_response"][entity]["forecast"]
                if not isinstance(forecast, list) or not forecast:
                    raise ValueError("forecast unavailable")
                snapshot = {"entity": entity, "kind": self.options["forecast_type"],
                            "state": state, "forecast": forecast, "fetched": now.isoformat(),
                            "layout": self.options.get("layout", "classic")}
                if snapshot["layout"] == "weatherman":
                    daily = api("services/weather/get_forecasts?return_response", {"entity_id": entity, "type": "daily"})
                    snapshot["daily_forecast"] = daily["service_response"][entity]["forecast"]
                validate_snapshot(snapshot)
                if self.cache_path:
                    temporary = self.cache_path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(snapshot))
                    temporary.replace(self.cache_path)
                self.snapshot = snapshot
                self.failed = False
            except Exception:
                # Never log exception text: it may contain authorization/URLs.
                self.failed = True
        if self.snapshot is None:
            raise ValueError("no successful weather snapshot yet")
        return self.compose(now)

    def compose(self, now):
        snapshot = self.snapshot
        zone = ZoneInfo(self.options.get("timezone", "Europe/Prague"))
        fetched = datetime.fromisoformat(snapshot["fetched"])
        local = fetched.astimezone(zone)
        stale = self.failed or (now - fetched).total_seconds() > self.options.get("weather_stale_minutes", 120) * 60
        state = snapshot["state"]
        attr = state["attributes"]
        description, icon = CONDITIONS.get(state["state"], ("Stav nedostupný", "unknown"))
        unit = attr.get("temperature_unit", "")
        entries = []
        for entry in snapshot["forecast"]:
            dt = datetime.fromisoformat(entry["datetime"])
            if dt.tzinfo is None:
                raise ValueError("forecast datetime must include timezone")
            if dt <= now:
                continue
            dt = dt.astimezone(zone)
            if snapshot["kind"] == "hourly":
                step = int(self.options.get("forecast_step_hours", "3"))
                if step > 1 and (dt.hour % step != 0 or dt.minute != 0):
                    continue
            label = dt.strftime("%H:%M") if snapshot["kind"] == "hourly" else dt.strftime("%d.%m.")
            _, entry_icon = CONDITIONS.get(entry.get("condition"), ("", "unknown"))
            temperature = number(entry.get("temperature"), "°" if unit in ("°C", "°F") else "")
            detail = "Zrážky " + number(entry.get("precipitation"), " " + attr.get("precipitation_unit", ""), 1)
            if snapshot["kind"] == "daily":
                detail = "Min " + number(entry.get("templow"), unit) + " · " + detail
            entries.append({"label": label, "icon": entry_icon, "temperature": temperature, "detail": detail})
            if len(entries) == 3:
                break
        return {"heading": "POČASIE", "date": local.strftime("%d.%m.%Y"), "demo": False,
                "weather": {"temperature": number(attr.get("temperature"), unit, 1),
                            "description": description, "icon": icon,
                            "detail": ("Predpoveď každé 3 hodiny" if self.options.get("forecast_step_hours", "3") == "3" else "Najbližšie hodiny") if snapshot["kind"] == "hourly" else "Denná predpoveď"},
                "metrics": [{"label": "VLHKOSŤ", "value": number(attr.get("humidity")), "unit": "%"},
                            {"label": "VIETOR", "value": number(attr.get("wind_speed"), decimals=1),
                             "unit": attr.get("wind_speed_unit", "")}],
                "forecast": entries,
                "notice": {"warning": stale or not entries, "title": "ZASTARANÉ ÚDAJE" if stale else "HOME ASSISTANT",
                           "text": "Zdroj nedostupný" if self.failed else ("Predpoveď chýba" if not entries else "Forecast Home")},
                "updated": local.strftime("%d.%m. %H:%M")}
