#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Flask Bridge API (agent/bridge.py).
Receives incoming WhatsApp messages from the Baileys client, runs the Two-Brain pipeline:
  1. Router: resolve contact relationship
  2. Decision Engine: check safety gates & rules
  3. Persona Generator: synthesize in-character reply (if should_reply is True)
  4. Console Feed Logger: append structured log entry to logs/console_feed.jsonl
  5. Response Dispatch: return response payload
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Also ensure agent directory is on sys.path
AGENT_DIR = Path(__file__).resolve().parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

try:
    from agent.router import resolve_relationship
    from agent.decision_engine import should_reply
    from agent.generator import generate_reply
except ImportError:
    from router import resolve_relationship
    from decision_engine import should_reply
    from generator import generate_reply

try:
    from ingestion.retrieval import retrieve_similar
except ImportError:
    def retrieve_similar(relationship: str, incoming_message: str, k: int = 3) -> list[dict]:
        return []

app = Flask(__name__)

LOGS_DIR = REPO_ROOT / "logs"
CONSOLE_FEED_PATH = LOGS_DIR / "console_feed.jsonl"


def _ensure_log_dir() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
@app.get("/health")
def health_check():
    """Health check endpoint to verify bridge readiness."""
    return jsonify({
        "status": "healthy",
        "service": "WhatsApp Cruise Control Flask Bridge",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.post("/process")
def process_message():
    """
    POST /process
    Accepts JSON with keys: jid, text, message_type, is_forwarded, from_me.
    Executes:
      1. resolve_relationship(jid) from agent/router.py
      2. should_reply(message_dict, relationship) from agent/decision_engine.py
      3. generate_reply(text, relationship) from agent/generator.py (if should_reply is True)
      4. retrieve_similar(relationship, text) for display / logging trace
      5. appends audit record to logs/console_feed.jsonl
    Returns:
      {should_reply: bool, reply: str or null, relationship: str, reason: str}
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    jid = str(payload.get("jid", ""))
    text = str(payload.get("text", ""))
    message_type = payload.get("message_type", "text")
    is_forwarded = bool(payload.get("is_forwarded", False))
    from_me = bool(payload.get("from_me", False))

    # 1. Call resolve_relationship(jid) from agent/router.py
    rel_result = resolve_relationship(jid)
    if isinstance(rel_result, (tuple, list)):
        relationship = str(rel_result[0])
    else:
        relationship = str(rel_result)

    # 2. Call should_reply(message_dict, relationship) from agent/decision_engine.py
    message_dict = {
        "jid": jid,
        "text": text,
        "message_type": message_type,
        "is_forwarded": is_forwarded,
        "from_me": from_me,
    }

    decision_res = should_reply(message_dict, relationship)
    if isinstance(decision_res, (tuple, list)):
        decision = bool(decision_res[0])
        reason = str(decision_res[1])
    else:
        decision = bool(decision_res)
        reason = "passed all gates" if decision else "ignored"

    # 3. If should_reply is True, call generate_reply(text, relationship) from agent/generator.py
    reply = None
    if decision:
        try:
            reply = generate_reply(text, relationship)
        except Exception as exc:
            reply = None
            reason = f"{reason}; generation error: {exc}"

    # 4. Purely for logging/display purposes in the console, call retrieve_similar directly
    retrieval_trace = []
    try:
        if text and text.strip() and relationship not in {"group", "unknown"}:
            retrieval_trace = retrieve_similar(relationship, text, k=3)
    except Exception as exc:
        retrieval_trace = [{"error": str(exc)}]

    # 5. Regardless of the outcome, append one line to logs/console_feed.jsonl
    _ensure_log_dir()
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "jid": jid,
        "text": text,
        "relationship": relationship,
        "decision": "reply" if decision else "ignore",
        "reason": reason,
        "reply": reply,
        "retrieval_trace": retrieval_trace,
    }
    with CONSOLE_FEED_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # 6. Return JSON response
    response_payload = {
        "should_reply": decision,
        "reply": reply,
        "relationship": relationship,
        "reason": reason,
    }
    return jsonify(response_payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
