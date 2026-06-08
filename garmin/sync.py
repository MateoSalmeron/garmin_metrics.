import json
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from garminconnect import Garmin

from config import ACTIVITIES_DIR
from races.recorder import build_race_result, save_race

load_dotenv()

_SPORT_MAP = {
    "running":             "running",
    "trail_running":       "running",
    "treadmill_running":   "running",
    "cycling":             "cycling",
    "road_biking":         "cycling",
    "mountain_biking":     "cycling",
    "indoor_cycling":      "cycling",
    "swimming":            "swimming",
    "open_water_swimming": "swimming",
    "lap_swimming":        "swimming",
}

MONTHS_BACK = 3


def sync_activities() -> list[dict]:
    """Download activities from the last 3 months. Returns newly saved ones."""
    username = os.getenv("GARMIN_USERNAME")
    password = os.getenv("GARMIN_PASSWORD")
    if not username or not password:
        raise ValueError("GARMIN_USERNAME and GARMIN_PASSWORD must be set in .env")

    client = Garmin(username, password)
    client.login()

    end   = datetime.now()
    start = end - timedelta(days=MONTHS_BACK * 30)

    raw_activities = client.get_activities_by_date(
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )

    saved = []
    for raw in raw_activities:
        activity = _normalize(raw)
        path = ACTIVITIES_DIR / f"{activity['id']}.json"
        if not path.exists():
            path.write_text(json.dumps(activity, indent=2, ensure_ascii=False))
            saved.append(activity)

        if _is_race(raw):
            _save_race_from_garmin(raw, client)

    return saved


def _is_race(raw: dict) -> bool:
    event_type = (raw.get("eventType") or {}).get("typeKey", "")
    return event_type.lower() == "race"


def _save_race_from_garmin(raw: dict, client: Garmin) -> None:
    """Extract race result from a Garmin activity and save it."""
    activity_id = str(raw.get("activityId", ""))
    date        = (raw.get("startTimeLocal") or "")[:10]
    name        = raw.get("activityName") or "Race"
    type_key    = (raw.get("activityType") or {}).get("typeKey", "")
    distance_km = round((raw.get("distance") or 0) / 1000, 2)
    duration_s  = raw.get("duration") or 0
    hr_avg      = raw.get("averageHR")
    hr_max      = raw.get("maxHR")

    total_time = _seconds_to_time(int(duration_s))
    distance   = _infer_distance_label(type_key, distance_km)
    splits     = _extract_splits(raw, client, activity_id)

    race = build_race_result(
        name=name,
        date=date,
        distance=distance,
        total_time=total_time,
        hr_avg=hr_avg,
        hr_max=hr_max,
        splits=splits,
        garmin_activity_id=activity_id,
        source="garmin",
    )
    save_race(race)


def _extract_splits(raw: dict, client: Garmin, activity_id: str) -> dict:
    """Try to get lap/split data. Returns empty dict if not available."""
    try:
        splits_data = client.get_activity_splits(activity_id)
        laps = splits_data.get("lapDTOs") or []
        if not laps:
            return {}

        result = {}
        for i, lap in enumerate(laps, 1):
            lap_distance_km = round((lap.get("distance") or 0) / 1000, 2)
            lap_duration_s  = lap.get("duration") or 0
            lap_hr          = lap.get("averageHR")
            result[f"lap_{i}"] = {
                "distance_km":  lap_distance_km,
                "time":         _seconds_to_time(int(lap_duration_s)),
                "hr_avg":       lap_hr,
            }
            if lap_distance_km > 0 and lap_duration_s > 0:
                pace = (lap_duration_s / 60) / lap_distance_km
                result[f"lap_{i}"]["pace_min_per_km"] = round(pace, 2)
        return result
    except Exception:
        return {}


def _normalize(raw: dict) -> dict:
    type_key = (raw.get("activityType") or {}).get("typeKey", "other")
    return {
        "id":           str(raw.get("activityId", "")),
        "date":         (raw.get("startTimeLocal") or "")[:10],
        "type":         _SPORT_MAP.get(type_key, type_key),
        "distance_km":  round((raw.get("distance") or 0) / 1000, 2),
        "duration_min": round((raw.get("duration") or 0) / 60, 1),
        "hr_avg":       raw.get("averageHR"),
        "hr_max":       raw.get("maxHR"),
        "is_race":      _is_race(raw),
        "source":       "garmin",
    }


def _seconds_to_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _infer_distance_label(type_key: str, distance_km: float) -> str:
    if "swim" in type_key:
        return "swimming_race"
    if "running" in type_key or "run" in type_key:
        if distance_km < 6:    return "5k"
        if distance_km < 11:   return "10k"
        if distance_km < 22:   return "media_maraton"
        return "maraton"
    if "cycling" in type_key or "bik" in type_key:
        return "cycling_race"
    if "triathlon" in type_key:
        if distance_km < 15:   return "sprint"
        if distance_km < 55:   return "olimpico"
        if distance_km < 120:  return "medio"
        return "iron"
    return "otro"


if __name__ == "__main__":
    saved = sync_activities()
    print(f"Synced {len(saved)} new activities")
    for a in saved:
        race_tag = " [RACE]" if a.get("is_race") else ""
        print(f"  {a['date']}  {a['type']}  {a['distance_km']} km{race_tag}")
