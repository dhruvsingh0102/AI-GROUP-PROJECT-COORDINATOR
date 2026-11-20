# Coordinator project handoff

## Goal
Build W-PS-1, AI Group Project Coordinator. Dhruv is building the project solo; the demo coordinates a small simulated project with real WhatsApp participants. Required loop: task → WhatsApp follow-up → participant reply → task-status update. “The API is connected, but I am waiting for test credentials” must produce **Blocked** with blocker **test credentials**, never Complete. A Blocked task should notify its designated unblocker when WhatsApp allows delivery.

## Rules
- Keep task classification conservative. Do not lower confidence thresholds to make tests pass.
- Blocker evidence takes precedence over completion language.
- Ambiguous replies remain Needs Clarification (or In Progress if they clearly say work is underway).
- Multi-task messages must not silently apply to the wrong task.
- Keep Meta, Supabase, and LLM credentials in `.env`; never print or commit them.
- The optional OpenCode model may identify a high-confidence blocker but cannot mark a task Complete.
- WhatsApp integration must verify Meta webhook signatures and honor its messaging window/template rules.

## Current implementation
- `engine.py` classifies replies; `test_engine.py` covers the required credentials case, vague replies, Hinglish blockers, negated completion, and ambiguous multi-task replies.
- `bot.py` is a FastAPI webhook for WhatsApp Business Cloud API. It supports profile linking with `/start <name>`, `/tasks`, `/ask <task_id>`, `/update <task_id> <reply>`, plain replies for one unambiguous open assigned task, blocker escalation, and duplicate webhook event suppression.
- `storage.py` supports SQLite local data and Supabase hosted data. WhatsApp profile phones and recent inbound timestamps are stored per person.
- Streamlit dashboard shows status counts, blockers, participant updates, WhatsApp link status, follow-ups, owner/unblocker editing, task search and filters, and a `/ask <task_id>` command.
- `seed.py` loads the demo coordinator, assignee, and unblocker. The task starts Pending and is assigned to the second name.
- Existing Supabase project: apply `supabase/whatsapp_migration.sql` in SQL Editor. Fresh project: apply `supabase/schema.sql`.

## WhatsApp requirements
- Create a Meta developer app with WhatsApp product and use a test business number to start.
- Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, and `WHATSAPP_APP_SECRET` in the server's `.env` or deployment environment.
- Meta webhooks require a public HTTPS callback at `/webhook`; subscribe the app to the WhatsApp `messages` field.
- Participants message the business number first with `/start <their seeded name>`. This links their phone and opens a reply window. Free-form outbound follow-ups/escalations are sent only while the recipient has a recent inbound window; if it expires, ask them to message again or configure an approved template.
- The local webhook can be exposed through an HTTPS tunnel during development. Never commit the tunnel URL if it contains credentials; it should not.

## Setup and run
1. `python3 -m venv .venv`
2. Activate it and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`; fill in the Meta WhatsApp values locally. `LLM_API_KEY` is optional for the deterministic scenario.
4. Run the Supabase migration/schema as appropriate, then `python test_engine.py` and `python check_setup.py`.
5. Seed with `python seed.py <coordinator> <participant> <unblocker>`.
6. In separate terminals run `python bot.py` and `streamlit run dashboard.py --server.address 127.0.0.1`.
7. Configure the public HTTPS webhook in Meta, then each participant messages the business number with `/start <their name>`. Test with `/update <task_id> The API is connected, but I am waiting for test credentials.` Expect Blocked / test credentials.

## Known limits / next steps
- Dashboard changes are manual and do not generate a WhatsApp escalation.
- The first WhatsApp implementation sends ordinary text messages, so recipient replies must have opened a valid 24-hour messaging window. Approved templates are not implemented yet.
- An unblocker must link their own phone to receive live escalations. A solo developer can verify the task classification without a second participant phone, but cannot verify actual delivery to a separate unblocker account alone.
- LLM fallback is used only for ambiguous replies and only to infer a high-confidence blocker. The rule-based required scenario works without a key.
- Do not ask users to paste credentials into chat; have them enter values directly in `.env` or deployment secrets.
