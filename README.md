# Coordinator

A solo-built W-PS-1 AI Group Project Coordinator. It uses WhatsApp Business Platform Cloud API for real participant updates, Supabase or SQLite for persistence, and simulated project tasks.

## WhatsApp setup

This integration uses Meta's WhatsApp Business Platform Cloud API, not direct automation of a personal WhatsApp account. In Meta for Developers, create an app with the WhatsApp product and use its test number to begin. Copy the access token and phone number ID into `.env`; also set the app secret and a verify token you choose. Keep all credentials in `.env` and never share them in chat.

Meta must be able to reach a public HTTPS webhook. For local development, expose port `8000` through a secure HTTPS tunnel; in Meta's Webhooks settings, use `https://<public-host>/webhook`, enter the same `WHATSAPP_VERIFY_TOKEN`, and subscribe to the WhatsApp `messages` field. The endpoint verifies Meta's challenge and request signature.

Each participant first messages the configured WhatsApp Business number with `/start Their Name`. This links their phone number and opens the reply window. WhatsApp requires a recent inbound message before the app can send free-form follow-ups or escalations; outside that window, an approved message template is needed. See Meta's [WhatsApp Business Platform overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview/) and [webhook security guidance](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/).

## Quick start

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure the Meta values in `.env`, then run:

```sh
python test_engine.py
python check_setup.py
python seed.py "Coordinator Name" "Participant Name" "Unblocker Name"
```

If you are using the existing Supabase project, run [`supabase/whatsapp_migration.sql`](supabase/whatsapp_migration.sql) in its SQL Editor. For a fresh Supabase project, run [`supabase/schema.sql`](supabase/schema.sql). Set `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `APP_PASSWORD` in the server environment. The Supabase secret key must stay server-side; the dashboard requires `APP_PASSWORD` when Supabase is enabled. Leaving both Supabase values blank uses local SQLite.

Start the WhatsApp webhook and dashboard in separate terminals:

```sh
python bot.py
```

```sh
streamlit run dashboard.py --server.address 127.0.0.1
```

Participants can send `/tasks`, `/ask <task_id>`, or `/update <task_id> <reply>` to the WhatsApp Business number. A plain reply is applied only when it maps unambiguously to one assigned open task. The coordinator dashboard shows tasks, blockers, participant updates, WhatsApp links, and follow-ups.

The seeded task starts **Pending**. “The API is connected, but I am waiting for test credentials” becomes **Blocked** with blocker **test credentials**, never Complete. Vague replies remain conservative; the optional LLM can identify a high-confidence blocker, but cannot mark work Complete.

## Dashboard and storage

The Streamlit dashboard supports status counts, blocker-first task ordering, task search and filters, adding participants/tasks, editing owners and unblockers, manual status changes, and activity history. It binds to localhost by default. SQLite stores local data in `coordinator.db`; Supabase is available for hosted persistence.

See [HANDOFF.md](HANDOFF.md) for current state and operating notes.
