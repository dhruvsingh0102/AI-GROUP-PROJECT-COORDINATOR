"""Optional LLM assist: it may identify a blocker, but cannot mark work complete."""
import json
import os
from openai import OpenAI


def extract_blocker(message: str) -> str | None:
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        return None
    client = OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL", "https://opencode.ai/inference/openai/v1"))
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "mimo-v2.6-flash-free"),
        temperature=0,
        messages=[
            {"role": "system", "content": "Identify only an explicit external dependency that prevents progress. A statement that work is connected/started is not completion. Never infer completion. Return JSON {\"blocked\": boolean, \"blocker\": string, \"confidence\": number}. For vague or completed replies use blocked=false."},
            {"role": "user", "content": message},
        ],
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content or "{}")
        blocker = str(data.get("blocker", "")).strip()
        if data.get("blocked") is True and float(data.get("confidence", 0)) >= 0.9 and blocker:
            return blocker[:100]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    return None
