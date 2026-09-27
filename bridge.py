#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Flask Bridge API.
Receives incoming WhatsApp messages from the Baileys client, runs the Two-Brain pipeline
(Router -> Safety Decision Engine -> RAG Retrieval -> Persona Generation),
logs decisions to logs/console_feed.jsonl, and returns the response payload.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

REPO_ROOT = Path(__file__).resolve().parent
if (REPO_ROOT.parent / "agent").exists() and not (REPO_ROOT / "agent").exists():
    REPO_ROOT = REPO_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.decision_engine import should_reply
from agent.generator import generate_reply
from agent.router import resolve_relationship
from ingestion.retrieval import retrieve_similar

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
    Main webhook invoked by Baileys WhatsApp client when an incoming message is received.
    Executes the full pipeline:
      1. Router: resolve contact relationship
      2. Decision Engine: check safety gates & rules
      3. RAG Retrieval: fetch past dialogue context from ChromaDB
      4. Persona Generator: synthesize in-character reply
      5. Audit: record trace to logs/console_feed.jsonl
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    jid = str(payload.get("jid", ""))
    text = str(payload.get("text", ""))
    message_type = payload.get("message_type", "text")
    is_forwarded = bool(payload.get("is_forwarded", False))
    from_me = bool(payload.get("from_me", False))

    relationship, _ = resolve_relationship(jid)
    message_dict = {
        "jid": jid,
        "text": text,
        "message_type": message_type,
        "is_forwarded": is_forwarded,
        "from_me": from_me,
    }

    decision, reason = should_reply(message_dict, relationship)

    retrieval_trace = []
    if relationship not in {"group", "unknown"}:
        try:
            retrieval_trace = retrieve_similar(relationship, text or "", k=3)
        except Exception as exc:  # defensive logging path
            retrieval_trace = [{"error": str(exc)}]

    reply = None
    if decision:
        try:
            reply = generate_reply(text, relationship)
        except Exception as exc:  # defensive generation path
            reply = None
            reason = f"{reason}; generation error: {exc}"

    response = {
        "should_reply": bool(decision),
        "reply": reply,
        "relationship": relationship,
        "reason": reason,
    }

    _ensure_log_dir()
    with CONSOLE_FEED_PATH.open("a", encoding="utf-8") as log_file:
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
        log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
