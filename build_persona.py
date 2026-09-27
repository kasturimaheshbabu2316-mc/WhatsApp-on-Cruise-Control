#!/usr/bin/env python3
"""Build simple persona style signals from a WhatsApp text export."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


MESSAGE_START = re.compile(
    r"^(?:\[(?P<date_ios>[^,]+),\s*(?P<time_ios>[^\]]+)\]\s+|(?P<date_and>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<time_and>[^-\n]+?)\s*-\s*)(?P<sender>[^:]+):\s?(?P<message>.*)$"
)
HINGLISH_WORDS = (
    "hai",
    "kya",
    "nahi",
    "yaar",
    "matlab",
    "acha",
    "theek",
    "bhai",
    "haan",
    "toh",
)
HINGLISH_PATTERN = re.compile(
    r"\b(?:" + "|".join(map(re.escape, HINGLISH_WORDS)) + r")\b",
    re.IGNORECASE,
)
EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF]"
)


def parse_messages(file_path: Path) -> list[tuple[str, str]]:
    """Return (sender, message) pairs from a WhatsApp text export."""
    messages: list[tuple[str, str]] = []
    current_sender: str | None = None
    current_message: list[str] = []

    def save_current() -> None:
        if current_sender is not None:
            messages.append((current_sender, "\n".join(current_message).strip()))

    with file_path.open(encoding="utf-8", errors="ignore") as export:
        for raw_line in export:
            line = raw_line.rstrip("\n\r")
            match = MESSAGE_START.match(line)
            if match:
                save_current()
                current_sender = match.group("sender")
                current_message = [match.group("message")]
            elif current_sender is not None:
                current_message.append(line)

    save_current()
    return messages


def compute_style_signals(messages: list[str]) -> dict:
    """Compute the requested style signals for one sender's messages."""
    hinglish_messages = sum(bool(HINGLISH_PATTERN.search(message)) for message in messages)
    word_counts = [len(re.findall(r"\b[\w'’-]+\b", message)) for message in messages]
    emojis = Counter(emoji for message in messages for emoji in EMOJI_PATTERN.findall(message))

    return {
        "hinglish_ratio_percent": round(100 * hinglish_messages / len(messages), 2),
        "average_message_length_words": round(sum(word_counts) / len(messages), 2),
        "top_emojis": [
            {"emoji": emoji, "frequency": frequency}
            for emoji, frequency in emojis.most_common(15)
        ],
        "total_sample_size": len(messages),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract persona style signals from a WhatsApp .txt export."
    )
    parser.add_argument("--file", type=Path, default=None, help="Path to the WhatsApp .txt export")
    parser.add_argument("--name", type=str, default=".", help="Exact sender name as it appears in the export (default: '.')")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (defaults to style_signals_<chat_name>.json or style_signals.json)",
    )
    return parser


def process_chat(file_path: Path, sender_name: str, output_path: Path | None = None) -> None:
    """Parse a chat export, compute signals for the specified sender, and save to JSON."""
    all_messages = parse_messages(file_path)
    sender_messages = [message for sender, message in all_messages if sender == sender_name]

    if not sender_messages:
        # If the default '.' wasn't found, find the top sender
        senders = Counter(sender for sender, _ in all_messages)
        print(f'Warning: no messages found for sender "{sender_name}" in {file_path.name}.')
        if senders:
            print(f"Available senders in this chat: {', '.join(f'{k} ({v} msgs)' for k, v in senders.most_common(5))}")
        return

    signals = compute_style_signals(sender_messages)
    
    if output_path is None:
        sanitized_name = re.sub(r"[^\w\-]", "_", file_path.stem.lower()).strip("_")
        output_path = file_path.parent / f"style_signals_{sanitized_name}.json"
        if not output_path.parent.exists():
            output_path = Path(f"style_signals_{sanitized_name}.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(signals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=" * 60)
    print(f"Chat File: {file_path.name}")
    print(f"Persona style signals for: {sender_name}")
    print(f"Hinglish messages: {signals['hinglish_ratio_percent']:.2f}%")
    print(f"Average message length: {signals['average_message_length_words']:.2f} words")
    print(f"Top emojis: {signals['top_emojis'] or 'none'}")
    print(f"Total sample size: {signals['total_sample_size']} messages")
    print(f"JSON written to: {output_path}")
    print("=" * 60)


def main() -> None:
    args = build_parser().parse_args()

    if args.file:
        process_chat(args.file, args.name, args.output)
    else:
        # Auto-discover chat exports in workspace
        root_dir = Path(__file__).resolve().parent
        chat_files = list(root_dir.glob("Whatsapp chats/**/*.txt")) + list(root_dir.glob("*.txt"))
        # Filter out non-chat text files if any
        chat_files = [f for f in chat_files if "chat" in f.name.lower() or "whatsapp" in f.name.lower()]

        if not chat_files:
            print("No WhatsApp chat exports found in 'Whatsapp chats/' directory.")
            return

        print(f"Discovered {len(chat_files)} WhatsApp chat export(s). Processing...\n")
        for chat_file in chat_files:
            process_chat(chat_file, args.name, args.output)


if __name__ == "__main__":
    main()