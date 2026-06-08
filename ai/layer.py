"""AI layer — the only file that knows how AI is called.

POC:        uses `claude --print` (no API key needed)
Production: swap _call_claude_api() and set USE_API=true in .env

To switch: change USE_API to true and set ANTHROPIC_API_KEY in .env.
Nothing else in the codebase needs to change.
"""

import json
import os
import subprocess

from config import CURRENT_METRICS, CURRENT_PLAN, PROFILE_FILE, PROMPTS_DIR

USE_API = os.getenv("USE_API", "false").lower() == "true"


def ask_claude(prompt: str) -> str:
    """Send a prompt to Claude and return the response string."""
    if USE_API:
        return _call_claude_api(prompt)
    return _call_claude_print(prompt)


def build_prompt(template_name: str, extra: dict | None = None) -> str:
    """Compose a prompt from a template + current metrics + user profile."""
    parts = [(PROMPTS_DIR / f"{template_name}.txt").read_text()]

    if CURRENT_METRICS.exists():
        parts.append(f"\n## Training metrics\n{CURRENT_METRICS.read_text()}")

    if PROFILE_FILE.exists():
        parts.append(f"\n## Athlete profile\n{PROFILE_FILE.read_text()}")

    if CURRENT_PLAN.exists():
        parts.append(f"\n## Current training plan\n{CURRENT_PLAN.read_text()}")

    if extra:
        parts.append(f"\n## Additional context\n{json.dumps(extra, indent=2, ensure_ascii=False)}")

    return "\n".join(parts)


# ── POC implementation ────────────────────────────────────────────────────────

def _call_claude_print(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "--print", prompt],
        capture_output=True,
        text=True,
        timeout=120,
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
