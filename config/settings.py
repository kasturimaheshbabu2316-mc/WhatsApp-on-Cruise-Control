#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Runtime Configuration and Allowlist Enforcement.
Reads configuration from config/settings.json and derives the active allowlist
from config/relationship_map.json.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent
REPO_ROOT = CONFIG_DIR.parent

SETTINGS_PATH = CONFIG_DIR / "settings.json"
RELATIONSHIP_MAP_PATH = CONFIG_DIR / "relationship_map.json"
KILL_SWITCH_PATH = REPO_ROOT / "kill_switch.flag"

DEFAULT_SETTINGS = {
    "dry_run": True,
    "min_delay_seconds": 3,
    "max_delay_seconds": 12,
}


def load_settings() -> dict:
    """
    Read config/settings.json and return settings as a dict.
    Returns safe defaults if the file is missing, empty, or fails to parse.
    Never crashes the caller over a settings file problem.
    """
    # Check primary path (config/settings.json) and fallback to configer/setting.json if needed
    candidates = [
        SETTINGS_PATH,
        REPO_ROOT / "configer" / "setting.json",
    ]

    for path in candidates:
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as settings_file:
                    data = json.load(settings_file)
                    if isinstance(data, dict):
                        # Merge with defaults to guarantee all expected keys exist
                        merged = DEFAULT_SETTINGS.copy()
                        merged.update(data)
                        return merged
            except (OSError, json.JSONDecodeError, TypeError):
                continue

    return DEFAULT_SETTINGS.copy()


def is_dry_run() -> bool:
    """Return whether outgoing replies should remain in dry-run mode (simulation only)."""
    return bool(load_settings().get("dry_run", True))


def is_kill_switch_active() -> bool:
    """Return whether the repository kill-switch flag (kill_switch.flag) exists in the repo root."""
    return KILL_SWITCH_PATH.exists()


def get_allowlist() -> set[str]:
    """
    Read config/relationship_map.json and return a set of all contact identifiers
    whose mapped relationship is NOT 'unknown' and is not the literal '_default' key.
    """
    if not RELATIONSHIP_MAP_PATH.exists():
        return set()

    try:
        with RELATIONSHIP_MAP_PATH.open("r", encoding="utf-8") as map_file:
            relationship_map = json.load(map_file)
    except (OSError, json.JSONDecodeError, TypeError):
        return set()

    if not isinstance(relationship_map, dict):
        return set()

    return {
        str(key).strip()
        for key, relationship in relationship_map.items()
        if str(key).strip() != "_default" and str(relationship).strip().lower() != "unknown"
    }


def enforce_allowlist(jid: str) -> bool:
    """
    Strip the JID suffix (everything before the first '@', matching agent/router.py)
    and return True only if that phone number is present in get_allowlist().
    """
    if not jid or not isinstance(jid, str):
        return False

    normalized = jid.strip()
    if not normalized:
        return False

    number = normalized.split("@", 1)[0]
    return bool(number) and number in get_allowlist()


if __name__ == "__main__":
    print("Settings:", load_settings())
    print("is_dry_run():", is_dry_run())
    print("is_kill_switch_active():", is_kill_switch_active())
    print("Allowlist:", get_allowlist())
