#!/usr/bin/env python3
"""Parse raw WhatsApp text exports into conversational reply pairs."""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_EXPORT_DIR = ROOT_DIR / "data" / "raw_export"
OUTPUT_PATH = ROOT_DIR / "data" / "processed_pairs.jsonl"
PER_CONVERSATION_OUTPUT_DIR = ROOT_DIR / "data" / "processed_pairs"
MAX_PAIRS_PER_CONVERSATION = 500

# Substrings identifying system, media, or non-conversational lines (case-insensitive)
SYSTEM_OR_MEDIA_SUBSTRINGS = (
    "Messages and calls are end-to-end encrypted",
    "<Media omitted>",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "GIF omitted",
    "document omitted",
    "Contact card omitted",
    "This message was deleted",
    "You deleted this message",
    "Missed voice call",
    "Missed video call",
    "Missed group voice call",
    "Missed group video call",
    "Voice call",
    "Video call",
    "Voice call ended",
    "Video call ended",
    "Ongoing voice call",
    "Ongoing video call",
    "Started a voice call",
    "Started a video call",
    "Started a call",
    "Started a group call",
    "Group voice call",
    "Group video call",
    "Call ended",
    "Call declined",
    "Call disconnected",
    "Can't talk now. What's up?",
    "Can't talk now. Call me later?",
    "Can't talk now. I'm on my way.",
    "Can't talk now",
    "<This message was edited>",
    "created group",
    "changed the subject",
    "added you",
    "changed this group's icon",
    "changed the group description",
    "Waiting for this message",
    "Live location shared",
)

# Import shared ONE_WORD_ACKS set from config.constants
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.constants import ONE_WORD_ACKS

# Supports standard unbracketed "DATE, TIME - SENDER: MESSAGE" and bracketed "[DATE, TIME] SENDER: MESSAGE"

MESSAGE_START = re.compile(
    r"^(?:\[(?P<bracket_date>[^,\]]+),\s*(?P<bracket_time>[^\]]+)\]|"
    r"(?P<plain_date>[^,]+),\s*(?P<plain_time>\S+(?:\s+[AP]M)?))"
    r"\s*(?:-|)\s*(?P<sender>[^:]+):\s?(?P<message>.*)$",
    re.IGNORECASE,
)


@dataclass
class Message:
    sender: str
    text: str
    timestamp: str


@dataclass
class Turn:
    sender: str
    text: str
    timestamp: str
    is_valid: bool = True


def conversation_id_from_path(file_path: Path) -> str:
    """Derive a lowercase hyphenated ID from an export filename."""
    name = file_path.stem
    prefix = "WhatsApp Chat with "
    if name.lower().startswith(prefix.lower()):
        name = name[len(prefix):]
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_messages(file_path: Path) -> list[Message]:
    """Parse message starts and attach every non-start line to the prior message."""
    messages: list[Message] = []
    current: Message | None = None

    def save_current() -> None:
        if current is not None:
            messages.append(current)

    with file_path.open(encoding="utf-8-sig", errors="replace") as export:
        for raw_line in export:
            line = raw_line.rstrip("\r\n")
            match = MESSAGE_START.match(line)
            if match:
                save_current()
                date = match.group("bracket_date") or match.group("plain_date")
                time = match.group("bracket_time") or match.group("plain_time")
                current = Message(
                    sender=match.group("sender").strip(),
                    text=match.group("message"),
                    timestamp=f"{date}, {time}",
                )
            elif current is not None:
                current.text += f"\n{line}"

    save_current()
    return messages


def is_system_or_media(message: str) -> bool:
    lowered = message.casefold()
    if "http://" in lowered or "https://" in lowered:
        return True
    return any(substring.casefold() in lowered for substring in SYSTEM_OR_MEDIA_SUBSTRINGS)


def is_standalone_acknowledgement(message: str) -> bool:
    normalized = re.sub(r"[\s.!?,;:]+$", "", message.strip().casefold())
    return normalized in ONE_WORD_ACKS



def build_turns(messages: list[Message]) -> list[Turn]:
    """Filter messages and merge consecutive valid messages from the same sender."""
    turns: list[Turn] = []
    for message in messages:
        text = message.text.strip()
        is_invalid = (
            not text
            or is_system_or_media(text)
            or is_standalone_acknowledgement(text)
        )

        if is_invalid:
            # An intervening media/call/empty/system event breaks previous turn continuity
            turns.append(Turn(message.sender, "", message.timestamp, is_valid=False))
            continue

        if turns and turns[-1].is_valid and turns[-1].sender == message.sender:
            turns[-1].text += f"\n{text}"
        else:
            turns.append(Turn(message.sender, text, message.timestamp, is_valid=True))
    return turns


def make_pairs(
    conversation_id: str, turns: list[Turn], my_name: str
) -> list[dict[str, str]]:
    """Emit adjacent other-person -> me reply pairs in file order."""
    pairs: list[dict[str, str]] = []
    for their_turn, my_turn in zip(turns, turns[1:]):
        if (
            their_turn.is_valid
            and my_turn.is_valid
            and their_turn.sender != my_name
            and my_turn.sender == my_name
        ):
            if len(my_turn.text.split()) > 100:
                continue
            if their_turn.text.strip().casefold() == my_turn.text.strip().casefold():
                continue
            pairs.append(
                {
                    "conversation_id": conversation_id,
                    "their_message": their_turn.text,
                    "my_reply": my_turn.text,
                    "timestamp": my_turn.timestamp,
                }
            )
    return pairs[-MAX_PAIRS_PER_CONVERSATION:]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse WhatsApp exports into reply pairs.")
    parser.add_argument(
        "--name", default=".", help="Exact sender name for your messages in the exports (default: '.')"
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory containing raw export .txt files (default: data/raw_export)",
    )
    return parser


def write_jsonl(output_path: Path, pairs: list[dict[str, str]]) -> None:
    """Write pairs as one JSON object per line."""
    with output_path.open("w", encoding="utf-8") as output:
        for pair in pairs:
            output.write(json.dumps(pair, ensure_ascii=False) + "\n")


def main() -> None:
    args = build_parser().parse_args()
    all_pairs: list[dict[str, str]] = []

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PER_CONVERSATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_dir = args.input_dir or RAW_EXPORT_DIR
    if input_dir.exists():
        files = sorted(input_dir.glob("*.txt")) or sorted(input_dir.glob("**/*.txt"))
    else:
        files = sorted(Path("Whatsapp chats").glob("**/*.txt"))

    if not files:
        print(f"Warning: No WhatsApp chat export (.txt) files found in {input_dir}.", file=sys.stderr)
        return

    print("=" * 60)
    print("WHATSAPP EXPORT PARSER")
    print("=" * 60)
    print(f"Raw exports directory:    {input_dir}")
    print(f"Target sender name:       {args.name!r}")
    print(f"Output path:              {OUTPUT_PATH}")
    print("-" * 60)

    for file_path in files:
        conversation_id = conversation_id_from_path(file_path)
        messages = parse_messages(file_path)
        pairs = make_pairs(conversation_id, build_turns(messages), args.name)
        all_pairs.extend(pairs)
        
        per_chat_output = PER_CONVERSATION_OUTPUT_DIR / f"{conversation_id}.jsonl"
        write_jsonl(per_chat_output, pairs)
        
        print(f"📄 {file_path.name}: {len(pairs)} pairs kept -> {per_chat_output.name}")
        if not pairs:
            print(
                f'   ⚠️  Warning: conversation_id "{conversation_id}" produced zero pairs; '
                f'check if --name "{args.name}" matches the exact sender in this file.'
            )

    write_jsonl(OUTPUT_PATH, all_pairs)

    print("=" * 60)
    print(f"✅ Total pairs written: {len(all_pairs)} to {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
