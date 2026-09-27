#!/usr/bin/env python3
"""Embed processed WhatsApp pairs and upsert them into local ChromaDB."""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
PAIRS_PATH = ROOT_DIR / "data" / "processed_pairs.jsonl"
MAP_PATH = ROOT_DIR / "config" / "contact_relationship_map.json"
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000
BATCH_SIZE = 50
RELATIONSHIPS = ("friend", "unknown")
PLACEHOLDER = "REPLACE_ME"



def load_pairs(pairs_path: Path) -> list[dict[str, str]]:
    if not pairs_path.exists():
        print(f"❌ Error: Processed pairs file not found at {pairs_path}", file=sys.stderr)
        print("Run 'python ingestion/parse_export.py' first.", file=sys.stderr)
        sys.exit(1)

    pairs: list[dict[str, str]] = []
    with pairs_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                pairs.append(json.loads(line_str))
            except json.JSONDecodeError as e:
                print(f"Warning: Line {line_num} in {pairs_path.name} is invalid JSON: {e}", file=sys.stderr)
    return pairs


def load_relationship_map(map_path: Path) -> dict[str, str]:
    search_paths = [
        map_path,
        ROOT_DIR / "config" / "contact_relationship_map.json",
        ROOT_DIR / "contact_relationship_map.json",
        ROOT_DIR / "relationship_map.json",
    ]
    for p in search_paths:
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"Warning: Could not read {p}: {e}. Trying next fallback.", file=sys.stderr)
    return {"_default": "unknown"}


def relationship_for(pair: dict[str, str], relationship_map: dict[str, str]) -> str:
    cid = pair.get("conversation_id", "")
    rel = relationship_map.get(cid, relationship_map.get("_default", "unknown"))
    if rel in (PLACEHOLDER, None, "") or rel.lower() not in RELATIONSHIPS:
        return "unknown"
    return rel.lower()


def stable_id(pair: dict[str, str], index: int) -> str:
    identity = "\x1f".join(
        (
            str(pair.get("conversation_id", "")),
            str(pair.get("timestamp", "")),
            str(index),
            str(pair.get("their_message", ""))[:50],
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Embed conversation pairs and upload to ChromaDB.")
    parser.add_argument(
        "--path",
        default=str(ROOT_DIR / "chroma_data"),
        help="Path to ChromaDB persistent storage directory (default: ./chroma_data)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Connect to ChromaDB HTTP server instead of local persistent directory",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"ChromaDB host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"ChromaDB port (default: {DEFAULT_PORT})")
    return parser


def get_chroma_client(args, chromadb):
    if args.http or (args.host != DEFAULT_HOST) or (args.port != DEFAULT_PORT):
        print(f"Connecting to ChromaDB HTTP server: http://{args.host}:{args.port}")
        try:
            client = chromadb.HttpClient(host=args.host, port=args.port)
            client.heartbeat()
            return client
        except Exception as e:
            print(f"\n❌ Error connecting to ChromaDB at http://{args.host}:{args.port}: {e}", file=sys.stderr)
            print("\n💡 Make sure the local ChromaDB server is running. You can start it with:", file=sys.stderr)
            print(f"   chroma run --path {args.path} --port {args.port}\n", file=sys.stderr)
            sys.exit(1)
    else:
        persist_path = Path(args.path)
        persist_path.mkdir(parents=True, exist_ok=True)
        print(f"Connecting to ChromaDB persistent storage at: {persist_path.resolve()}")
        try:
            client = chromadb.PersistentClient(path=str(persist_path))
            client.heartbeat()
            return client
        except Exception as e:
            print(f"\n❌ Error opening ChromaDB at {persist_path}: {e}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    args = build_parser().parse_args()

    try:
        import chromadb  # type: ignore
    except ImportError:
        print("❌ Error: chromadb package is not installed. Install it with: pip install chromadb", file=sys.stderr)
        sys.exit(1)

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        print("❌ Error: sentence-transformers package is not installed. Install it with: pip install sentence-transformers", file=sys.stderr)
        sys.exit(1)

    pairs = load_pairs(PAIRS_PATH)
    relationship_map = load_relationship_map(MAP_PATH)

    print("=" * 60)
    print("CHROMA EMBEDDING & INGESTION PIPELINE")
    print("=" * 60)
    print(f"Total pairs to process:    {len(pairs)}")

    client = get_chroma_client(args, chromadb)

    collections = {
        rel: client.get_or_create_collection(f"history_{rel}")
        for rel in RELATIONSHIPS
    }

    print(f"Loading embedding model:   {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded successfully. Starting embedding batches...\n")

    counts: defaultdict[str, int] = defaultdict(int)

    for batch_start in range(0, len(pairs), BATCH_SIZE):
        batch = pairs[batch_start : batch_start + BATCH_SIZE]
        their_messages = [pair.get("their_message", "") for pair in batch]

        embeddings = model.encode(their_messages, show_progress_bar=False)

        grouped: defaultdict[str, list[tuple[dict[str, str], list[float], int]]] = defaultdict(list)
        for offset, (pair, embedding) in enumerate(zip(batch, embeddings)):
            index = batch_start + offset
            rel = relationship_for(pair, relationship_map)
            grouped[rel].append((pair, embedding.tolist(), index))

        for rel, records in grouped.items():
            ids = [stable_id(pair, index) for pair, _, index in records]
            
            for other_rel in RELATIONSHIPS:
                if other_rel != rel:
                    try:
                        collections[other_rel].delete(ids=ids)
                    except Exception:
                        pass

            collections[rel].upsert(
                ids=ids,
                embeddings=[emb for _, emb, _ in records],
                documents=[pair.get("their_message", "") for pair, _, _ in records],
                metadatas=[
                    {
                        "conversation_id": pair.get("conversation_id", ""),
                        "my_reply": pair.get("my_reply", ""),
                        "timestamp": pair.get("timestamp", ""),
                    }
                    for pair, _, _ in records
                ],
            )
            counts[rel] += len(records)

        processed = min(batch_start + len(batch), len(pairs))
        print(f"⏳ Processed {processed}/{len(pairs)} pairs ({(processed/len(pairs))*100:.1f}%)")

    print("\n" + "=" * 60)
    print("CHROMA EMBEDDING SUMMARY")
    print("=" * 60)
    for rel in RELATIONSHIPS:
        count = collections[rel].count()
        print(f"• history_{rel:<13}: {count} total records in collection")
        if count == 0:
            print(f"  ⚠️  WARNING: history_{rel} is completely empty!")
    print("=" * 60)
    print("✅ Ingestion to ChromaDB complete.")


if __name__ == "__main__":
    main()