#!/usr/bin/env python3
"""Build or update the conversation_id to relationship category map."""

import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
PAIRS_PATH = ROOT_DIR / "data" / "processed_pairs.jsonl"
MAP_PATH = ROOT_DIR / "config" / "contact_relationship_map.json"
FALLBACK_ROOT_MAP_PATH = ROOT_DIR / "contact_relationship_map.json"
PLACEHOLDER = "REPLACE_ME"
DEFAULT_KEY = "_default"
DEFAULT_VALUE = "unknown"


def load_conversation_ids(pairs_path: Path) -> list[str]:
    """Read data/processed_pairs.jsonl and collect distinct conversation_ids sorted alphabetically."""
    if not pairs_path.exists():
        print(f"Warning: Pairs file not found at {pairs_path}", file=sys.stderr)
        return []

    conversation_ids: set[str] = set()
    with pairs_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                record = json.loads(line_str)
                cid = record.get("conversation_id")
                if cid:
                    conversation_ids.add(cid.strip())
            except json.JSONDecodeError as e:
                print(f"Warning: Line {line_num} in {pairs_path.name} is invalid JSON: {e}", file=sys.stderr)

    return sorted(conversation_ids)


def load_existing_map(map_path: Path) -> dict[str, str]:
    """Load existing contact_relationship_map.json without removing existing manual classifications."""
    target = map_path
    if not target.exists() and FALLBACK_ROOT_MAP_PATH.exists():
        target = FALLBACK_ROOT_MAP_PATH

    if not target.exists():
        return {}

    try:
        with target.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            print(f"Warning: {target} did not contain a JSON object. Starting fresh.", file=sys.stderr)
            return {}
    except Exception as e:
        print(f"Warning: Could not read existing map {target}: {e}", file=sys.stderr)
        return {}


def main() -> None:
    conversation_ids = load_conversation_ids(PAIRS_PATH)
    relationship_map = load_existing_map(MAP_PATH)

    new_ids: list[str] = []
    for cid in conversation_ids:
        if cid not in relationship_map:
            relationship_map[cid] = PLACEHOLDER
            new_ids.append(cid)

    # Always ensure "_default": "unknown" exists
    relationship_map.setdefault(DEFAULT_KEY, DEFAULT_VALUE)

    # Sort alphabetically by key
    sorted_map = dict(sorted(relationship_map.items(), key=lambda item: item[0]))

    # Save to config/contact_relationship_map.json with 2-space indentation
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MAP_PATH.open("w", encoding="utf-8") as f:
        json.dump(sorted_map, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Find keys that still have REPLACE_ME
    placeholders = [
        k for k, v in sorted_map.items() if v == PLACEHOLDER
    ]

    # Print summary
    print("=" * 60)
    print("CONTACT RELATIONSHIP MAP SUMMARY")
    print("=" * 60)
    print(f"Processed pairs file:             {PAIRS_PATH}")
    print(f"Relationship map file:            {MAP_PATH}")
    print(f"Total distinct conversation_ids:  {len(conversation_ids)}")
    print(f"New conversation_ids added:       {len(new_ids)}")
    if new_ids:
        for nid in new_ids:
            print(f"  + Added: {nid!r} -> {PLACEHOLDER!r}")
    
    print("-" * 60)
    print(f"Entries requiring manual classification ({len(placeholders)} remaining):")
    if placeholders:
        for cid in placeholders:
            print(f"  - {cid}: {PLACEHOLDER}")
        print(f"\n👉 Please edit '{MAP_PATH}' and replace '{PLACEHOLDER}' with the relationship name (e.g., 'friend', 'group', 'family', 'wife', 'professional').")
    else:
        print("  ✅ All conversation_ids are classified!")
    print("=" * 60)


if __name__ == "__main__":
    main()
