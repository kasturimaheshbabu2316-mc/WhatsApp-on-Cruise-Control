import json

import pytest

from agent.router import resolve_relationship


@pytest.fixture
def temp_map(tmp_path):
    map_path = tmp_path / "relationship_map.json"
    map_data = {
        "_default": "unknown",
        "919812345670": "friend",
        "144443332255": "friend",
    }
    map_path.write_text(json.dumps(map_data), encoding="utf-8")
    return str(map_path)


def test_known_number_resolves_correctly(temp_map):
    # Known number with @s.whatsapp.net suffix
    assert resolve_relationship("919812345670@s.whatsapp.net", temp_map) == ("friend", "history_friend")
    # Known number with @lid suffix
    assert resolve_relationship("144443332255@lid", temp_map) == ("friend", "history_friend")


def test_unknown_number_falls_back_to_default(temp_map):
    assert resolve_relationship("999999999999@s.whatsapp.net", temp_map) == ("unknown", "history_unknown")


def test_group_jid_always_returns_group_none(temp_map):
    # Standard group JID ends with @g.us
    assert resolve_relationship("1234567890-123456@g.us", temp_map) == ("group", None)
    # Even if the number prefix exists in the map, @g.us immediately returns ("group", None)
    assert resolve_relationship("919812345670@g.us", temp_map) == ("group", None)


def test_malformed_or_empty_jid_does_not_crash(temp_map):
    assert resolve_relationship("", temp_map) == ("unknown", "history_unknown")
    assert resolve_relationship("@", temp_map) == ("unknown", "history_unknown")
    assert resolve_relationship("   ", temp_map) == ("unknown", "history_unknown")
    assert resolve_relationship(None, temp_map) == ("unknown", "history_unknown")


def test_missing_default_in_map_falls_back_to_unknown(tmp_path):
    map_path = tmp_path / "empty_map.json"
    map_path.write_text(json.dumps({"919812345670": "friend"}), encoding="utf-8")
    assert resolve_relationship("999999999999@s.whatsapp.net", str(map_path)) == ("unknown", "history_unknown")
