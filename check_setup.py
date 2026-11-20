"""Non-secret setup validation. Does not print environment variable values."""
import importlib.util
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
checks = {
    "Python 3.9+": __import__("sys").version_info >= (3, 9),
    "requirements installed": all(importlib.util.find_spec(m) for m in ("streamlit", "dotenv", "openai", "supabase", "fastapi", "uvicorn", "requests")),
    ".env exists": Path(".env").is_file(),
    "LLM_BASE_URL set": bool(os.getenv("LLM_BASE_URL", "").strip()),
    "LLM_MODEL set": bool(os.getenv("LLM_MODEL", "").strip()),
}
llm_key_set = bool(os.getenv("LLM_API_KEY", "").strip())
whatsapp_vars = (
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_APP_SECRET",
)
for var in whatsapp_vars:
    checks[f"{var} set"] = bool(os.getenv(var, "").strip())
supabase_url = os.getenv("SUPABASE_URL", "").strip()
supabase_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
supabase_config_ok = bool(supabase_url) == bool(supabase_key)
checks["Supabase URL/key configured together"] = supabase_config_ok
checks["APP_PASSWORD set for Supabase dashboard"] = not supabase_url or bool(os.getenv("APP_PASSWORD", "").strip())
for label, ok in checks.items():
    print(f"{'OK' if ok else 'MISSING'}  {label}")
print(f"{'OK' if llm_key_set else 'INFO'}  LLM_API_KEY {'set' if llm_key_set else 'not set (optional; rule-based mode is enabled)'}")
print("\nSetup check: " + ("PASS" if all(checks.values()) else "INCOMPLETE"))
raise SystemExit(0 if all(checks.values()) else 1)
