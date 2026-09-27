#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Root Bridge Module.
Re-exports the Flask app and endpoints from agent.bridge for backward-compatible
execution from both root (`python bridge.py`) and agent (`python agent/bridge.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.bridge import app, health_check, process_message

__all__ = ["app", "health_check", "process_message"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
