from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

ACTIVITIES_DIR     = DATA_DIR / "activities"
METRICS_DIR        = DATA_DIR / "metrics"
TRAINING_PLANS_DIR = DATA_DIR / "plans" / "training"
DIET_PLANS_DIR     = DATA_DIR / "plans" / "diet"
RACES_DIR          = DATA_DIR / "races"
HISTORY_DIR        = DATA_DIR / "history"
PROFILE_FILE       = DATA_DIR / "profile.json"
JOURNAL_FILE       = DATA_DIR / "journal.json"
CONVERSATION_FILE  = DATA_DIR / "conversation.json"
CURRENT_METRICS    = METRICS_DIR / "current.json"
CURRENT_PLAN       = TRAINING_PLANS_DIR / "current.txt"
PENDING_PLAN       = TRAINING_PLANS_DIR / "pending.txt"
CURRENT_DIET       = DIET_PLANS_DIR / "current.txt"
PROMPTS_DIR        = BASE_DIR / "ai" / "prompts"

for _d in [ACTIVITIES_DIR, METRICS_DIR, TRAINING_PLANS_DIR, DIET_PLANS_DIR, RACES_DIR, HISTORY_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
