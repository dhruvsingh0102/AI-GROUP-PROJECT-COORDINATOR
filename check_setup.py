"""Non-secret setup validation. Does not print environment variable values."""
import importlib.util
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
checks = {
    "Python 3.9+": __import__("sys").version_info >= (3, 9),
    "requirements installed": all(importlib.util.find_spec(m) for m in ("telegram", "streamlit", "dotenv", "openai")),
    ".env exists": Path(".env").is_file(),
    "TELEGRAM_BOT_TOKEN set": bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip()),
    "LLM_API_KEY set": bool(os.getenv("LLM_API_KEY", "").strip()),
    "LLM_BASE_URL set": bool(os.getenv("LLM_BASE_URL", "").strip()),
    "LLM_MODEL set": bool(os.getenv("LLM_MODEL", "").strip()),
}
for label, ok in checks.items():
    print(f"{'OK' if ok else 'MISSING'}  {label}")
print("\nSetup check: " + ("PASS" if all(checks.values()) else "INCOMPLETE"))
raise SystemExit(0 if all(checks.values()) else 1)
