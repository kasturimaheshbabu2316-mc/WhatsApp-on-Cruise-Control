#!/usr/bin/env python3
"""Layered reply-or-ignore decision engine."""

from __future__ import annotations

import json
import os
import string
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai

try:
    from config.constants import ONE_WORD_ACKS
except ImportError:
    try:
        from constants import ONE_WORD_ACKS
    except ImportError:
        ONE_WORD_ACKS = {
            "ok",
            "okay",
            "k",
            "kk",
            "haan",
            "hmm",
            "thanks",
            "thank you",
            "cool",
            "nice",
        }

load_dotenv()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS = [MODEL_NAME, "gemini-2.0-flash", "gemini-1.5-flash"]
DECISION_LOG_PATH = Path("logs/decision_log.jsonl")
EXPECTED_LABELS = {"safe_to_auto_reply", "needs_human_money_or_serious"}


def _log_decision(
    message_text: str,
    relationship: str,
    decision: str,
    reason: str,
    raw_response: str | None = None,
) -> None:
    os.makedirs("logs", exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message_text,
        "relationship": relationship,
        "decision": decision,
        "reason": reason,
    }
    if raw_response is not None:
        entry["raw_response"] = raw_response
    with DECISION_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _finish(
    message_text: str,
    relationship: str,
    should_reply: bool,
    reason: str,
    raw_response: str | None = None,
) -> tuple[bool, str]:
    _log_decision(
        message_text,
        relationship,
        "reply" if should_reply else "ignore",
        reason,
        raw_response,
    )
    return should_reply, reason


def _classify_with_llm(text: str) -> tuple[str, str | None]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "needs_human_money_or_serious", "Missing GEMINI_API_KEY"

    client = genai.Client(api_key=api_key)
    prompt = (
        "Classify the following incoming message as exactly one label: "
        "safe_to_auto_reply or needs_human_money_or_serious.\n"
        "Use needs_human_money_or_serious for anything involving money, payments, "
        "loans, medical, legal, serious personal matters, or genuine ambiguity.\n"
        "Return exactly one label and no other text.\n\n"
        f"Message: {text}"
    )
    raw_response = ""
    last_error = None
    for model_candidate in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(model=model_candidate, contents=prompt)
            raw_response = (response.text or "").strip()
            if raw_response:
                break
        except Exception as error:
            last_error = error
            err_str = str(error)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str:
                time.sleep(1.0)
                continue
            return "needs_human_money_or_serious", f"LLM error: {error}"
    else:
        return "needs_human_money_or_serious", f"LLM error: {last_error}"

    if raw_response in EXPECTED_LABELS:
        return raw_response, None
    return "needs_human_money_or_serious", raw_response


def should_reply(message: dict, relationship: str) -> tuple[bool, str]:
    """Apply cheap safety gates before making one guarded intent-classification call."""
    text = message.get("text", "")
    if not isinstance(text, str):
        text = ""

    # HARD RULES (instant, no LLM call)
    if message.get("from_me") is True:
        return _finish(text, relationship, False, "own message")
    if relationship == "group":
        return _finish(text, relationship, False, "group chat, not allowlisted")
    if relationship == "unknown":
        return _finish(text, relationship, False, "sender not in allowlist")

    # SIGNAL RULES (still no LLM call)
    # Session 4.1 will upgrade this specific case into a rule-based contextual ack instead of a plain ignore, but for now, ignore is correct and expected.
    message_type = message.get("message_type", "")
    if message_type in ("image", "audio", "video") and not text.strip():
        return _finish(text, relationship, False, "media-only, no text to ground a reply")
    if message.get("is_forwarded") is True:
        return _finish(text, relationship, False, "forwarded content, not a real question")

    normalized_text = text.strip().lower().translate(
        str.maketrans("", "", string.punctuation)
    )
    if normalized_text in ONE_WORD_ACKS:
        return _finish(text, relationship, False, "low-signal ack, no reply needed")

    # INTENT CHECK (the one LLM call, via google-genai / gemini-3.5-flash)
    label, raw_response = _classify_with_llm(text)
    if label == "safe_to_auto_reply":
        return _finish(text, relationship, True, "passed all gates")

    reason = "needs human review: money or serious/ambiguous intent"
    if raw_response is not None:
        reason = "intent check failed closed"
    return _finish(text, relationship, False, reason, raw_response)
