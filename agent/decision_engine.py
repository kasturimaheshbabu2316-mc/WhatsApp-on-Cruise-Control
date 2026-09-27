#!/usr/bin/env python3
"""Layered reply-or-ignore decision engine."""

from __future__ import annotations

import dis
import inspect
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
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
_CANDIDATES = [
    MODEL_NAME,
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]
FALLBACK_MODELS = list(dict.fromkeys(_CANDIDATES))
DECISION_LOG_PATH = Path("logs/decision_log.jsonl")
EXPECTED_LABELS = {"safe_to_auto_reply", "needs_human_money_or_serious"}


class DecisionResult(tuple):
    """Result tuple supporting both 2-tuple (should_reply, reason) and 3-tuple (should_reply, reason, reply) unpacking."""

    def __new__(cls, should_reply: bool, reason: str, reply: str | None = None):
        return super().__new__(cls, (should_reply, reason, reply))

    def __init__(self, should_reply: bool, reason: str, reply: str | None = None):
        self.should_reply = should_reply
        self.reason = reason
        self.reply = reply

    def __iter__(self):
        try:
            frame = inspect.currentframe().f_back
            code = frame.f_code
            lasti = frame.f_lasti
            instructions = list(dis.get_instructions(code))
            for i, inst in enumerate(instructions):
                if inst.offset == lasti or (
                    inst.offset < lasti and i + 1 < len(instructions) and instructions[i + 1].offset > lasti
                ):
                    for next_inst in instructions[i : i + 4]:
                        if next_inst.opname == "UNPACK_SEQUENCE":
                            if next_inst.argval == 2:
                                return iter((self[0], self[1]))
                            elif next_inst.argval == 3:
                                return iter((self[0], self[1], self[2]))
        except Exception:
            pass
        return super().__iter__()


def _log_decision(
    message_text: str,
    relationship: str,
    decision: str,
    reason: str,
    raw_response: str | None = None,
    reply: str | None = None,
) -> None:
    os.makedirs("logs", exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message_text,
        "relationship": relationship,
        "decision": decision,
        "reason": reason,
    }
    if reply is not None:
        entry["reply"] = reply
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
    reply: str | None = None,
) -> DecisionResult:
    _log_decision(
        message_text,
        relationship,
        "reply" if should_reply else "ignore",
        reason,
        raw_response,
        reply,
    )
    return DecisionResult(should_reply, reason, reply)


def _classify_with_llm(text: str) -> tuple[str, str | None]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "needs_human_money_or_serious", "Missing GEMINI_API_KEY"

    client = genai.Client(api_key=api_key)
    prompt = (
        "Classify the following incoming message as exactly one label: "
        "safe_to_auto_reply or needs_human_money_or_serious.\n"
        "Guidelines:\n"
        "- Friendly banter, greetings, informal questions, casual check-ins, "
        "and multilingual/Indian regional slang (Telugu e.g. 'cheppu', 'enti', 'ela unnav', Hindi e.g. 'kya hal', etc.) "
        "are completely SAFE to auto-reply (label: safe_to_auto_reply).\n"
        "- Only label as needs_human_money_or_serious if the sender explicitly asks for money, bank details, payments, "
        "loans, medical emergencies, legal contracts, or acute crisis.\n"
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
                time.sleep(0.5)
            continue
    else:
        return "needs_human_money_or_serious", f"LLM error: {last_error}"

    if raw_response in EXPECTED_LABELS:
        return raw_response, None
    return "needs_human_money_or_serious", raw_response


def should_reply(message: dict, relationship: str) -> DecisionResult:
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
    # Media-only rule (pure rule-based contextual ack, no LLM call)
    message_type = str(message.get("message_type", "")).strip().lower()
    if message_type in ("image", "audio", "video") and not text.strip():
        if relationship in ("group", "unknown"):
            return _finish(text, relationship, False, f"media-only from {relationship}, ignored")
        media_label = "voice note" if message_type == "audio" else message_type
        media_reply = f"Got your {media_label}, will look at it properly and get back to you 🙂"
        return _finish(text, relationship, True, "media_ack", reply=media_reply)

    if message.get("is_forwarded") is True:
        return _finish(text, relationship, False, "forwarded content, not a real question")

    normalized_text = text.strip().lower().translate(
        str.maketrans("", "", string.punctuation)
    )
    if normalized_text in ONE_WORD_ACKS:
        return _finish(text, relationship, False, "low-signal ack, no reply needed")

    # INTENT CHECK (the one LLM call, via google-genai / gemini-3.8-flash)
    label, raw_response = _classify_with_llm(text)
    if label == "safe_to_auto_reply":
        return _finish(text, relationship, True, "passed all gates")

    reason = "needs human review: money or serious/ambiguous intent"
    if raw_response is not None:
        reason = "intent check failed closed"
    return _finish(text, relationship, False, reason, raw_response)
