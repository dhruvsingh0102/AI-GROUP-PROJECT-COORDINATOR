"""WhatsApp Cloud API webhook for the project coordinator."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

load_dotenv()

import storage
from engine import analyze_update
from llm import extract_blocker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("coordinator.whatsapp")
app = FastAPI(title="Coordinator WhatsApp webhook")

GRAPH_API_VERSION = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v27.0").strip()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing from the server environment.")
    return value


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if not 8 <= len(digits) <= 15:
        raise ValueError("Invalid WhatsApp phone number.")
    return digits


def send_whatsapp_message(phone: str, message: str) -> None:
    token = _required("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = _required("WHATSAPP_PHONE_NUMBER_ID")
    endpoint = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": normalize_phone(phone),
                "type": "text",
                "text": {"preview_url": False, "body": message[:4000]},
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Could not reach the WhatsApp Cloud API.") from exc
    if not response.ok:
        # Do not log response headers or request credentials.
        raise RuntimeError(f"WhatsApp Cloud API returned HTTP {response.status_code}.")


def _reply(phone: str, text: str) -> None:
    try:
        send_whatsapp_message(phone, text)
    except Exception:
        logger.exception("Could not send WhatsApp reply")


def _list_tasks(sender: str) -> None:
    rows = storage.tasks()
    if not rows:
        _reply(sender, "No tasks yet. Add tasks from the dashboard.")
        return
    lines = [
        f"#{row['id']} {row['title']} — {row['status']}"
        + (f" (blocker: {row['blocker']})" if row.get("blocker") else "")
        for row in rows
    ]
    _reply(sender, "\n".join(lines))


def _ask_for_update(sender: str, task_id: int) -> None:
    row = storage.task(task_id)
    if not row:
        _reply(sender, f"Task #{task_id} was not found.")
        return
    assignee = next((p for p in storage.people() if p["id"] == row["assignee_id"]), None)
    if not assignee:
        _reply(sender, "Assign this task to a participant before sending a follow-up.")
        return
    if not assignee.get("whatsapp_phone"):
        _reply(sender, f"{assignee['name']} must link WhatsApp first by messaging the number with /start {assignee['name']}.")
        return
    if not storage.whatsapp_window_open(assignee):
        _reply(sender, f"Ask {assignee['name']} to message the Coordinator WhatsApp number first. WhatsApp requires an open 24-hour reply window for this follow-up.")
        return
    followup = f"Hi {assignee['name']} — quick update on '{row['title']}'? Please reply with what is done, what remains, or anything blocking you."
    try:
        send_whatsapp_message(assignee["whatsapp_phone"], followup)
    except Exception:
        logger.exception("Could not deliver WhatsApp follow-up")
        _reply(sender, f"WhatsApp could not deliver the follow-up to {assignee['name']}.")
        return
    storage.add_followup(task_id, assignee["id"], followup)
    _reply(sender, f"Follow-up sent to {assignee['name']} for task #{task_id}.")


def _handle_update(sender: str, message: str, forced_task_id: int | None = None) -> None:
    person = storage.person_by_whatsapp(sender)
    if not person:
        _reply(sender, "Link your team profile first with /start Your Name.")
        return
    rows = [row for row in storage.tasks() if row["assignee_id"] == person["id"] and row["status"] != "Complete"]
    if forced_task_id is not None:
        rows = [row for row in rows if row["id"] == forced_task_id]
    if not rows:
        _reply(sender, "You have no open assigned tasks. Ask the coordinator to assign one.")
        return
    if len(rows) > 1:
        matches = [row for row in rows if row["title"].casefold() in message.casefold()]
        if len(matches) != 1:
            choices = "\n".join(f"#{row['id']} {row['title']}" for row in rows)
            _reply(sender, "You have multiple open tasks. Send one update per message and include its task title:\n" + choices)
            return
        rows = matches

    row = rows[0]
    decision = analyze_update(message)
    if decision.status == "Needs Clarification":
        try:
            blocker = extract_blocker(message)
            if blocker:
                from engine import Decision
                decision = Decision("Blocked", blocker, 0.90, "LLM detected an explicit dependency")
        except Exception:
            logger.exception("Optional LLM blocker extraction failed; keeping the rule-based result")

    storage.set_task_status(row["id"], decision.status, decision.blocker)
    storage.add_update(row["id"], person["id"], message, decision.status, decision.blocker)
    if decision.status == "Blocked":
        unblocker = next((p for p in storage.people() if p["id"] == row["unblocker_id"]), None)
        notified = False
        if unblocker and unblocker.get("whatsapp_phone") and storage.whatsapp_window_open(unblocker):
            try:
                send_whatsapp_message(
                    unblocker["whatsapp_phone"],
                    f"Escalation: {person['name']} is blocked on '{row['title']}'. Blocker: {decision.blocker}. Please help unblock this task.",
                )
                notified = True
            except Exception:
                logger.exception("Could not deliver WhatsApp blocker escalation")
        if notified:
            suffix = f" I notified {unblocker['name']} on WhatsApp."
        elif unblocker:
            suffix = f" {unblocker['name']} is the unblocker; they need to message the Coordinator number first so WhatsApp allows an escalation."
        else:
            suffix = " No unblocker is assigned yet."
        _reply(sender, f"Marked '{row['title']}' Blocked — blocker: {decision.blocker}.{suffix}")
    elif decision.status == "Complete":
        _reply(sender, f"Marked '{row['title']}' Complete.")
    elif decision.status == "Needs Clarification":
        _reply(sender, f"I couldn't confidently classify that update. '{row['title']}' remains Needs Clarification. Please say what is done, what remains, or what is blocking you.")
    else:
        _reply(sender, f"Recorded update for '{row['title']}'. Status: In Progress.")


def _process_text_message(sender: str, message: str) -> None:
    text = message.strip()
    start_match = re.match(r"^/?start(?:@\w+)?(?:\s+(.+))?$", text, flags=re.I)
    if start_match:
        name = (start_match.group(1) or "").strip()
        if not name:
            _reply(sender, "Welcome to Coordinator. Link your seeded team profile with /start Your Name.")
            return
        person = next((p for p in storage.people() if p["name"].casefold() == name.casefold()), None)
        if not person:
            _reply(sender, f"I couldn't find '{name}' in the project participants. Ask the coordinator to add your name first.")
            return
        try:
            linked = storage.add_person(person["name"], sender)
        except Exception:
            _reply(sender, "That WhatsApp number is already linked to a different participant. Ask the coordinator to review the participant list.")
            return
        _reply(sender, f"Hi {linked['name']}! Your WhatsApp number is linked. Send a task update here, or use /tasks.")
        return

    person = storage.person_by_whatsapp(sender)
    if not person:
        _reply(sender, "Welcome to Coordinator. Link your seeded team profile first with /start Your Name.")
        return
    storage.note_whatsapp_inbound(person["id"])

    if re.match(r"^/?tasks\s*$", text, flags=re.I):
        _list_tasks(sender)
        return
    ask_match = re.match(r"^/?ask\s+(\d+)\s*$", text, flags=re.I)
    if ask_match:
        _ask_for_update(sender, int(ask_match.group(1)))
        return
    update_match = re.match(r"^/?update\s+(\d+)\s+(.+)$", text, flags=re.I | re.S)
    if update_match:
        _handle_update(sender, update_match.group(2).strip(), int(update_match.group(1)))
        return
    _handle_update(sender, text)


def _verify_signature(payload: bytes, signature: str) -> bool:
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    if not app_secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
def health():
    return {"status": "ok", "provider": "whatsapp"}


@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode", "")
    token = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        return challenge
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    if not _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for item in value.get("messages", []):
                message_id = item.get("id")
                sender = item.get("from")
                if not message_id or not sender:
                    continue
                try:
                    sender = normalize_phone(sender)
                except ValueError:
                    continue
                if not storage.claim_whatsapp_message(message_id):
                    continue
                if item.get("type") != "text":
                    _reply(sender, "Please send your task update as a text message.")
                    continue
                body = (item.get("text") or {}).get("body", "")
                if body.strip():
                    try:
                        _process_text_message(sender, body)
                    except Exception:
                        logger.exception("Could not process a WhatsApp message")
    return {"status": "received"}


@app.on_event("startup")
def initialize_storage():
    storage.init_db()


def main():
    uvicorn.run("bot:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)


if __name__ == "__main__":
    main()
