import collections
import json
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


INPUT_PATH = "data/processed_pairs.jsonl"
SAMPLE_SIZE = 5
NOISE_MARKERS = (
    "omitted",
    "<media",
    "deleted",
    "voice call",
    "video call",
    "can't talk now",
    "http://",
    "https://",
)
WARNING = "\033[91m"
RESET = "\033[0m"


def warn(message: str) -> None:
    print(f"{WARNING}WARNING: {message}{RESET}")


def word_count(text: str) -> int:
    return len(text.split())


def normalized_words(text: str) -> set[str]:
    words = set()
    for word in text.casefold().split():
        cleaned = "".join(character for character in word if character.isalnum())
        if cleaned:
            words.add(cleaned)
    return words


def is_near_identical(first: str, second: str) -> bool:
    """Detect exact or almost identical text without third-party dependencies."""
    first_words = normalized_words(first)
    second_words = normalized_words(second)
    if not first_words or not second_words:
        return False
    overlap = len(first_words & second_words) / len(first_words | second_words)
    return overlap >= 0.9 and min(len(first_words), len(second_words)) >= 2


def load_pairs() -> tuple[list[dict], int]:
    pairs: list[dict] = []
    malformed_count = 0
    with open(INPUT_PATH, encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError as error:
                malformed_count += 1
                warn(f"Line {line_number} is not valid JSON: {error}")
    return pairs, malformed_count


def print_samples(pairs: list[dict]) -> None:
    print(f"\nRandom samples ({min(SAMPLE_SIZE, len(pairs))}):")
    for sample_number, pair in enumerate(random.sample(pairs, min(SAMPLE_SIZE, len(pairs))), 1):
        print(f"\n--- Sample {sample_number} [{pair.get('conversation_id', 'unknown')}] ---")
        print(f"Their message:\n{pair.get('their_message', '')}")
        print(f"\nMy reply:\n{pair.get('my_reply', '')}")
        print(f"\nTimestamp: {pair.get('timestamp', 'unknown')}")


def main() -> None:
    pairs, malformed_count = load_pairs()
    counts = collections.Counter(pair.get("conversation_id", "<missing>") for pair in pairs)
    issues = malformed_count

    print(f"Pair validation report: {INPUT_PATH}")
    print(f"Total pairs: {len(pairs)}")
    print("\nPairs by conversation:")
    if counts:
        for conversation_id, count in sorted(counts.items()):
            print(f"- {conversation_id}: {count}")
    else:
        warn("No conversation IDs found")
        issues += 1

    for conversation_id, count in counts.items():
        if count == 0:
            warn(f"conversation_id '{conversation_id}' has 0 pairs")
            issues += 1

    noise_flags = 0
    long_flags = 0
    duplicate_flags = 0
    for pair_number, pair in enumerate(pairs, start=1):
        their_message = pair.get("their_message", "")
        my_reply = pair.get("my_reply", "")

        for field_name, text in (("their_message", their_message), ("my_reply", my_reply)):
            lowered = text.casefold()
            if not text.strip():
                warn(f"Pair {pair_number}: empty {field_name}")
                noise_flags += 1
            elif any(marker in lowered for marker in NOISE_MARKERS):
                warn(f"Pair {pair_number}: noise marker leaked into {field_name}")
                noise_flags += 1

        if word_count(my_reply) > 100:
            warn(f"Pair {pair_number}: my_reply is {word_count(my_reply)} words")
            long_flags += 1

        if their_message.casefold() == my_reply.casefold() or is_near_identical(
            their_message, my_reply
        ):
            warn(f"Pair {pair_number}: their_message and my_reply are identical or near-identical")
            duplicate_flags += 1

    issues += noise_flags + long_flags + duplicate_flags
    print_samples(pairs)

    print("\nFlag totals:")
    print(f"- Noise/empty: {noise_flags}")
    print(f"- Suspiciously long replies: {long_flags}")
    print(f"- Identical/near-identical pairs: {duplicate_flags}")
    print(f"\n{'âœ… Looks good' if issues == 0 else f'âš ï¸ {issues} issues found â€” review above'}")


if __name__ == "__main__":
    main()