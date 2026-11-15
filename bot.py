"""Telegram front end. Members link themselves with /start <name>."""
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import storage
from engine import analyze_update
from llm import extract_blocker

load_dotenv()
logging.basicConfig(level=logging.INFO)
# HTTP client INFO logs include request URLs. Telegram bot URLs contain the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        name = " ".join(context.args).strip()
        person = storage.add_person(name, update.effective_user.id)
        await update.message.reply_text(f"Hi {person['name']}! Your Telegram account is linked. Send a task update here, or use /tasks.")
    else:
        await update.message.reply_text("Welcome to Coordinator. Link your seeded team member profile with /start Your Name.")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = storage.tasks()
    if not rows:
        await update.message.reply_text("No tasks yet. Add tasks from the dashboard.")
        return
    body = [f"#{r['id']} {r['title']} — {r['status']}" + (f" (blocker: {r['blocker']})" if r['blocker'] else "") for r in rows]
    await update.message.reply_text("\n".join(body))


async def ask_for_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a real Telegram check-in to a task's assigned participant."""
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /ask <task_id>")
        return
    task_id = int(context.args[0])
    row = storage.task(task_id)
    if not row:
        await update.message.reply_text(f"Task #{task_id} was not found.")
        return
    assignee = next((p for p in storage.people() if p['id'] == row['assignee_id']), None)
    if not assignee:
        await update.message.reply_text("Assign this task to a participant before sending a follow-up.")
        return
    if not assignee['telegram_id']:
        await update.message.reply_text(f"{assignee['name']} must start the bot with /start {assignee['name']} before I can message them.")
        return
    followup = f"Hi {assignee['name']} — quick update on '{row['title']}'? Please reply with what is done, what remains, or anything blocking you."
    try:
        await context.bot.send_message(chat_id=assignee['telegram_id'], text=followup)
    except Exception:
        logging.exception("Could not send task follow-up")
        await update.message.reply_text(f"Telegram could not deliver the follow-up to {assignee['name']}.")
        return
    storage.add_followup(task_id, assignee['id'], followup)
    await update.message.reply_text(f"Follow-up sent to {assignee['name']} for task #{task_id}.")


async def update_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apply an explicit task update: /update <task_id> <reply text>."""
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /update <task_id> <your progress reply>")
        return
    task_id = int(context.args[0])
    row = storage.task(task_id)
    if not row:
        await update.message.reply_text(f"Task #{task_id} was not found.")
        return
    await handle_update(update, context, task_id, " ".join(context.args[1:]))


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE, forced_task_id=None, forced_message=None):
    person = storage.person_by_telegram(update.effective_user.id)
    if not person:
        await update.message.reply_text("Link your profile first with /start Your Name.")
        return
    rows = [r for r in storage.tasks() if r['assignee_id'] == person['id'] and r['status'] != 'Complete']
    if forced_task_id is not None:
        rows = [r for r in rows if r['id'] == forced_task_id]
    if not rows:
        await update.message.reply_text("You have no open assigned tasks. Ask the coordinator to assign one.")
        return
    if len(rows) > 1:
        # Match explicit task title mentions; never guess when a single reply is ambiguous.
        text = update.message.text or ""
        matches = [r for r in rows if r['title'].lower() in text.lower()]
        if len(matches) != 1:
            await update.message.reply_text("You have multiple open tasks. Please send one update per message and include the task title:\n" + "\n".join(f"#{r['id']} {r['title']}" for r in rows))
            return
        rows = matches
    row = rows[0]
    message = forced_message if forced_message is not None else (update.message.text or "")
    decision = analyze_update(message)
    if decision.status == "Needs Clarification":
        # The model can conservatively upgrade ambiguity to Blocked, never to Complete.
        try:
            blocker = extract_blocker(message)
            if blocker:
                from engine import Decision
                decision = Decision("Blocked", blocker, 0.90, "LLM detected an explicit dependency")
        except Exception:
            logging.exception("LLM blocker extraction failed; keeping conservative rule-based decision")
    storage.set_task_status(row['id'], decision.status, decision.blocker)
    storage.add_update(row['id'], person['id'], message, decision.status, decision.blocker)
    if decision.status == "Blocked":
        unblocker = next((p for p in storage.people() if p['id'] == row['unblocker_id']), None)
        if unblocker and unblocker['telegram_id']:
            try:
                await context.bot.send_message(chat_id=unblocker['telegram_id'], text=f"Escalation: {person['name']} is blocked on '{row['title']}'. Blocker: {decision.blocker}. Please help unblock this task.")
            except Exception:
                logging.exception("Could not deliver blocker escalation")
        suffix = f" I notified {unblocker['name']}." if unblocker and unblocker['telegram_id'] else (f" {unblocker['name']} can unblock it; they need to link Telegram with /start {unblocker['name']}." if unblocker else " No unblocker is assigned yet.")
        await update.message.reply_text(f"Marked '{row['title']}' Blocked — blocker: {decision.blocker}.{suffix}")
    elif decision.status == "Complete":
        await update.message.reply_text(f"Marked '{row['title']}' Complete.")
    elif decision.status == "Needs Clarification":
        await update.message.reply_text(f"I couldn't confidently classify that update. '{row['title']}' remains Needs Clarification. Please say what is done, what remains, or what is blocking you.")
    else:
        await update.message.reply_text(f"Recorded update for '{row['title']}'. Status: In Progress.")


def main():
    storage.init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing. Add it to .env first.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("update", update_task))
    app.add_handler(CommandHandler("ask", ask_for_update))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_update))
    print("Coordinator bot is polling Telegram…")
    app.run_polling()


if __name__ == "__main__":
    main()
