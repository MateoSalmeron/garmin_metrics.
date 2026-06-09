# Triathlon AI Training System

A local-first personal triathlon coach. Syncs your Garmin workouts, calculates training load metrics, and uses Claude AI to generate personalized training plans, weekly analysis, and daily diet recommendations — all controlled from a Telegram bot on your phone.

Everything runs on your laptop. Your data never leaves your machine.

---

## How it works

```
Garmin Connect (last 6 months)
      ↓
garmin/sync.py          ← downloads activities + detects races automatically
      ↓
data/activities/        ← one JSON per workout
data/races/             ← one JSON per race result (with splits)
      ↓
metrics/calculator.py   ← volume, HR zones, avg paces (4w / 12w / 6m windows)
      ↓
data/metrics/current.json
      ↓
ai/layer.py             ← ask_claude(prompt) → response
                           always injects: current date, metrics, profile,
                           race history, active plan, conversation context
      ↓
Telegram bot            ← your interface from phone or laptop
```

---

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://claude.ai/code) installed and logged in (`claude --version`)
- A Garmin Connect account with activities
- A Telegram account

---

## Setup

### 1. Create your Telegram bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a display name and a username ending in `bot`
4. Copy the token BotFather gives you

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...   # from BotFather
GARMIN_USERNAME=your@email.com
GARMIN_PASSWORD=yourpassword
ANTHROPIC_API_KEY=                        # leave empty for now (Phase 4)
USE_API=false                             # keep false — uses claude --print
```

### 3. Fill in your profile

Edit `data/profile.json` — this is what makes AI advice personal rather than generic:

```json
{
  "name": "Mateo",
  "age": 30,
  "height_cm": 180,
  "weight_kg": 83,
  "max_hr": null,
  "resting_hr": null,
  "level": "intermediate",
  "goal": "finish_olimpico",
  "available_days": ["lunes", "martes", "jueves", "sabado", "domingo"],
  "max_hours_per_week": 15,
  "target_races": [
    {
      "name": "Triatlón X",
      "date": "2027-05-15",
      "distance": "olimpico",
      "priority": "A",
      "goal_time": null
    }
  ],
  "injuries_history": ["Fasciitis plantar"]
}
```

**Profile fields:**

| Field | Notes |
|-------|-------|
| `age` | Used to estimate max HR (220 − age) if `max_hr` is null |
| `max_hr` | Overrides the estimate if you know your real max HR |
| `resting_hr` | Enables Karvonen HR zone calculation (more precise) |
| `level` | `beginner` / `intermediate` / `advanced` |
| `goal` | `finish_olimpico` / `improve_time` / `podium` |
| Race `priority` | `A` = goal race (full taper) · `B` = important · `C` = training race |

### 4. Install and run

```bash
make install   # creates .venv and installs dependencies
make run       # starts the bot
```

Open Telegram, find your bot, send `/help`.

---

## Commands

### Training
| Command | What it does |
|---------|-------------|
| `/sync` | Download last 6 months from Garmin, recalculate all metrics |
| `/estado` | Quick fitness check — fresh / loaded / fatigued (5 lines) |
| `/analizar` | Deep analysis of last 6 months with expert coach AI |
| `/resumen` | Fitness summary + predicted times for 5K, 10K, half marathon, sprint tri, olympic tri |
| `/alerta` | Check for overtraining risk |

### Plans
| Command | What it does |
|---------|-------------|
| `/plan [instrucciones]` | Generate a full-season plan up to your next A race. Optional: add instructions inline |
| `/guardar_plan` | Save the plan once you're happy with it |
| `/ver_plan` | View the current or pending plan |

### Diet
| Command | What it does |
|---------|-------------|
| `/dieta` | Generate a weekly nutrition plan adapted to training load |
| `/ver_dieta` | View the saved diet |

### Races
| Command | What it does |
|---------|-------------|
| `/carreras` | List upcoming races with countdown |
| `/nueva_carrera` | Add a race to the calendar |
| `/resultados` | View past race results |
| `/registrar_carrera` | Log a race result manually |

### Other
| Command | What it does |
|---------|-------------|
| `/nota <text>` | Log post-workout feeling — AI reads it as context |
| `/help` | List all commands |
| **free chat** | Ask anything — AI answers with full context loaded |

---

## Plan workflow

The plan is never saved automatically. You control when it's committed:

```
/plan                      → generates plan, shows it, does NOT save
/plan más natación este mes → same with extra instructions
[free chat to refine]       → AI keeps plan in context, adapts on request
/guardar_plan              → saves when you're happy
/ver_plan                  → shows pending or saved plan
```

---

## Adding race results

**Automatically:** `/sync` detects activities Garmin has marked as races and saves them with splits.

**Manually:**
```
/registrar_carrera nombre|fecha|distancia|tiempo[|pos_general][|pos_cat][|notas]
```
Example:
```
/registrar_carrera 10K Valencia|2026-03-15|10k|44:30|38|6|Bien hasta el km 8
```

Distances: `5k` `10k` `media_maraton` `maraton` `sprint` `olimpico` `medio` `iron`

Race history is automatically included in every AI call — plans and predictions are based on your real times, not estimates.

---

## Conversation context

The bot maintains a rolling conversation window (last 5 exchanges, 4-hour window). This means:

- After `/plan` or `/dieta`, keep chatting to refine — the AI remembers what it just told you
- `/sync` clears the history (fresh data = fresh start)

The AI always knows the current date and day of the week (injected automatically), so schedules and race countdowns are always accurate.

---

## Data structure

All data lives in `data/` on your laptop (Docker volume if running containerised):

```
data/
├── activities/        ← one JSON per Garmin workout
├── races/             ← one JSON per race result (time, splits, position, HR)
├── metrics/
│   └── current.json   ← recalculated on every /sync
├── plans/
│   ├── training/
│   │   ├── current.txt   ← saved training plan
│   │   └── pending.txt   ← plan awaiting approval
│   └── diet/
│       └── current.txt   ← saved diet plan
├── history/           ← planned vs actual compliance (Phase 2)
├── conversation.json  ← rolling chat history (auto-managed)
├── profile.json       ← your personal profile (edit this)
└── journal.json       ← post-workout feelings
```

`data/` is in `.gitignore` — personal data never reaches GitHub.

---

## Makefile

```bash
make run      # Start bot locally (POC — uses claude --print)
make stop     # Kill the running bot
make install  # Create .venv and install dependencies
make help     # Show all commands
```

Docker (Phase 4, requires `ANTHROPIC_API_KEY`):
```bash
make up       # Start in Docker background
make down     # Stop containers
make logs     # Follow logs
make build    # Rebuild image
```

---

## Debug — run modules directly

```bash
python -m garmin.sync          # sync and print what was saved
python -m metrics.calculator   # recalculate metrics and print JSON
```

---

## Switching to production AI (Phase 4)

When you want to move from `claude --print` to the Anthropic API:

1. Get a key at [console.anthropic.com](https://console.anthropic.com)
2. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...` and `USE_API=true`

That's the only change needed. Docker always uses `USE_API=true` automatically.

---

## Roadmap

- [x] Architecture design and project plan
- [x] Full project scaffolding (modules, Makefile, Docker)
- [x] Phase 1 — Garmin sync (6 months), metrics, Claude `--print`, `/sync` `/estado` `/analizar` `/resumen`
- [x] Phase 1+ — Race tracking (auto + manual), conversation context, date injection, long-term plan with approval flow, diet
- [ ] Phase 2 — CTL/ATL/TSB, plan vs actual compliance tracking
- [ ] Phase 3 — Race periodization (base/build/peak/taper auto-detection), overtraining automation
- [ ] Phase 4 — Claude API, Docker deployment, optional web dashboard
