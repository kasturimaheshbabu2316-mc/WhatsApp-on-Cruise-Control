#!/usr/bin/env python3
"""Validate relationship-map entries for WhatsApp-style number keys."""

import json
import re
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT_DIR / "config" / "relationship_map.json"
FALLBACK_MAP_PATH = Path("config/relationship_map.json")
VALID_RELATIONSHIPS = {"family", "friend", "professional", "unknown"}


def load_map() -> dict:
    target_path = MAP_PATH if MAP_PATH.exists() else FALLBACK_MAP_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Relationship map not found at {MAP_PATH} or {FALLBACK_MAP_PATH}")

    with target_path.open("r", encoding="utf-8") as map_file:
        data = json.load(map_file)
    if not isinstance(data, dict):
        raise ValueError(f"{target_path} must contain a JSON object at the top level")
    return data


def key_looks_like_contact_copy_paste(key: str) -> bool:
    """Flag any key containing +, spaces, dashes, or letters."""
    return bool(re.search(r"[+\s\-A-Za-z]", key))


def digit_length_looks_implausible(key: str) -> bool:
    """Flag any key whose digit length is fewer than 8 or more than 15 digits."""
    digits = re.sub(r"\D", "", key)
    return len(digits) < 8 or len(digits) > 15


def main() -> int:
    issues: list[str] = []

    try:
        relationship_map = load_map()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: unable to load relationship map: {exc}", file=sys.stderr)
        return 1

    default_value = relationship_map.get("_default")
    if "_default" not in relationship_map:
        issues.append('Missing required key "_default"')
    elif default_value not in VALID_RELATIONSHIPS:
        issues.append(
            f'Invalid "_default" value: {default_value!r}; expected one of {sorted(VALID_RELATIONSHIPS)}'
        )

    for key, value in sorted(relationship_map.items()):
        if key == "_default":
            continue

        if key_looks_like_contact_copy_paste(key):
            issues.append(
                f"Key {key!r} looks like a copy-paste/contact-format mistake: contains +, spaces, dashes, or letters"
            )

        if digit_length_looks_implausible(key):
            digits_only = re.sub(r"\D", "", key)
            issues.append(
                f"Key {key!r} has implausible digit length ({len(digits_only)} digits)"
            )

        if value is None:
            issues.append(f"Key {key!r} has a null value; expected a relationship string")
        elif not isinstance(value, str):
            issues.append(f"Key {key!r} has a non-string value: {value!r}")
        elif value not in VALID_RELATIONSHIPS and value != "group":
            issues.append(
                f"Key {key!r} has unexpected relationship value: {value!r}; expected one of {sorted(VALID_RELATIONSHIPS)}"
            )

    print("=" * 60)
    print("RELATIONSHIP MAP PRE-FLIGHT VALIDATION")
    print("=" * 60)
    print(f"Target file:            {MAP_PATH}")
    print(f"Total entries checked:  {len(relationship_map)}")

    if issues:
        print("\n❌ FAIL: Relationship map validation issues found:")
        for issue in issues:
            print(f"  • {issue}")
        print("=" * 60)
        return 1

    print("\n✅ PASS: Relationship map looks valid.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
