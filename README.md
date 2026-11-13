# Coordinator

A solo-built hackathon project coordinator. Its demo follows the W-PS-1 group-project scenario with a real Telegram bot, real participants, and simulated task data.

## Quick start

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put the Telegram bot token and OpenCode Zen API key in `.env`. Do not share them in chat. Then run:

```sh
python test_engine.py
python check_setup.py
python seed.py "Coordinator Name" "Participant Name" "Unblocker Name"
```

By default, the app stores data in local SQLite (`coordinator.db`). For a hosted deployment, create a Supabase project, run [`supabase/schema.sql`](supabase/schema.sql) in its SQL Editor, then set `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and a strong `APP_PASSWORD` in the server environment. Setting both Supabase values switches storage to Supabase; leaving both blank keeps SQLite. Never put the secret key in browser code or commit it. The dashboard requires `APP_PASSWORD` in Supabase mode because the server key has elevated database access.

Start the bot and dashboard in separate terminals:

```sh
python bot.py
```

```sh
streamlit run dashboard.py --server.address 127.0.0.1
```

Each demo participant links their account with `/start Their Name`. Use `/tasks` to see task IDs, then `/ask <task_id>` to send a real follow-up. They reply in Telegram; the bot interprets the response and records the status change. The assigned unblocker receives an escalation when a task becomes Blocked. The dashboard shows task status, blockers, participants, sent follow-ups, and participant replies. It also lets you add participants and tasks, edit task owners and unblockers, change task status, search/filter tasks, and copy the `/ask <task_id>` command for a Telegram check-in. The dashboard binds to localhost.

The seeded task starts **Pending**. The engine marks “The API is connected, but I am waiting for test credentials” **Blocked** with blocker **test credentials**. After the participant receives credentials, finishes testing, and replies that the task is complete, the bot marks it **Complete**. Rule-based classification works when the LLM key is absent; the optional model only helps detect blockers in ambiguous replies and cannot mark tasks Complete.

See [HANDOFF.md](HANDOFF.md) for project rules and current implementation notes.

## Build sequence

This is being built solo in phases: backend, functional frontend, UI/UX refinement, then remaining improvements. The dashboard now has a first visual pass, status colors, search, filters, and blocker-first task ordering. Further polish can follow the first live demo.
