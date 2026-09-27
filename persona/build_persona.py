#!/usr/bin/env python3
"""Build persona style signals from a WhatsApp text export."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


MESSAGE_START = re.compile(
    r"^(?:\[(?P<date_ios>[^,]+),\s*(?P<time_ios>[^\]]+)\]\s+|(?P<date>[^,]+),\s*(?P<time>[^-\n]+?)\s*-\s*)(?P<sender>[^:]+):\s?(?P<message>.*)$"
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
    """Parse WhatsApp text export and return (sender, message) pairs."""
    messages: list[tuple[str, str]] = []
    current_sender: str | None = None
    current_message: list[str] = []

    def save_current() -> None:
        if current_sender is not None:
            messages.append((current_sender, "\n".join(current_message).strip()))

    with open(file_path, "r", encoding="utf-8", errors="ignore") as export:
        for raw_line in export:
            line = raw_line.rstrip("\r\n")
            match = MESSAGE_START.match(line)
            if match:
                save_current()
                current_sender = match.group("sender").strip()
                current_message = [match.group("message")]
            elif current_sender is not None:
                current_message.append(line)

    save_current()
    return messages


def compute_style_signals(messages: list[str]) -> dict:
    """Compute persona style signals from a list of messages."""
    if not messages:
        return {
            "hinglish_ratio_percent": 0.0,
            "average_message_length_words": 0.0,
            "top_emojis": [],
            "total_sample_size": 0,
        }

    hinglish_messages = sum(
        bool(HINGLISH_PATTERN.search(message)) for message in messages
    )
    word_counts = [
        len(re.findall(r"\b[\w'’-]+\b", message)) for message in messages
    ]
    emojis = Counter(
        emoji
        for message in messages
        for emoji in EMOJI_PATTERN.findall(message)
    )

    return {
        "hinglish_ratio_percent": round(100.0 * hinglish_messages / len(messages), 2),
        "average_message_length_words": round(sum(word_counts) / len(messages), 2),
        "top_emojis": [
            {"emoji": emoji, "frequency": frequency}
            for emoji, frequency in emojis.most_common(15)
        ],
        "total_sample_size": len(messages),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract persona style signals from a WhatsApp .txt export."
    )
    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Path to the WhatsApp .txt export file",
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Exact sender name as it appears in the export",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("persona/style_signals.json"),
        help="Path to output JSON file (default: persona/style_signals.json)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    all_messages = parse_messages(args.file)
    sender_messages = [
        message for sender, message in all_messages if sender == args.name
    ]

    if not sender_messages:
        print(
            f'\n⚠️  Warning: Zero matching messages found for sender "{args.name}" in {args.file.name}.\n'
            f"Please double-check the exact sender name as it appears in the raw export.\n"
        )
        senders = Counter(sender for sender, _ in all_messages)
        if senders:
            print("Available senders found in the file:")
            for sender_name, count in senders.most_common(10):
                print(f"  - {sender_name!r}: {count} messages")
        print("\nNo output file was written.")
        sys.exit(1)

    signals = compute_style_signals(sender_messages)

    # Save to JSON
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Print human-readable summary to terminal
    print("=" * 60)
    print("PERSONA STYLE SIGNALS SUMMARY")
    print("=" * 60)
    print(f"File:                   {args.file}")
    print(f"Sender:                 {args.name}")
    print(f"Total Sample Size:      {signals['total_sample_size']} messages")
    print(f"Hinglish Ratio:         {signals['hinglish_ratio_percent']:.2f}%")
    print(f"Avg Message Length:     {signals['average_message_length_words']:.2f} words")
    print("Top Emojis:")
    if signals["top_emojis"]:
        for item in signals["top_emojis"]:
            print(f"  {item['emoji']} : {item['frequency']}")
    else:
        print("  (None found)")
    print("=" * 60)
    print(f"JSON saved to:          {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
