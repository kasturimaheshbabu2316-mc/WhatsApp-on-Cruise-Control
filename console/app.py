#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Live Console Feed (console/app.py).
Displays live incoming WhatsApp messages, safety decisions, reasons,
generated AI responses, ChromaDB retrieval traces, and provides real-time
runtime controls for DRY_RUN/LIVE, randomized delays, and emergency kill-switch.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "logs" / "console_feed.jsonl"
MODE_PATH = ROOT / "config" / "mode.txt"
SETTINGS_PATH = ROOT / "config" / "settings.json"
KILL_SWITCH_PATH = ROOT / "kill_switch.flag"

DEFAULT_SETTINGS = {
    "dry_run": True,
    "min_delay_seconds": 3,
    "max_delay_seconds": 12,
}

RELATIONSHIP_COLORS = {
    "family": "#2e7d32",
    "friend": "#1565c0",
    "professional": "#6a1b9a",
    "unknown": "#6b7280",
    "group": "#6b7280",
}


def load_settings() -> dict:
    """Read config/settings.json safely, falling back to defaults on error."""
    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                merged = DEFAULT_SETTINGS.copy()
                merged.update(data)
                return merged
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()


def save_settings(new_settings: dict) -> None:
    """Atomic write to config/settings.json using temporary file rename."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    dir_path = SETTINGS_PATH.parent

    # Write to a temporary file in the same directory, then atomically replace
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix="settings_", suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, SETTINGS_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def set_mode_file(mode: str) -> None:
    """Synchronize with config/mode.txt for backward compatibility."""
    try:
        MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODE_PATH.write_text(mode.strip().upper() + "\n", encoding="utf-8")
    except Exception:
        pass


def load_logs() -> list[dict]:
    """Load the latest 50 decision feed log entries."""
    if not LOG_PATH.exists():
        return []

    entries: list[dict] = []
    try:
        with LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                    if isinstance(entry, dict):
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []

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


# --- Streamlit Page Setup ---
st.set_page_config(page_title="WhatsApp Cruise Control Feed", page_icon="🚗", layout="wide")

if st_autorefresh is not None:
    st_autorefresh(interval=2000, key="console_live_feed")

# --- Prominent Kill Switch Warning Banner ---
if KILL_SWITCH_PATH.exists():
    st.error(
        "🚨 **KILL SWITCH ENGAGED** — All autonomous processing is currently HALTED! "
        "No incoming WhatsApp messages will be processed or replied to while this flag exists."
    )
    col_k1, _ = st.columns([1, 4])
    with col_k1:
        if st.button("🟢 Clear Kill Switch & Resume", key="top_clear_kill", type="primary", use_container_width=True):
            try:
                KILL_SWITCH_PATH.unlink(missing_ok=True)
            except Exception as err:
                st.error(f"Failed to clear kill switch: {err}")
            st.rerun()

st.title("🚗 WhatsApp Live Decision Feed")
st.caption("Live streaming incoming messages, safety gating, RAG retrieval trace, and AI responses")

# --- Sidebar Runtime Controls ---
current_settings = load_settings()
is_dry = bool(current_settings.get("dry_run", True))
min_delay = int(current_settings.get("min_delay_seconds", 3))
max_delay = int(current_settings.get("max_delay_seconds", 12))

with st.sidebar:
    st.markdown("### 🛑 Emergency Control")
    if KILL_SWITCH_PATH.exists():
        st.warning("⚠️ Kill switch is currently ACTIVE.")
        if st.button("🟢 Clear Kill Switch", key="sidebar_clear_kill", use_container_width=True):
            try:
                KILL_SWITCH_PATH.unlink(missing_ok=True)
            except Exception as err:
                st.error(f"Error: {err}")
            st.rerun()
    else:
        if st.button(
            "🛑 KILL SWITCH",
            type="primary",
            use_container_width=True,
            help="Immediately halts all WhatsApp message processing across Baileys and Bridge",
        ):
            KILL_SWITCH_PATH.write_text("", encoding="utf-8")
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Operational Settings")

    # DRY_RUN vs LIVE mode toggle
    mode_selection = st.radio(
        "Current Operating Mode",
        ["DRY_RUN", "LIVE"],
        index=0 if is_dry else 1,
        help="DRY_RUN: Simulates decisions and logs replies without sending. LIVE: Actively dispatches WhatsApp messages.",
    )
    new_dry_run = (mode_selection == "DRY_RUN")
    if new_dry_run != is_dry:
        current_settings["dry_run"] = new_dry_run
        save_settings(current_settings)
        set_mode_file("DRY_RUN" if new_dry_run else "LIVE")
        st.success(f"Mode set to {'DRY_RUN' if new_dry_run else 'LIVE'}!")
        st.rerun()

    # Pre-send random delay range inputs
    st.markdown("#### ⏱️ Reply Delay Range")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        new_min_delay = st.number_input(
            "Min Delay (s)",
            min_value=1,
            max_value=120,
            value=min_delay,
            step=1,
            help="Minimum human-like delay before sending a reply",
        )
    with col_d2:
        new_max_delay = st.number_input(
            "Max Delay (s)",
            min_value=1,
            max_value=120,
            value=max_delay,
            step=1,
            help="Maximum human-like delay before sending a reply",
        )

    if new_min_delay >= new_max_delay:
        st.error("⚠️ Min delay must be strictly less than Max delay!")
    elif (new_min_delay != min_delay) or (new_max_delay != max_delay):
        current_settings["min_delay_seconds"] = int(new_min_delay)
        current_settings["max_delay_seconds"] = int(new_max_delay)
        save_settings(current_settings)
        st.success("Delay range updated!")
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
    if st.button("🧹 Clear Feed Logs", use_container_width=True):
        if LOG_PATH.exists():
            LOG_PATH.write_text("", encoding="utf-8")
        st.rerun()

# --- Main Live Stream ---
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
