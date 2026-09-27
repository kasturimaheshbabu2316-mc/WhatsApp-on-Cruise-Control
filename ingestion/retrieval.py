#!/usr/bin/env python3
from __future__ import annotations

"""Retrieve top-k similar conversation pairs from relationship-specific ChromaDB history."""

import os
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = ROOT_DIR / "chroma_data"
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8000))

# Load embedding model once at module level
_model: SentenceTransformer = SentenceTransformer(MODEL_NAME)

# Load ChromaDB client once at module level
try:
    if CHROMA_PATH.exists():
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    else:
        _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    _client.heartbeat()
except Exception:
    try:
        _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        _client.heartbeat()
    except Exception:
        try:
            _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            _client.heartbeat()
        except Exception as final_err:
            raise ConnectionError(f"Failed to connect to ChromaDB: {final_err}") from final_err


def get_client() -> chromadb.ClientAPI:
    """Return the initialized ChromaDB client instance."""
    return _client


def get_model() -> SentenceTransformer:
    """Return the initialized SentenceTransformer model instance."""
    return _model


def retrieve_similar(
    relationship: str, incoming_message: str, k: int = 3
) -> list[dict]:
    """Retrieve top-k similar past conversation turns from Chroma history collection.

    Returns a list of {"their_message": str, "my_reply": str, "distance": float} dicts.
    Returns an empty list if the collection doesn't exist or has zero results.
    Never raises an exception for an empty result, only for genuine connection failures.
    """
    if not incoming_message or not isinstance(incoming_message, str) or not incoming_message.strip():
        return []

    collection_name = f"history_{relationship}"
    try:
        collection = _client.get_collection(collection_name)
    except Exception as e:
        err_msg = str(e).lower()
        if "does not exist" in err_msg or "not found" in err_msg or isinstance(e, (ValueError, KeyError)):
            return []
        raise

    count = collection.count()
    if count == 0:
        return []

    query_embedding = _model.encode([incoming_message.strip()], show_progress_bar=False)[0].tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, count),
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output: list[dict] = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        my_reply = meta.get("my_reply", "") if isinstance(meta, dict) else ""
        output.append(
            {
                "their_message": doc,
                "my_reply": my_reply,
                "distance": float(dist),
            }
        )
    return output
