#!/usr/bin/env python3
"""Root settings module - re-exports from config.settings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import (
    DEFAULT_SETTINGS,
    enforce_allowlist,
    get_allowlist,
    is_dry_run,
    is_kill_switch_active,
    load_settings,
)

__all__ = [
    "DEFAULT_SETTINGS",
    "load_settings",
    "is_dry_run",
    "is_kill_switch_active",
    "get_allowlist",
    "enforce_allowlist",
]

if __name__ == "__main__":
    print("Settings from root:", load_settings())
    print("is_dry_run():", is_dry_run())
    print("is_kill_switch_active():", is_kill_switch_active())
    print("Allowlist:", get_allowlist())
