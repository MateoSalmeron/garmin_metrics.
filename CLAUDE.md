# CLAUDE.md — Triathlon AI Training System

## What this project is

A **local-first** personal triathlon training assistant. It pulls workout data from Garmin Connect, calculates performance metrics (CTL/ATL/TSB, HR zones, weekly volume), and uses Claude AI to generate personalized training plans, weekly analysis, and daily diet recommendations. The interface is a Telegram bot running on the user's laptop.

The user (Mateo) practices triathlon (swim/bike/run), has a Garmin watch with GPS + HRM, but **no power meter**.

---

## Architecture (8 layers)

```
Garmin Connect
      ↓
[1] python-garminconnect     — data extraction (pip library, no AI tokens consumed)
      ↓
[2] /data/activities/        — raw JSON per activity
      ↓
[3] metrics.py               — calculates CTL/ATL/TSB, HR zones, volume trends
      ↓
[4] /data/metrics/current.json  — calculated metrics ready for AI
      ↓
[5] ai_layer.py              — decoupled AI interface (POC: claude --print / prod: Anthropic API)
      ↓
[6] /data/plans/             — training/diet plans with validation state
      ↓
[7] Telegram bot             — conversational interface via polling (no server needed)
      ↑↓
User (mobile or terminal)
```

---

## Key design principles

- **Local first**: everything runs on the user's laptop. Only Telegram is external.
- **Decoupled AI layer**: `ai_layer.py` exposes a single `ask_claude(prompt: str) -> str` function. Swapping POC → production = changing one module, nothing else.
- **JSON storage**: all data in `/data/`. Human-readable, LLM-friendly, no DB needed.
- **No RAG**: all context (metrics + profile + plan) fits comfortably in Claude's context window.
- **Docker**: full system dockerized for portability (laptop → Raspberry Pi → VPS).

---

## Directory structure

```
/
├── bot/
│   └── telegram_bot.py      # Telegram bot, all commands
├── scripts/
│   ├── sync.py              # uses python-garminconnect library, dumps JSONs
│   └── metrics.py           # calculates all training metrics
├── ai/
│   └── ai_layer.py          # SINGLE interface: ask_claude(prompt) -> str
├── data/                    # gitignored if personal data; mounted as Docker volume
│   ├── activities/          # one JSON per Garmin activity
│   ├── metrics/             # current.json + historical
│   ├── plans/
│   │   ├── training/        # weekly plans with status (propuesto/validado/modificado)
│   │   └── diet/            # daily diet plans
│   ├── history/             # compliance log: planned vs actual
│   ├── profile.json         # static user profile, always loaded by AI
│   └── journal.json         # post-workout feelings log
├── prompts/                 # prompt templates (weekly_analysis, plan, diet, etc.)
├── Dockerfile
├── docker-compose.yml
├── .env                     # credentials — NEVER commit
├── .env.example             # template — commit this
└── requirements.txt
```

---

## Telegram bot commands

| Command | Action |
|---------|--------|
| `/sync` | Download new Garmin activities + recalculate metrics |
| `/status` | Current fitness snapshot (CTL/ATL/TSB + weekly volume) |
| `/analyze` | Full AI analysis of recent weeks |
| `/plan` | Generate next week's training plan |
| `/plan validate` | Validate proposed plan |
| `/diet` | Daily diet based on training load |
| `/note <text>` | Add entry to feelings journal |
| `/races` | List target races |
| `/help` | List commands |
| free chat | Any question — AI responds with full context loaded |

---

## AI layer (POC vs production)

**POC** — Claude Code `--print` mode (no API key needed):
```bash
claude --print "$(cat prompts/weekly_analysis.txt) $(cat data/metrics/current.json)"
```

**Production** — Claude API (when POC is validated):
```python
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-opus-4-8",  # or claude-sonnet-4-6 for lower cost
    max_tokens=2000,
    messages=[{"role": "user", "content": prompt}]
)
```

Cost estimate: ~5,000 tokens per weekly analysis ≈ €0.02.

---

## Environment variables (.env)

```
TELEGRAM_BOT_TOKEN=
GARMIN_USERNAME=
GARMIN_PASSWORD=
ANTHROPIC_API_KEY=       # only needed in production mode
```

---

## Implementation phases

| Phase | Status | Scope |
|-------|--------|-------|
| **Phase 1 — POC** | 🔲 todo | python-garminconnect setup, sync script, basic metrics, Claude --print, Telegram /sync /status /analyze |
| **Phase 2 — Core** | 🔲 todo | CTL/ATL/TSB, plan generation + persistence, journal, plan validation, plan vs actual tracking |
| **Phase 3 — Diet & periodization** | 🔲 todo | Diet module, periodization logic (base/build/peak/taper), overtraining alerts |
| **Phase 4 — Production** | 🔲 todo | Migrate AI to Claude API, evaluate Raspberry Pi deployment, optional web dashboard |

**Rule: never start a phase until the previous one is working end-to-end.**

---

## Critical implementation notes

- `ai_layer.py` must be the ONLY file that knows how AI is called. All other modules call `ask_claude()`.
- Scripts must be runnable both from the bot AND from the terminal directly (for development/debugging).
- `profile.json` is always injected into every AI call — it's what makes recommendations personal, not generic.
- Bot must handle errors gracefully: Garmin timeouts, AI slowness, missing data, etc.
- JSON schemas must be documented precisely so a future DB migration or UI is straightforward.
- No credentials in code. Ever. `.env` + `python-dotenv`.
