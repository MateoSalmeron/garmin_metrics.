"""Race result storage and retrieval.

Each race is saved as a separate JSON file in data/races/.
File naming: YYYY-MM-DD_slugified-name.json
"""

import json
import re
from config import RACES_DIR


def save_race(race: dict) -> None:
    """Save a race result to data/races/. Overwrites if same date+name exists."""
    date = race.get("date", "unknown")
    slug = _slugify(race.get("name", "race"))
    (RACES_DIR / f"{date}_{slug}.json").write_text(
        json.dumps(race, indent=2, ensure_ascii=False)
    )


def load_all_races() -> list[dict]:
    """Return all saved race results sorted by date (most recent first)."""
    races = [json.loads(f.read_text()) for f in RACES_DIR.glob("*.json")]
    return sorted(races, key=lambda r: r.get("date", ""), reverse=True)


def load_recent_races(n: int = 10) -> list[dict]:
    return load_all_races()[:n]


def build_race_result(
    name: str,
    date: str,
    distance: str,
    total_time: str,
    position_overall: int | None = None,
    position_category: int | None = None,
    finishers_total: int | None = None,
    splits: dict | None = None,
    hr_avg: int | None = None,
    hr_max: int | None = None,
    notes: str = "",
    garmin_activity_id: str | None = None,
    source: str = "manual",
) -> dict:
    """Build a standardised race result dict."""
    return {
        "id":       f"{date}_{_slugify(name)}",
        "date":     date,
        "name":     name,
        "distance": distance,
        "type":     _infer_type(distance),
        "source":   source,
        "result": {
            "total_time":          total_time,
            "position_overall":    position_overall,
            "position_category":   position_category,
            "finishers_total":     finishers_total,
        },
        "splits":             splits or {},
        "hr_avg":             hr_avg,
        "hr_max":             hr_max,
        "notes":              notes,
        "garmin_activity_id": garmin_activity_id,
    }


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàä]", "a", text)
    text = re.sub(r"[éèë]", "e", text)
    text = re.sub(r"[íìï]", "i", text)
    text = re.sub(r"[óòö]", "o", text)
    text = re.sub(r"[úùü]", "u", text)
    text = re.sub(r"[ñ]", "n", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:50]


def _infer_type(distance: str) -> str:
    distance = distance.lower()
    if distance in ("sprint", "olimpico", "medio", "iron", "xterra"):
        return "triathlon"
    if distance in ("5k", "10k", "media_maraton", "maraton"):
        return "running"
    if distance in ("aquatlon",):
        return "aquatlon"
    return "other"
