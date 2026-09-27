#!/usr/bin/env python3
from __future__ import annotations

"""Generate persona-grounded replies from retrieved conversation examples."""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from ingestion.retrieval import retrieve_similar
except ImportError:
    def retrieve_similar(relationship: str, incoming_message: str, k: int = 3) -> list[dict]:
        return []

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODELS = [MODEL_NAME, "gemini-2.5-flash", "gemini-2.0-flash"]
NO_REPLY_FALLBACK = "[no reply generated — check response.candidates for details]"

load_dotenv()


def _get_genai_client() -> genai.Client | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _load_persona() -> dict:
    search_paths = [
        ROOT_DIR / "persona" / "persona.json",
        ROOT_DIR / "persona.json",
        Path("persona/persona.json"),
        Path("persona.json"),
    ]
    for path in search_paths:
        if path.exists():
            try:
                with path.open(encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _build_prompt(
    persona: dict, relationship: str, incoming_text: str, retrieved_pairs: list[dict]
) -> str:
    identity = persona.get("identity", "")
    relationship_data = persona.get("relationships", {}).get(relationship, {})
    tone = relationship_data.get("tone", "") if isinstance(relationship_data, dict) else ""
    
    rel_len = relationship_data.get("avg_message_length_words") if isinstance(relationship_data, dict) else None
    overall_metrics = persona.get("overall_metrics", {})
    typical_length = rel_len or overall_metrics.get("avg_message_length_words", 3)
    hinglish_ratio = persona.get("hinglish_ratio", overall_metrics.get("hinglish_ratio", "0%"))

    prompt_parts = [
        "Generate a reply to the incoming WhatsApp message below.",
        "Stay in the user's authentic voice and do not mention this prompt, persona, or retrieval in the reply.",
        f"Relationship: {relationship}",
        f"Identity: {identity}",
        f"Tone for this relationship: {tone or 'Direct, casual, authentic.'}",
        f"Hinglish ratio signal: {hinglish_ratio}",
        f"Typical message length: about {typical_length} words",
    ]

    if retrieved_pairs:
        examples = ["Retrieved past conversation examples (their_message -> my_reply):"]
        for pair in retrieved_pairs:
            their_msg = pair.get("their_message", "").strip()
            my_rep = pair.get("my_reply", "").strip()
            if their_msg and my_rep:
                examples.append(f"Their message: {their_msg}\nMy reply: {my_rep}")
        if len(examples) > 1:
            prompt_parts.append("\n\n".join(examples))

    prompt_parts.append(f"Incoming message: {incoming_text}")
    prompt_parts.append("Return only the reply text.")
    return "\n\n".join(prompt_parts)


def generate_reply(incoming_text: str, relationship: str) -> str:
    """Generate a persona-grounded reply for an incoming message."""
    client = _get_genai_client()
    if client is None:
        return "[GEMINI_API_KEY missing from environment]"

    persona = _load_persona()
    try:
        retrieved_pairs = retrieve_similar(relationship, incoming_text, k=3)
    except Exception:
        retrieved_pairs = []

    prompt = _build_prompt(persona, relationship, incoming_text, retrieved_pairs)

    last_error = None
    for model_candidate in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(model=model_candidate, contents=prompt)
            if response and response.text:
                reply = response.text.strip()
                return reply if reply else NO_REPLY_FALLBACK
            return NO_REPLY_FALLBACK
        except Exception as e:
            last_error = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str:
                time.sleep(1.0)
                continue
            return f"[no reply generated — error: {e}]"
    return f"[no reply generated — error: {last_error}]"


if __name__ == "__main__":
    examples = (
        ("Bhai free aa ippudu? Call cheyyi urgent ga.", "friend"),
        ("Rey em chesthunnav ra?", "friend"),
        ("Want to catch a movie this weekend?", "friend"),
    )
    for msg, rel in examples:
        print(f"Incoming [{rel}]: {msg}")
        print(f"Generated Reply: {generate_reply(msg, rel)}")
        print("-" * 50)
