#!/usr/bin/env python3
"""Run readable retrieval checks against the relationship-specific histories."""

import argparse
import sys
from contextlib import redirect_stdout
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.retrieval import retrieve_similar

RESULTS_PATH = ROOT_DIR / "retrieval_results.txt"
RELATIONSHIPS = ("friend", "unknown")

# Realistic, tone-appropriate built-in queries per relationship category
SAMPLE_QUERIES = {
    "friend": (
        "Bhai free aa ippudu? Call cheyyi urgent ga.",
        "Rey em chesthunnav ra?",
        "Ludo adudham coins unnai, vasthava?",
    ),
    "unknown": (
        "Can you send me an update?",
        "What time should we meet?",
        "Thanks, I will check and let you know.",
    ),
}


class Tee:
    """Write the report to the terminal and the saved results file simultaneously."""

    def __init__(self, terminal, report_file):
        self.terminal = terminal
        self.report_file = report_file

    def write(self, text: str) -> int:
        self.terminal.write(text)
        self.report_file.write(text)
        self.report_file.flush()
        return len(text)

    def flush(self) -> None:
        self.terminal.flush()
        self.report_file.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Demo and verify retrieval from relationship-specific ChromaDB histories."
    )
    parser.add_argument(
        "--relationship",
        choices=("all", *RELATIONSHIPS),
        default="all",
        help="Relationship collection to search (default: all — friend, unknown).",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Custom query string to test across selected relationship collection(s).",
    )
    parser.add_argument(
        "-k",
        type=int,
        default=3,
        help="Number of similar results to retrieve (default: 3).",
    )
    return parser


def selected_relationships(relationship: str) -> tuple[str, ...]:
    return RELATIONSHIPS if relationship == "all" else (relationship,)


def print_results(relationship: str, query: str, results: list[dict]) -> bool:
    print("\n" + "=" * 72)
    print(f"Collection:     history_{relationship}")
    print(f"Test query:     {query}")
    print("=" * 72)

    if not results:
        print("  (No matching results found)")
        print("=" * 72)
        return True

    distances = [r.get("distance", 0.0) for r in results]

    for result_number, item in enumerate(results, start=1):
        dist = item.get("distance", 0.0)
        doc = item.get("their_message", "")
        reply = item.get("my_reply", "")

        print(f"\n--- Result {result_number} [distance: {dist:.6f}] ---")
        print(f"Their message:\n{doc}")
        print(f"\nMy reply:\n{reply}")

    print("-" * 72)
    is_monotonic = all(first <= second for first, second in zip(distances, distances[1:]))
    return is_monotonic


def run_demo(args: argparse.Namespace) -> None:
    relationships = selected_relationships(args.relationship)
    sanity_checks: dict[str, list[bool]] = {rel: [] for rel in relationships}

    for relationship in relationships:
        queries = (args.query,) if args.query else SAMPLE_QUERIES.get(relationship, ("Hello",))
        has_results = False

        for query in queries:
            results = retrieve_similar(relationship=relationship, incoming_message=query, k=args.k)
            if not results:
                continue
            has_results = True
            is_monotonic = print_results(relationship, query, results)
            sanity_checks[relationship].append(is_monotonic)

        if not has_results:
            print(f"\n⚠️  no data in history_{relationship}, skipping")

    print("\n" + "=" * 72)
    print("RETRIEVAL SANITY CHECKS (Distance Monotonicity):")
    print("=" * 72)
    for relationship in relationships:
        checks = sanity_checks[relationship]
        if not checks:
            print(f"- {relationship:<14}: ⚠️ skipped (no data in collection)")
        elif all(checks):
            print(f"- {relationship:<14}: ✅ distances monotonically increasing (expected/good)")
        else:
            print(f"- {relationship:<14}: ⚠️ distances not monotonically increasing (worth a second look)")
    print("=" * 72)


def main() -> None:
    args = build_parser().parse_args()
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", encoding="utf-8") as report_file:
        with redirect_stdout(Tee(sys.stdout, report_file)):
            run_demo(args)
    print(f"\n📄 Saved complete retrieval results report to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()