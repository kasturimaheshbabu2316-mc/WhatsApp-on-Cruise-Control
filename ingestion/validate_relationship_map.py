#!/usr/bin/env python3
"""Validate that every processed conversation_id has a classified relationship."""

import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
PAIRS_PATH = ROOT_DIR / "data" / "processed_pairs.jsonl"
MAP_PATH = ROOT_DIR / "config" / "contact_relationship_map.json"
PLACEHOLDER = "REPLACE_ME"


def load_conversation_ids(pairs_path: Path) -> list[str]:
    """Read data/processed_pairs.jsonl and collect distinct conversation_ids."""
    if not pairs_path.exists():
        print(f"❌ Error: Processed pairs file not found: {pairs_path}", file=sys.stderr)
        sys.exit(1)

    conversation_ids: set[str] = set()
    with pairs_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                record = json.loads(line_str)
                cid = record.get("conversation_id")
                if cid:
                    conversation_ids.add(cid.strip())
            except json.JSONDecodeError:
                pass
    return sorted(conversation_ids)


def load_relationship_map(map_path: Path) -> dict[str, str]:
    """Load relationship map from config/contact_relationship_map.json."""
    if not map_path.exists():
        print(f"❌ Error: Relationship map file not found: {map_path}", file=sys.stderr)
        print(f"Run 'python ingestion/build_relationship_map.py' first.", file=sys.stderr)
        sys.exit(1)

    try:
        with map_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"❌ Error: {map_path} must be a JSON object mapping conversation_id to relationship.", file=sys.stderr)
                sys.exit(1)
            return data
    except Exception as e:
        print(f"❌ Error: Could not read {map_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    conversation_ids = load_conversation_ids(PAIRS_PATH)
    relationship_map = load_relationship_map(MAP_PATH)

    missing_keys: list[str] = []
    unclassified_keys: list[str] = []

    for cid in conversation_ids:
        if cid not in relationship_map:
            missing_keys.append(cid)
        elif relationship_map[cid] == PLACEHOLDER or not relationship_map[cid].strip():
            unclassified_keys.append(cid)

    if missing_keys or unclassified_keys:
        print("=" * 60, file=sys.stderr)
        print("❌ RELATIONSHIP MAP VALIDATION FAILED", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        if missing_keys:
            print(f"\nMissing from {MAP_PATH.name} ({len(missing_keys)}):", file=sys.stderr)
            for cid in missing_keys:
                print(f"  - {cid}", file=sys.stderr)

        if unclassified_keys:
            print(f"\nStill set to '{PLACEHOLDER}' or empty ({len(unclassified_keys)}):", file=sys.stderr)
            for cid in unclassified_keys:
                print(f"  - {cid}", file=sys.stderr)

        print("\n👉 Please update config/contact_relationship_map.json with valid relationship names before proceeding.", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("✅ RELATIONSHIP MAP VALIDATION PASSED")
    print("=" * 60)
    print(f"Validated {len(conversation_ids)} conversation IDs in '{MAP_PATH}':")
    for cid in conversation_ids:
        print(f"  • {cid} -> {relationship_map[cid]!r}")
    print(f"Default fallback: {relationship_map.get('_default', 'unknown')!r}")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
