.PHONY: install run stop up down logs build help

VENV   = .venv
PYTHON = $(VENV)/bin/python
PIP    = $(VENV)/bin/pip

help:        ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

# ── Local (POC) ────────────────────────────────────────────────────────────────

$(VENV):
	python3 -m venv $(VENV)

install: $(VENV)  ## Create virtualenv and install dependencies
	$(PIP) install -r requirements.txt

run: $(VENV)      ## Start the bot locally (uses claude --print)
	PYTHONPATH=. $(PYTHON) bot/telegram_bot.py

stop:             ## Kill the locally running bot
	pkill -f "python bot/telegram_bot.py" || echo "Bot was not running"

# ── Docker (Phase 4 — requires ANTHROPIC_API_KEY) ──────────────────────────────

up:               ## Start bot in Docker background (needs API key)
	docker compose up -d

down:             ## Stop and remove Docker containers
	docker compose down

logs:             ## Follow Docker container logs
	docker compose logs -f bot

build:            ## Rebuild Docker image
	docker compose build
