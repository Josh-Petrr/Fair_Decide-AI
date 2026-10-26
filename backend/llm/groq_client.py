"""Thin Groq client (OpenAI-compatible REST). Returns None on any failure so callers fall back gracefully."""
import json
import logging
import re

import httpx

from ..config import GROQ_API_KEY, LLM_RUNTIME

URL = "https://api.groq.com/openai/v1/chat/completions"
log = logging.getLogger("fairdecide.llm")
THINK = re.compile(r"<think>.*?</think>", re.S)


def available() -> bool:
    return LLM_RUNTIME == "groq" and bool(GROQ_API_KEY)


def _post(body):
    r = httpx.post(URL, json=body, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def chat(model, system, user, json_mode=False, temperature=0.2, max_tokens=900):
    if not available():
        return None
    body = dict(model=model, temperature=temperature, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if "qwen" in model:
        body["reasoning_format"] = "hidden"          # reasoning models: return only the final answer
    try:
        try:
            text = _post(body)
        except httpx.HTTPStatusError as e:           # model may not accept an optional parameter - retry plain
            if e.response.status_code != 400 or "reasoning_format" not in body:
                raise
            body.pop("reasoning_format")
            text = _post(body)
        text = THINK.sub("", text).strip()
        if json_mode:
            text = text[text.find("{"): text.rfind("}") + 1]
            return json.loads(text)
        return text
    except Exception as exc:
        log.warning("Groq call failed (%s) - using rule-based fallback", type(exc).__name__)
        return None
