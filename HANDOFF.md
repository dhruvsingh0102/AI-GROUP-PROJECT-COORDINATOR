# Coordinator project handoff

## Goal
Build W-PS-1, AI Group Project Coordinator. Dhruv is building the project solo; the demo itself coordinates a small simulated project with real Telegram participants. The required loop is task → Telegram follow-up → participant reply → task-status update. “The API is connected, but I am waiting for test credentials” must result in **Blocked** with blocker **test credentials**, never Complete. A Blocked task should notify its designated unblocker when they have linked Telegram.

## Rules
- Keep task status classification conservative. Do not lower confidence thresholds to make tests pass.
- Blocker evidence takes precedence over completion language.
- Ambiguous replies remain Needs Clarification (or In Progress if they clearly say work is underway).
- Multi-task messages must not silently apply to the wrong task.
- Keep bot and LLM secrets in `.env`; never print their values or commit `.env`.
- The optional OpenCode Zen model may identify a blocker but cannot mark a task Complete.

## Current state
- Implemented: `engine.py`, `storage.py`, `bot.py`, `dashboard.py`, `seed.py`, `check_setup.py`, `test_engine.py`, and `llm.py`.
- Functional Streamlit dashboard displays status counts, task details, blockers, participant updates, Telegram follow-ups, and participant Telegram-link state. It supports adding participants/tasks and manually changing task statuses.
- Build sequence: backend and functional frontend are in place; visual UI/UX refinement is next.
- SQLite stores seeded people, tasks, and update history in `coordinator.db`.
- Seeded demo task starts Pending and is assigned to the second seeded participant; the third participant is the designated unblocker.
- Every demo participant links Telegram with `/start <seeded name>`. Telegram bots cannot message a user before that user has started the bot.
- Model default: `mimo-v2.6-flash-free`, OpenCode OpenAI-compatible endpoint `https://opencode.ai/inference/openai/v1`.

## Setup and run
1. `python3 -m venv .venv`
2. Activate it, then `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`; fill in `TELEGRAM_BOT_TOKEN` and `LLM_API_KEY` locally.
4. `python test_engine.py` and `python check_setup.py`.
5. `python seed.py <coordinator> <participant> <unblocker>`.
6. In separate terminals run `python bot.py` and `streamlit run dashboard.py`.
7. Each person starts the bot with `/start <their name>`. The coordinator sends `/ask <task_id>`. The participant replies: `The API is connected, but I am waiting for test credentials.` Expect Blocked / test credentials and a Telegram escalation to the unblocker.

## Known limits / next steps
- Use `/update <task_id> <reply>` to target a task explicitly when multiple tasks are open.
- Dashboard changes are manual; dashboard edits do not generate a Telegram escalation.
- The LLM fallback is used only on ambiguous text and only to infer a high-confidence blocker. Rule-based test scenario works without a key.
- Verify Telegram and Zen credentials with the user present. Do not request secrets in chat; have them put them in `.env`.
