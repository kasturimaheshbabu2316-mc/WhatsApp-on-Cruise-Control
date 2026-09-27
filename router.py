#!/usr/bin/env python3
from __future__ import annotations

"""Resolve a WhatsApp JID to its relationship and Chroma collection."""

import json
from pathlib import Path


def resolve_relationship(
    jid: str, map_path: str = "config/relationship_map.json"
) -> tuple[str, str | None]:
    """Resolve a WhatsApp number or group JID to its relationship and collection."""
    if not jid or not isinstance(jid, str):
        return ("unknown", "history_unknown")

    normalized = jid.strip()
    if not normalized:
        return ("unknown", "history_unknown")

    # If jid ends with "@g.us", immediately return ("group", None)
    if normalized.endswith("@g.us"):
        return ("group", None)

    # Strip everything from '@' onward (handles both @s.whatsapp.net and @lid)
    number = normalized.split("@", 1)[0]
    if not number:
        return ("unknown", "history_unknown")

    relationship_map_path = Path(map_path)
    relationship_map: dict[str, str] = {}
    if relationship_map_path.exists():
        try:
            with relationship_map_path.open("r", encoding="utf-8") as map_file:
                data = json.load(map_file)
                if isinstance(data, dict):
                    relationship_map = data
        except Exception:
            relationship_map = {}

    relationship = relationship_map.get(number)
    if relationship is None:
        relationship = relationship_map.get("_default", "unknown") or "unknown"

    if relationship == "group":
        return ("group", None)

    collection_name = f"history_{relationship}"
    return (relationship, collection_name)
