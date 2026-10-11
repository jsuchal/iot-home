"""Daily wall-clock schedules evaluated on UTC minutes (DST-safe)."""
import math
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def minute(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("schedule times must use HH:MM")
    hour, mins = map(int, value.split(":"))
    return hour * 60 + mins


def validate(options):
    if options.get("update_mode", "interval") not in ("interval", "daily", "window"):
        raise ValueError("invalid update_mode")
    ZoneInfo(options.get("timezone", "Europe/Prague"))
    times = options.get("update_times", ["07:00", "12:00", "18:00"])
    if not isinstance(times, list) or not times or len(times) > 48:
        raise ValueError("update_times needs 1..48 HH:MM entries")
    for value in times:
        minute(value)
    start, end = minute(options.get("window_start", "07:00")), minute(options.get("window_end", "22:00"))
    if start == end:
        raise ValueError("window_start and window_end must differ")
    interval = options.get("window_interval_minutes", 30)
    if type(interval) is not int or not 1 <= interval <= 1440:
        raise ValueError("window_interval_minutes must be 1..1440")


def sleep_seconds(options, now=None):
    mode = options.get("update_mode", "interval")
    if mode == "interval":
        return options["sleep_seconds"]
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    zone = ZoneInfo(options.get("timezone", "Europe/Prague"))
    times = {minute(t) for t in options.get("update_times", ["07:00", "12:00", "18:00"])}
    start, end = minute(options.get("window_start", "07:00")), minute(options.get("window_end", "22:00"))
    span = (end - start) % 1440
    candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # UTC iteration skips nonexistent spring times and visits both autumn folds.
    for _ in range(3 * 1440):
        local = candidate.astimezone(zone)
        value = local.hour * 60 + local.minute
        offset = (value - start) % 1440
        due = value in times if mode == "daily" else offset < span and offset % options.get("window_interval_minutes", 30) == 0
        if due:
            return max(60, min(86400, math.ceil((candidate - now).total_seconds())))
        candidate += timedelta(minutes=1)
    raise ValueError("no schedule occurrence found")
