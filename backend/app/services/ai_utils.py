import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings


def _extract_json_object(text: str) -> dict[str, Any] | None:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = value.find("{")
    end = value.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(value[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


async def ask_openai_json(prompt: str) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=prompt,
        )
    except Exception:
        # External AI failures must not take down resume upload, scans, matching,
        # or application preparation. Callers always have deterministic fallbacks.
        return None
    return _extract_json_object(response.output_text)


def clean_string_list(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text.lower() not in {entry.lower() for entry in result}:
            result.append(text)
        if len(result) >= limit:
            break
    return result
