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

Start the bot and dashboard in separate terminals:

```sh
python bot.py
```

```sh
streamlit run dashboard.py
```

Each demo participant links their account with `/start Their Name`. Use `/tasks` to see task IDs, then `/ask <task_id>` to send a real follow-up. They reply in Telegram; the bot interprets the response and records the status change. The assigned unblocker receives an escalation when a task becomes Blocked. The dashboard shows task status, blockers, participants, sent follow-ups, and participant replies; it also lets you add participants and tasks or manually change task status.

The seeded task starts **Pending**. The engine marks “The API is connected, but I am waiting for test credentials” **Blocked** with blocker **test credentials**. After the participant receives credentials, finishes testing, and replies that the task is complete, the bot marks it **Complete**. Rule-based classification works when the LLM key is absent; the optional model only helps detect blockers in ambiguous replies and cannot mark tasks Complete.

See [HANDOFF.md](HANDOFF.md) for project rules and current implementation notes.

## Build sequence

This is being built solo in phases: backend, functional frontend, UI/UX refinement, then remaining improvements. The dashboard now has a first visual pass, status colors, search, filters, and blocker-first task ordering. Further polish can follow the first live demo.
