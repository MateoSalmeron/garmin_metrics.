"""AI layer — the only file that knows how AI is called.

POC:        uses `claude --print` (no API key needed)
Production: swap _call_claude_api() and set USE_API=true in .env

To switch: change USE_API to true and set ANTHROPIC_API_KEY in .env.
Nothing else in the codebase needs to change.
"""

import json
import os
import subprocess
from datetime import date as _date

from config import CURRENT_METRICS, CURRENT_PLAN, PENDING_PLAN, PROFILE_FILE, PROMPTS_DIR
from races.recorder import load_all_races

USE_API = os.getenv("USE_API", "false").lower() == "true"

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_NAMES_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def ask_claude(prompt: str) -> str:
    """Send a prompt to Claude and return the response string."""
    if USE_API:
        return _call_claude_api(prompt)
    return _call_claude_print(prompt)


def build_prompt(
    template_name: str,
    extra: dict | None = None,
    history: list[dict] | None = None,
) -> str:
    """Compose a prompt: date + template + metrics + profile + plan + races + history + extra."""
    today     = _date.today()
    day_en    = _DAY_NAMES[today.weekday()]
    day_es    = _DAY_NAMES_ES[today.weekday()]
    date_line = (
        f"[FECHA ACTUAL: {day_es} {today.day} de {_month_es(today.month)} de {today.year} "
        f"({day_en} {today.isoformat()})]"
    )

    parts = [date_line, (PROMPTS_DIR / f"{template_name}.txt").read_text()]

    if CURRENT_METRICS.exists():
        parts.append(f"\n## Training metrics\n{CURRENT_METRICS.read_text()}")

    if PROFILE_FILE.exists():
        parts.append(f"\n## Athlete profile\n{PROFILE_FILE.read_text()}")

    # Prefer pending plan (being refined) over the saved one
    plan_file = PENDING_PLAN if PENDING_PLAN.exists() else CURRENT_PLAN
    if plan_file.exists():
        label = "Training plan (pending approval)" if PENDING_PLAN.exists() else "Current training plan"
        parts.append(f"\n## {label}\n{plan_file.read_text()}")

    all_races = load_all_races()
    if all_races:
        parts.append(
            f"\n## Race history (all results, most recent first)\n"
            f"{json.dumps(all_races, indent=2, ensure_ascii=False)}"
        )

    if history:
        lines = []
        for msg in history:
            role    = "Usuario" if msg["role"] == "user" else "Asistente"
            content = msg["content"][:600]  # trim very long messages
            lines.append(f"[{role}]: {content}")
        parts.append(f"\n## Conversación reciente\n" + "\n".join(lines))

    if extra:
        parts.append(f"\n## Additional context\n{json.dumps(extra, indent=2, ensure_ascii=False)}")

    return "\n".join(parts)


def _month_es(m: int) -> str:
    return ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"][m - 1]


# ── POC implementation ────────────────────────────────────────────────────────

def _call_claude_print(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "--print", prompt],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude --print failed: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Production implementation (Phase 4) ──────────────────────────────────────

def _call_claude_api(prompt: str) -> str:
    import anthropic  # only imported when USE_API=true

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
