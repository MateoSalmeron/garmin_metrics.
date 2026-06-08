# Triathlon AI Training System

A local-first personal triathlon coach. Syncs your Garmin workouts, calculates training load metrics (CTL/ATL/TSB, HR zones, weekly volume), and uses Claude AI to generate personalized training plans, weekly analysis, and daily diet recommendations — all controlled from a Telegram bot on your phone.

Everything runs on your laptop. Your data never leaves your machine.

---

## How it works

```
Garmin Connect
      ↓
garmin/sync.py          ← downloads activities as JSON files
      ↓
data/activities/        ← one JSON per workout
      ↓
metrics/calculator.py   ← calculates CTL/ATL/TSB, HR zones, weekly volume
      ↓
data/metrics/current.json
      ↓
ai/layer.py             ← ask_claude(prompt) → response
      ↓
Telegram bot            ← your interface from phone or laptop
```

---

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://claude.ai/code) installed and logged in (`claude --version` should work)
- A Garmin Connect account with some activities
- A Telegram account

---

## Step 1 — Create your Telegram bot

You need a bot token to connect the system to your Telegram.

1. Open Telegram and search for **@BotFather**
2. Send `/start`
3. Send `/newbot`
4. Choose a **display name** — anything you like, e.g. `My Triathlon Coach`
5. Choose a **username** — must be unique and end in `bot`, e.g. `mateo_tri_bot`
6. BotFather replies with your token:
   ```
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   Copy it — you'll need it in the next step.

> The bot is private by default. Only you can talk to it unless you share the link.

---

## Step 2 — Configure credentials

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz   # from BotFather
GARMIN_USERNAME=your@email.com                               # Garmin Connect login
GARMIN_PASSWORD=yourpassword                                 # Garmin Connect password
ANTHROPIC_API_KEY=                                          # leave empty for now (Phase 4)
USE_API=false                                               # keep false (uses claude --print)
```

> `.env` is in `.gitignore` — it will never be committed to git.

---

## Step 3 — Fill in your profile

Edit `data/profile.json` with your personal data. This is what makes AI recommendations specific to you rather than generic:

```json
{
  "name": "Mateo",
  "age": 30,
  "height_cm": 175,
  "weight_kg": 70,
  "max_hr": null,
  "resting_hr": null,
  "level": "intermediate",
  "goal": "finish_olimpico",
  "available_days": ["lunes", "martes", "jueves", "sabado", "domingo"],
  "max_hours_per_week": 10,
  "target_races": [
    {
      "name": "Triatlón X",
      "date": "2026-09-15",
      "distance": "olimpico",
      "priority": "A",
      "goal_time": null
    }
  ]
}
```

**Field reference:**

| Field | Notes |
|-------|-------|
| `age` | Used to estimate max HR (220 − age) if `max_hr` is null |
| `max_hr` | Fill this if you know it from a real test — overrides the estimate |
| `resting_hr` | Optional. Enables more precise HR zones (Karvonen formula) |
| `level` | `beginner` / `intermediate` / `advanced` |
| `goal` | `finish_olimpico` / `improve_time` / `podium` — shapes training intensity |
| `priority` in races | `A` = goal race (full taper) · `B` = important (partial taper) · `C` = training race |

---

## Step 4 — Install dependencies

```bash
make install
```

Or manually:
```bash
pip install -r requirements.txt
```

---

## Step 5 — Run the bot

```bash
make run
```

The bot starts polling. Open Telegram, find your bot by its username, and send `/help`.

> The laptop must be on and the bot must be running for it to respond. No server needed.

---

## Available commands

| Command | What it does |
|---------|-------------|
| `/sync` | Download new Garmin activities + recalculate metrics |
| `/status` | Weekly volume: this week vs last week per sport |
| `/analyze` | Full AI analysis of your recent training |
| `/help` | List of commands |

Phase 2 will add: `/plan`, `/plan validate`, `/diet`, `/note`, `/races`

---

## Where your data is stored

All data lives in `data/` on your laptop:

```
data/
├── activities/        ← one JSON per Garmin workout (e.g. 12345678.json)
├── metrics/
│   └── current.json   ← recalculated on every /sync
├── plans/
│   ├── training/      ← weekly training plans (Phase 2)
│   └── diet/          ← daily diet plans (Phase 3)
├── history/           ← planned vs actual compliance (Phase 2)
├── profile.json       ← your personal profile (edit this)
└── journal.json       ← post-workout feelings log (Phase 2)
```

`data/` is in `.gitignore` so your personal workout data is never pushed to GitHub.

---

## Makefile commands

```bash
make run      # Start bot locally (POC mode, uses claude --print)
make stop     # Kill the running bot
make install  # pip install -r requirements.txt
make help     # Show all commands
```

Docker commands (Phase 4, requires `ANTHROPIC_API_KEY`):
```bash
make up       # Start in Docker background
make down     # Stop and remove containers
make logs     # Follow container logs
make build    # Rebuild Docker image
```

---

## Running each module standalone (for debugging)

Each module can run independently from the terminal:

```bash
python -m garmin.sync          # sync activities, print what was saved
python -m metrics.calculator   # recalculate metrics, print result
```

---

## Roadmap

- [x] Project design and architecture
- [x] Project scaffolding (modules, Docker, Makefile)
- [ ] **Phase 1 — POC**: Garmin sync, basic metrics, Claude `--print`, `/sync` `/status` `/analyze`
- [ ] **Phase 2 — Core**: CTL/ATL/TSB, training plans, journal, plan vs actual tracking
- [ ] **Phase 3 — Diet & periodization**: nutrition module, race periodization, overtraining alerts
- [ ] **Phase 4 — Production**: migrate AI to Claude API, Docker deployment, optional web dashboard

---

## Switching to production mode (Phase 4)

When the POC works and you want to switch to the Anthropic API:

1. Get an API key at [console.anthropic.com](https://console.anthropic.com)
2. Add it to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Set `USE_API=true` in `.env`

That's the only change needed. The rest of the code is untouched.
For Docker deployment, `USE_API=true` is already set inside the container automatically.
