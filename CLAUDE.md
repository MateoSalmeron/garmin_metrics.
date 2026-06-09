# CLAUDE.md — Triathlon AI Training System

## What this project is

A local-first personal triathlon coaching assistant for Mateo. Pulls 6 months of workout data from Garmin Connect, calculates performance metrics, and uses Claude AI to generate personalized training plans, weekly analysis, and daily diet recommendations. Interface is a Telegram bot running on the user's laptop.

User: Mateo — triathlete (swim/bike/run), Garmin watch with GPS + HRM, no power meter. Plantar fasciitis history.

---

## Architecture

```
Garmin Connect (last 6 months)
      ↓
[1] garmin/sync.py          — python-garminconnect library, detects races
      ↓
[2] data/activities/        — one JSON per workout
    data/races/             — one JSON per race result (splits, position, HR)
      ↓
[3] metrics/calculator.py   — volume, HR zones, avg paces (4w/12w/6m windows)
      ↓
[4] data/metrics/current.json
      ↓
[5] ai/layer.py             — ask_claude(prompt) / build_prompt()
                               ONLY file that knows how AI is called
      ↓
[6] data/plans/training/    — pending.txt (draft) + current.txt (approved)
    data/plans/diet/        — current.txt
      ↓
[7] bot/telegram_bot.py     — Telegram polling bot, all commands
```

---

## Directory structure

```
/
├── garmin/
│   └── sync.py              # fetch 6 months, detect races, normalize JSONs
├── metrics/
│   └── calculator.py        # CTL/ATL prep, HR zones, paces (4w/12w/6m)
├── races/
│   └── recorder.py          # save/load race results, build_race_result()
├── ai/
│   ├── layer.py             # ask_claude() + build_prompt() — swappable POC/prod
│   └── prompts/
│       ├── analysis.txt     # expert coach, 6-month deep analysis
│       ├── summary.txt      # fitness state + race time predictions
│       ├── plan.txt         # long-term periodization plan
│       ├── diet.txt         # weekly nutrition (sports dietitian persona)
│       ├── status.txt       # quick 5-line fitness check
│       ├── overtraining.txt # fatigue/overtraining detection
│       └── chat.txt         # free chat with full context
├── bot/
│   └── telegram_bot.py      # all commands + conversation history helpers
├── data/                    # runtime data — gitignored
│   ├── activities/          # one JSON per Garmin activity
│   ├── races/               # one JSON per race result
│   ├── metrics/current.json # recalculated on every /sync
│   ├── plans/training/      # current.txt (saved) + pending.txt (draft)
│   ├── plans/diet/          # current.txt
│   ├── history/             # compliance tracking (Phase 2)
│   ├── conversation.json    # rolling chat history (last 20 messages)
│   ├── profile.json         # athlete profile — always loaded by AI
│   └── journal.json         # post-workout feelings
├── config.py                # all paths + auto-creates data dirs on import
├── Makefile
├── Dockerfile / docker-compose.yml
├── .env / .env.example
└── requirements.txt
```

---

## Bot commands

| Command | Description |
|---------|-------------|
| `/sync` | Download last 6 months from Garmin + recalculate metrics. Clears conversation history. |
| `/estado` | Quick fitness check (5 lines) |
| `/analizar` | Deep 6-month analysis — expert coach persona |
| `/resumen` | Fitness summary + race time predictions (5K→iron) |
| `/plan [text]` | Generate long-term plan to next A race. Optional inline instructions. Saves to `pending.txt`. |
| `/guardar_plan` | Commit pending plan to `current.txt` when satisfied |
| `/ver_plan` | Show pending (with reminder) or saved plan |
| `/dieta` | Generate weekly nutrition plan — sports dietitian persona. Saves to `pending`. |
| `/ver_dieta` | Show saved diet |
| `/alerta` | Overtraining/fatigue check |
| `/carreras` | Upcoming races with countdown |
| `/nueva_carrera` | `nombre\|fecha\|distancia\|prioridad` |
| `/resultados` | Past race history |
| `/registrar_carrera` | `nombre\|fecha\|distancia\|tiempo[\|pos][\|notas]` |
| `/nota <text>` | Add journal entry — AI reads it as context |
| `/help` | Command list |
| free chat | Any question — full context + conversation history |

---

## AI layer — POC vs production

**POC** (`USE_API=false`, default):
```bash
claude --print "<full prompt>"
```
Requires Claude Code CLI installed and authenticated locally. Timeout: 180s.

**Production** (`USE_API=true`):
```python
client.messages.create(model="claude-sonnet-4-6", max_tokens=4096, ...)
```
Docker always sets `USE_API=true` (ENV in Dockerfile).

### What `build_prompt()` always injects

Every AI call receives, in order:
1. **Current date and day** (Spanish + English) — fixes day-of-week errors
2. **Prompt template** (from `ai/prompts/`)
3. **Training metrics** (`data/metrics/current.json`)
4. **Athlete profile** (`data/profile.json`)
5. **Active plan** — `pending.txt` if it exists, else `current.txt`
6. **Full race history** (`data/races/*.json`, most recent first)
7. **Conversation history** (last N exchanges, if passed by caller)
8. **Extra context** (command-specific: next race, instructions, journal...)

---

## Conversation history

Stored in `data/conversation.json` as a rolling list of `{role, content, ts}`.

- Max 20 messages retained (10 exchanges)
- Free chat reads last 5 exchanges within a 4-hour window
- `/plan` and `/dieta` clear history and seed it with their response
- `/sync` clears history (fresh data = fresh start)
- Enables natural follow-up: after `/plan`, chat to refine before `/guardar_plan`

---

## Race tracking

**Auto:** `garmin/sync.py` detects activities where `eventType.typeKey == "race"`, saves to `data/races/` with lap splits via `get_activity_splits()`.

**Manual:** `/registrar_carrera nombre|fecha|distancia|tiempo[|pos_general][|pos_categoria][|notas]`

Race data schema:
```json
{
  "id": "2026-03-15_10k_valencia",
  "date": "2026-03-15",
  "name": "10K Valencia",
  "distance": "10k",
  "type": "running",
  "source": "manual",
  "result": { "total_time": "44:30", "position_overall": 38 },
  "splits": {},
  "hr_avg": null,
  "notes": "Bien hasta el km 8"
}
```

---

## Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Always | From @BotFather |
| `GARMIN_USERNAME` | Always | Garmin Connect email |
| `GARMIN_PASSWORD` | Always | Garmin Connect password |
| `ANTHROPIC_API_KEY` | Phase 4 only | From console.anthropic.com |
| `USE_API` | Optional | `false` (default) = claude --print, `true` = Anthropic API |

---

## Implementation phases

| Phase | Status | Scope |
|-------|--------|-------|
| **Phase 1 — POC** | ✅ done | Garmin sync (6m), basic metrics, Claude --print, all core commands |
| **Phase 1+** | ✅ done | Race tracking, conversation history, date injection, plan approval flow, diet |
| **Phase 2 — Core** | 🔲 next | CTL/ATL/TSB, plan vs actual compliance, semanas de descarga automáticas |
| **Phase 3 — Periodization** | 🔲 todo | Auto base/build/peak/taper phases, overtraining automation |
| **Phase 4 — Production** | 🔲 todo | Claude API, Docker deployment, optional web dashboard |

---

## Critical implementation rules

- `ai/layer.py` is the **only** file that knows how AI is called. All other modules call `ask_claude()`.
- `config.py` is the **only** file with path constants. Never hardcode paths elsewhere.
- `data/profile.json` is **always** injected — it's what makes advice personal not generic.
- Scripts must run standalone from terminal: `python -m garmin.sync`, `python -m metrics.calculator`.
- No credentials in code. Ever. `.env` + `python-dotenv` only.
- Plans are **never** auto-saved. Always `pending.txt` first, `/guardar_plan` to commit.
