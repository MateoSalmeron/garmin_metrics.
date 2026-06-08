import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from garminconnect import Garmin

from config import ACTIVITIES_DIR

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

    return saved


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
        "source":       "garmin",
    }


if __name__ == "__main__":
    saved = sync_activities()
    print(f"Synced {len(saved)} new activities")
    for a in saved:
        print(f"  {a['date']}  {a['type']}  {a['distance_km']} km  {a['duration_min']} min")
