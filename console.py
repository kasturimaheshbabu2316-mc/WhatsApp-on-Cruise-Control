#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Live Console Feed (Root runner).
Re-exports/runs console/app.py logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Run the console/app.py implementation
app_script = ROOT / "console" / "app.py"
with app_script.open("r", encoding="utf-8") as f:
    code = compile(f.read(), str(app_script), "exec")
    exec(code, globals())
