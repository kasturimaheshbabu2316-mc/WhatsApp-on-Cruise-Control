#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Live Console Feed.
Standalone Streamlit viewer displaying live incoming WhatsApp messages,
autonomous decision results, reasons, generated replies, and ChromaDB retrieval traces.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "logs" / "console_feed.jsonl"
MODE_PATH = ROOT / "config" / "mode.txt"

RELATIONSHIP_COLORS = {
    "family": "#2e7d32",
    "friend": "#1565c0",
    "professional": "#6a1b9a",
    "unknown": "#6b7280",
    "group": "#6b7280",
}


def read_mode() -> str:
    try:
        text = MODE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "DRY_RUN"

    value = text.upper().strip()
    return value if value in {"DRY_RUN", "LIVE"} else "DRY_RUN"


def set_mode(mode: str) -> None:
    MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODE_PATH.write_text(mode.strip().upper() + "\n", encoding="utf-8")


def load_logs() -> list[dict]:
    if not LOG_PATH.exists():
        return []

    entries: list[dict] = []

    with LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)

    entries = [entry for entry in entries if isinstance(entry, dict)]
    return entries[-50:][::-1]


def render_relationship_badge(relationship: str) -> None:
    rel = str(relationship or "unknown").lower()
    color = RELATIONSHIP_COLORS.get(rel, "#6b7280")
    st.markdown(
        f"""
        <span style="
            display: inline-block;
            background-color: {color};
            color: white;
            border-radius: 999px;
            padding: 0.25rem 0.7rem;
            font-size: 0.8rem;
            font-weight: 600;
            line-height: 1.2;
            margin-right: 0.5rem;
        ">{rel}</span>
        """,
        unsafe_allow_html=True,
    )


def render_trace_item(item: object) -> None:
    if isinstance(item, dict):
        their_message = item.get("their_message") or item.get("message") or item.get("text") or "No excerpt available"
        my_reply = item.get("my_reply") or item.get("reply")
        distance = item.get("distance")

        st.markdown("**Past dialogue match:**")
        st.code(their_message, language="text")
        if my_reply:
            st.markdown("**How you replied:**")
            st.code(my_reply, language="text")
        if distance is not None:
            st.caption(f"Cosine distance: {distance:.4f}")
        return

    if isinstance(item, str):
        st.code(item, language="text")
        return

    st.write(item)


st.set_page_config(page_title="WhatsApp Cruise Control Feed", page_icon="🚗", layout="wide")

if st_autorefresh is not None:
    st_autorefresh(interval=2000, key="console_live_feed")

st.title("🚗 WhatsApp Live Decision Feed")
st.caption("Live streaming incoming messages, safety gating, RAG retrieval trace, and AI responses")

mode_value = read_mode()
with st.sidebar:
    st.markdown("### ⚙️ Session Mode")
    new_mode = st.radio(
        "Current Operating Mode",
        ["DRY_RUN", "LIVE"],
        index=0 if mode_value == "DRY_RUN" else 1,
        help="DRY_RUN tests without sending WhatsApp messages; LIVE dispatches actual WhatsApp replies.",
    )
    if new_mode != mode_value:
        set_mode(new_mode)
        st.success(f"Mode changed to {new_mode}")
        st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Metrics")
    log_entries = load_logs()
    total_messages = len(log_entries)
    total_replies = sum(1 for entry in log_entries if str(entry.get("decision", "ignore")).lower() == "reply")
    total_ignored = total_messages - total_replies

    st.metric("Total Messages Processed", total_messages)
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Replies", total_replies)
    with col_m2:
        st.metric("Ignored", total_ignored)

    st.markdown("---")
    if st.button("🧹 Clear Feed Logs"):
        if LOG_PATH.exists():
            LOG_PATH.write_text("", encoding="utf-8")
        st.rerun()

if not log_entries:
    st.info("⏳ Waiting for messages from WhatsApp Baileys client... Send a message to your WhatsApp number to see it appear here in real-time.")
    st.stop()

for entry in log_entries:
    timestamp = entry.get("timestamp", "unknown")
    jid = entry.get("jid", "unknown")
    incoming_text = entry.get("text", "")
    relationship = str(entry.get("relationship", "unknown")).lower()
    decision = str(entry.get("decision", "ignore")).lower()
    reason = entry.get("reason", "no reason provided")
    reply = entry.get("reply")
    retrieval_trace = entry.get("retrieval_trace") or []

    with st.container():
        st.markdown("---")
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.caption(f"🕒 {timestamp} • 👤 `{jid}`")
        with cols[1]:
            render_relationship_badge(relationship)
        with cols[2]:
            if decision == "reply":
                st.markdown("<span style='color: #25d366; font-weight: 700; font-size: 16px;'>🟢 REPLY</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #8696a0; font-weight: 700; font-size: 16px;'>⚪ IGNORED</span>", unsafe_allow_html=True)

        if incoming_text:
            st.markdown(f"**Incoming Message:** `{incoming_text}`")
        st.write(f"**Gate Reason:** {reason}")

        if reply:
            st.markdown("**Generated Reply:**")
            st.info(reply)

        with st.expander("🔍 ChromaDB Retrieval Trace"):
            if not retrieval_trace:
                st.write("No retrieval trace available for this message.")
            else:
                for idx, item in enumerate(retrieval_trace, start=1):
                    st.markdown(f"**Match #{idx}**")
                    render_trace_item(item)
                    if idx < len(retrieval_trace):
                        st.markdown("---")
