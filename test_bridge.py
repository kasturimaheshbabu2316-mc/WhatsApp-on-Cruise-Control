"""Tests for the Flask bridge server."""

from __future__ import annotations

import json
import pytest
from bridge import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "service" in data


def test_process_unknown_contact(client):
    response = client.post(
        "/process",
        json={
            "jid": "919000000000@s.whatsapp.net",
            "text": "Hello there",
            "message_type": "text",
            "is_forwarded": False,
            "from_me": False,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["should_reply"] is False
    assert data["relationship"] == "unknown"
    assert "not in allowlist" in data["reason"].lower()


def test_process_from_me(client):
    response = client.post(
        "/process",
        json={
            "jid": "919812345670@s.whatsapp.net",
            "text": "Hey what's up",
            "message_type": "text",
            "is_forwarded": False,
            "from_me": True,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["should_reply"] is False
    assert "own message" in data["reason"].lower()


def test_process_money_request(client):
    response = client.post(
        "/process",
        json={
            "jid": "919812345670@s.whatsapp.net",
            "text": "Send me 50000 rupees emergency loan please",
            "message_type": "text",
            "is_forwarded": False,
            "from_me": False,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["should_reply"] is False
    assert "money" in data["reason"].lower() or "human" in data["reason"].lower()
