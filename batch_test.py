#!/usr/bin/env python3
"""Exercise every reply-or-ignore gate in one readable dry run."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure workspace root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agent.decision_engine import should_reply
from agent.generator import generate_reply
from agent.router import resolve_relationship


TEST_CASES = [
    {
        "name": "own message",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": True,
        "text": "I already sent this update.",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "group chat",
        "jid": "120363000000000000@g.us",
        "from_me": False,
        "text": "What time are we meeting?",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "unknown number",
        "jid": "919899999999@s.whatsapp.net",
        "from_me": False,
        "text": "Hello, are you available?",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "media only",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": False,
        "text": "",
        "message_type": "image",
        "is_forwarded": False,
    },
    {
        "name": "forwarded message",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": False,
        "text": "Please share this important update.",
        "message_type": "text",
        "is_forwarded": True,
    },
    {
        "name": "one-word ack",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": False,
        "text": "thanks",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "money request",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": False,
        "text": "Can you send me 5000 rupees?",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "casual friend (dinner)",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": False,
        "text": "Are you free for dinner tonight?",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "casual friend (banter)",
        "jid": "919812345670@s.whatsapp.net",
        "from_me": False,
        "text": "Rey em chesthunnav ra?",
        "message_type": "text",
        "is_forwarded": False,
    },
    {
        "name": "casual friend (weekend plan)",
        "jid": "144443332255@s.whatsapp.net",
        "from_me": False,
        "text": "Want to catch a movie this weekend?",
        "message_type": "text",
        "is_forwarded": False,
    },
]


def compact(value: str, limit: int = 42) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else f"{value[: limit - 3]}..."


def main() -> None:
    results: list[dict[str, str]] = []
    print("Running decision-engine batch test...\n")

    for idx, test_case in enumerate(TEST_CASES):
        if idx > 0:
            time.sleep(1.0)
        relationship, _ = resolve_relationship(test_case["jid"])
        message = {
            key: test_case[key]
            for key in ("from_me", "text", "message_type", "is_forwarded")
        }
        should_reply_result, reason = should_reply(message, relationship)
        reply = ""
        if should_reply_result:
            time.sleep(1.0)
            try:
                reply = generate_reply(test_case["text"], relationship)
            except Exception as error:
                reply = f"[generation error: {error}]"

        results.append(
            {
                "message": test_case["text"],
                "relationship": relationship,
                "decision": "reply" if should_reply_result else "ignore",
                "reason": reason,
                "reply": reply,
            }
        )
        print(f"[{test_case['name']}] -> {results[-1]['decision'].upper()}: {reason}")
        if reply:
            print(f"  ↳ Generated Reply: {compact(reply, 100)}")

    print("\n" + "=" * 125)
    print("BATCH TEST DECISION ENGINE SUMMARY")
    print("=" * 125)
    print(f"{'Message':<42} {'Relationship':<14} {'Decision':<10} {'Reason':<44} Reply")
    print("-" * 125)
    for result in results:
        msg_display = result["message"] if result["message"] else "(media without caption)"
        print(
            f"{compact(msg_display, 40):<42} "
            f"{result['relationship']:<14} "
            f"{result['decision']:<10} "
            f"{compact(result['reason'], 42):<44} "
            f"{compact(result['reply'], 50)}"
        )
    print("=" * 125)


if __name__ == "__main__":
    main()
