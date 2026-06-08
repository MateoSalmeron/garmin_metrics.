"""Phase 1 metrics: weekly volume, HR zones, average paces per sport.

Phase 2 will add CTL/ATL/TSB (chronic/acute training load).
"""

import json
from datetime import date, datetime, timedelta

from config import ACTIVITIES_DIR, CURRENT_METRICS, PROFILE_FILE

SPORTS = ["running", "cycling", "swimming"]
ZONE_THRESHOLDS = [0.60, 0.70, 0.80, 0.90]


def _load_profile() -> dict:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text())
    return {}


def _resolve_max_hr(profile: dict) -> int:
    if profile.get("max_hr"):
        return int(profile["max_hr"])
    age = profile.get("age")
    if age:
        return 220 - int(age)
    return 185


def calculate_metrics() -> dict:
    profile  = _load_profile()
    max_hr   = _resolve_max_hr(profile)
    activities = _load_activities()
    today    = date.today()

    week_start      = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(weeks=1)

    this_week = _filter_period(activities, week_start, today)
    prev_week = _filter_period(activities, prev_week_start, week_start)
    last_4w   = _filter_period(activities, today - timedelta(weeks=4),  today)
    last_12w  = _filter_period(activities, today - timedelta(weeks=12), today)
    last_24w  = _filter_period(activities, today - timedelta(weeks=24), today)

    metrics = {
        "generated_at":       str(today),
        "max_hr_used":        max_hr,
        "weekly_volume":      _volume_by_sport(this_week),
        "prev_weekly_volume": _volume_by_sport(prev_week),
        "last_4w_volume":     _volume_by_sport(last_4w),
        "last_12w_volume":    _volume_by_sport(last_12w),
        "last_6m_volume":     _volume_by_sport(last_24w),
        "avg_paces_last_4w":  _avg_paces(last_4w),
        "avg_paces_last_6m":  _avg_paces(last_24w),
        "hr_zones_this_week": _hr_zones(this_week, max_hr),
        "hr_zones_last_4w":   _hr_zones(last_4w, max_hr),
        "hr_zones_last_6m":   _hr_zones(last_24w, max_hr),
        "activities_count": {
            "this_week": len(this_week),
            "prev_week": len(prev_week),
            "last_4w":   len(last_4w),
            "last_12w":  len(last_12w),
            "last_6m":   len(last_24w),
        },
        "last_activity": activities[0]["date"] if activities else None,
    }

    CURRENT_METRICS.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    return metrics


def _load_activities() -> list[dict]:
    activities = [json.loads(f.read_text()) for f in ACTIVITIES_DIR.glob("*.json")]
    return sorted(activities, key=lambda a: a.get("date", ""), reverse=True)


def _filter_period(activities: list[dict], start: date, end: date) -> list[dict]:
    return [
        a for a in activities
        if start <= datetime.strptime(a["date"], "%Y-%m-%d").date() < end
    ]


def _volume_by_sport(activities: list[dict]) -> dict:
    volume = {s: {"km": 0.0, "min": 0.0} for s in SPORTS}
    for a in activities:
        sport = a.get("type", "other")
        if sport in volume:
            volume[sport]["km"]  += a.get("distance_km", 0) or 0
            volume[sport]["min"] += a.get("duration_min", 0) or 0
    for s in volume:
        volume[s]["km"]  = round(volume[s]["km"], 1)
        volume[s]["min"] = round(volume[s]["min"], 0)
    return volume


def _avg_paces(activities: list[dict]) -> dict:
    """Average pace/speed per sport over the provided activity list."""
    totals = {s: {"km": 0.0, "min": 0.0} for s in SPORTS}
    for a in activities:
        sport = a.get("type", "other")
        if sport in totals and (a.get("distance_km") or 0) > 0:
            totals[sport]["km"]  += a["distance_km"]
            totals[sport]["min"] += a.get("duration_min", 0) or 0

    paces = {}
    r = totals["running"]
    if r["km"] > 0:
        paces["running_pace_min_per_km"] = round(r["min"] / r["km"], 2)

    c = totals["cycling"]
    if c["km"] > 0 and c["min"] > 0:
        paces["cycling_speed_km_h"] = round(c["km"] / (c["min"] / 60), 1)

    s = totals["swimming"]
    if s["km"] > 0:
        paces["swimming_pace_min_per_100m"] = round(s["min"] / (s["km"] * 10), 2)

    return paces


def _hr_zones(activities: list[dict], max_hr: int) -> dict:
    zones = {f"z{i+1}": 0.0 for i in range(5)}
    for a in activities:
        hr = a.get("hr_avg")
        if not hr:
            continue
        pct = hr / max_hr
        dur = a.get("duration_min", 0) or 0
        if pct < ZONE_THRESHOLDS[0]:
            zones["z1"] += dur
        elif pct < ZONE_THRESHOLDS[1]:
            zones["z2"] += dur
        elif pct < ZONE_THRESHOLDS[2]:
            zones["z3"] += dur
        elif pct < ZONE_THRESHOLDS[3]:
            zones["z4"] += dur
        else:
            zones["z5"] += dur
    return {k: round(v, 0) for k, v in zones.items()}


if __name__ == "__main__":
    metrics = calculate_metrics()
    print(json.dumps(metrics, indent=2))
