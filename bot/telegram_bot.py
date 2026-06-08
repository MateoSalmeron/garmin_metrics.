"""Telegram bot — all commands."""

import json
import logging
import os
from datetime import date, datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai.layer import ask_claude, build_prompt
from config import (
    CURRENT_DIET,
    CURRENT_METRICS,
    CURRENT_PLAN,
    JOURNAL_FILE,
    PROFILE_FILE,
)
from garmin.sync import sync_activities
from metrics.calculator import calculate_metrics

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )


async def _send_long(message, text: str) -> None:
    """Split responses that exceed Telegram's 4096 char limit."""
    for i in range(0, len(text), 4000):
        await message.reply_text(text[i : i + 4000])


def _load_profile() -> dict:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text())
    return {}


def _next_a_race(profile: dict) -> dict | None:
    races = [
        r for r in profile.get("target_races", [])
        if r.get("priority") == "A" and r.get("date", "") >= str(date.today())
    ]
    return min(races, key=lambda r: r["date"]) if races else None


def _weeks_until(date_str: str) -> int:
    delta = datetime.strptime(date_str, "%Y-%m-%d").date() - date.today()
    return max(0, delta.days // 7)


def _load_journal_recent(days: int = 14) -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    entries = json.loads(JOURNAL_FILE.read_text())
    cutoff = str(date.today() - __import__("datetime").timedelta(days=days))
    return [e for e in entries if e.get("date", "") >= cutoff]


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Syncing last 3 months from Garmin Connect...")
    try:
        saved = sync_activities()
        calculate_metrics()
        msg = f"✓ Done. {len(saved)} new activities downloaded, metrics updated."
        if not saved:
            msg = "✓ Done. No new activities since last sync. Metrics refreshed."
        await update.message.reply_text(msg)
    except Exception as e:
        log.exception("sync failed")
        await update.message.reply_text(f"Sync failed: {e}")


async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CURRENT_METRICS.exists():
        await update.message.reply_text("No metrics yet — run /sync first.")
        return
    await _typing(update, context)
    try:
        prompt = build_prompt("status")
        await _send_long(update.message, ask_claude(prompt))
    except Exception as e:
        log.exception("estado failed")
        await update.message.reply_text(f"Error: {e}")


async def cmd_analizar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CURRENT_METRICS.exists():
        await update.message.reply_text("No metrics yet — run /sync first.")
        return
    await update.message.reply_text("Analizando los últimos 3 meses... (puede tardar un momento)")
    await _typing(update, context)
    try:
        prompt = build_prompt("analysis", extra={"journal_recent": _load_journal_recent()})
        await _send_long(update.message, ask_claude(prompt))
    except Exception as e:
        log.exception("analizar failed")
        await update.message.reply_text(f"Error: {e}")


async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CURRENT_METRICS.exists():
        await update.message.reply_text("No metrics yet — run /sync first.")
        return
    await update.message.reply_text("Generando resumen y predicciones...")
    await _typing(update, context)
    try:
        profile = _load_profile()
        next_race = _next_a_race(profile)
        extra = {"next_a_race": next_race}
        if next_race:
            extra["weeks_until_race"] = _weeks_until(next_race["date"])
        prompt = build_prompt("summary", extra=extra)
        await _send_long(update.message, ask_claude(prompt))
    except Exception as e:
        log.exception("resumen failed")
        await update.message.reply_text(f"Error: {e}")


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _load_profile()
    next_race = _next_a_race(profile)
    if not next_race:
        await update.message.reply_text(
            "No hay ninguna carrera A en tu calendario. "
            "Añade una con /nueva_carrera o edita data/profile.json."
        )
        return
    weeks = _weeks_until(next_race["date"])
    if weeks < 2:
        await update.message.reply_text("La carrera A es en menos de 2 semanas. No tiene sentido generar un plan ahora.")
        return

    await update.message.reply_text(
        f"Generando plan de temporada para *{next_race['name']}* ({weeks} semanas)...\n"
        "Esto puede tardar un poco.",
        parse_mode="Markdown",
    )
    await _typing(update, context)
    try:
        extra = {
            "next_a_race": next_race,
            "weeks_until_race": weeks,
            "today": str(date.today()),
        }
        prompt = build_prompt("plan", extra=extra)
        plan_text = ask_claude(prompt)
        CURRENT_PLAN.write_text(plan_text)
        await _send_long(update.message, plan_text)
        await update.message.reply_text("Plan guardado. Consúltalo en cualquier momento con /ver_plan.")
    except Exception as e:
        log.exception("plan failed")
        await update.message.reply_text(f"Error: {e}")


async def cmd_ver_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CURRENT_PLAN.exists():
        await update.message.reply_text("No hay ningún plan guardado. Genera uno con /plan.")
        return
    await _send_long(update.message, CURRENT_PLAN.read_text())


async def cmd_dieta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Generando propuesta nutricional semanal...")
    await _typing(update, context)
    try:
        extra = {"journal_recent": _load_journal_recent(7)}
        prompt = build_prompt("diet", extra=extra)
        diet_text = ask_claude(prompt)
        CURRENT_DIET.write_text(diet_text)
        await _send_long(update.message, diet_text)
        await update.message.reply_text("Dieta guardada. Consúltala con /ver_dieta.")
    except Exception as e:
        log.exception("dieta failed")
        await update.message.reply_text(f"Error: {e}")


async def cmd_ver_dieta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CURRENT_DIET.exists():
        await update.message.reply_text("No hay ninguna dieta guardada. Genera una con /dieta.")
        return
    await _send_long(update.message, CURRENT_DIET.read_text())


async def cmd_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CURRENT_METRICS.exists():
        await update.message.reply_text("No metrics yet — run /sync first.")
        return
    await _typing(update, context)
    try:
        prompt = build_prompt("overtraining")
        await _send_long(update.message, ask_claude(prompt))
    except Exception as e:
        log.exception("alerta failed")
        await update.message.reply_text(f"Error: {e}")


async def cmd_nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /nota <your note>\nExample: /nota Piernas muy pesadas, dormí mal")
        return

    entries = json.loads(JOURNAL_FILE.read_text()) if JOURNAL_FILE.exists() else []
    entries.append({"date": str(date.today()), "note": text})
    JOURNAL_FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    await update.message.reply_text(f"✓ Nota guardada: \"{text}\"")


async def cmd_carreras(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _load_profile()
    races = sorted(profile.get("target_races", []), key=lambda r: r.get("date", ""))
    if not races:
        await update.message.reply_text(
            "No hay carreras en tu calendario.\nAñade una con /nueva_carrera"
        )
        return

    today = str(date.today())
    lines = ["*Carreras programadas:*\n"]
    for r in races:
        weeks = _weeks_until(r["date"])
        status = f"{weeks}w left" if r["date"] >= today else "✓ completada"
        priority_label = {"A": "🔴 A", "B": "🟡 B", "C": "⚪ C"}.get(r.get("priority", ""), r.get("priority", ""))
        lines.append(
            f"{priority_label} *{r['name']}*\n"
            f"   📅 {r['date']} ({r.get('distance', '?')}) — {status}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_nueva_carrera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /nueva_carrera nombre|fecha|distancia|prioridad
    Example: /nueva_carrera Triatlón Sprint|2026-09-15|sprint|B
    """
    raw = " ".join(context.args) if context.args else ""
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) != 4:
        await update.message.reply_text(
            "Formato: /nueva_carrera nombre|fecha|distancia|prioridad\n\n"
            "Ejemplo:\n/nueva_carrera Triatlón Sprint Santander|2026-09-15|sprint|B\n\n"
            "Distancias: sprint, olimpico, media, iron\n"
            "Prioridades: A (objetivo), B (importante), C (entrenamiento)"
        )
        return

    name, race_date, distance, priority = parts

    try:
        datetime.strptime(race_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Fecha inválida. Usa el formato YYYY-MM-DD, ej: 2026-09-15")
        return

    if priority.upper() not in ("A", "B", "C"):
        await update.message.reply_text("Prioridad debe ser A, B o C.")
        return

    profile = _load_profile()
    profile.setdefault("target_races", []).append({
        "name":     name,
        "date":     race_date,
        "distance": distance.lower(),
        "priority": priority.upper(),
        "goal_time": None,
        "notes":    "",
    })
    PROFILE_FILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    await update.message.reply_text(
        f"✓ Carrera añadida:\n*{name}* — {race_date} ({distance}) — Prioridad {priority.upper()}",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*Comandos disponibles:*\n\n"
        "📡 /sync — Descargar últimos 3 meses de Garmin\n"
        "⚡ /estado — Check rápido de forma actual\n"
        "🔍 /analizar — Análisis profundo de los últimos 3 meses\n"
        "📊 /resumen — Resumen + predicciones de tiempos\n\n"
        "🗓 /plan — Generar plan de temporada hasta tu próxima carrera A\n"
        "📋 /ver\\_plan — Ver el plan guardado\n\n"
        "🥗 /dieta — Generar propuesta nutricional semanal\n"
        "🍽 /ver\\_dieta — Ver la dieta guardada\n\n"
        "🚨 /alerta — Comprobar riesgo de sobreentrenamiento\n\n"
        "🏁 /carreras — Ver carreras del calendario\n"
        "➕ /nueva\\_carrera — Añadir una carrera\n\n"
        "📝 /nota <texto> — Guardar sensación post-entreno\n\n"
        "💬 *Chat libre* — Escríbeme cualquier pregunta"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_free_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    await _typing(update, context)
    try:
        extra = {
            "user_message":   user_text,
            "journal_recent": _load_journal_recent(7),
        }
        profile = _load_profile()
        next_race = _next_a_race(profile)
        if next_race:
            extra["next_a_race"] = next_race
            extra["weeks_until_race"] = _weeks_until(next_race["date"])

        prompt = build_prompt("chat", extra=extra)
        await _send_long(update.message, ask_claude(prompt))
    except Exception as e:
        log.exception("free chat failed")
        await update.message.reply_text(f"Error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("sync",          cmd_sync))
    app.add_handler(CommandHandler("estado",        cmd_estado))
    app.add_handler(CommandHandler("analizar",      cmd_analizar))
    app.add_handler(CommandHandler("resumen",       cmd_resumen))
    app.add_handler(CommandHandler("plan",          cmd_plan))
    app.add_handler(CommandHandler("ver_plan",      cmd_ver_plan))
    app.add_handler(CommandHandler("dieta",         cmd_dieta))
    app.add_handler(CommandHandler("ver_dieta",     cmd_ver_dieta))
    app.add_handler(CommandHandler("alerta",        cmd_alerta))
    app.add_handler(CommandHandler("nota",          cmd_nota))
    app.add_handler(CommandHandler("carreras",      cmd_carreras))
    app.add_handler(CommandHandler("nueva_carrera", cmd_nueva_carrera))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_chat))

    log.info("Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
