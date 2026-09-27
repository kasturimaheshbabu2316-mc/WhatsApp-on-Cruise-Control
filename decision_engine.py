#!/usr/bin/env python3
"""Root decision_engine module - re-exports from agent.decision_engine."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.decision_engine import DecisionResult, should_reply

__all__ = ["DecisionResult", "should_reply"]

if __name__ == "__main__":
    msg = {"message_type": "image", "text": "", "from_me": False}
    result = should_reply(msg, "friend")
    print(f"friend media ack: should_reply={result.should_reply}, reason={result.reason}, reply={result.reply}")
    result_unknown = should_reply(msg, "unknown")
    print(f"unknown media ack: should_reply={result_unknown.should_reply}, reason={result_unknown.reason}")
