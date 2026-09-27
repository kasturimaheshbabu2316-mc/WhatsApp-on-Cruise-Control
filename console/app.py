#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Glassmorphic Live Console (console/app.py).
A modern, frosted-glass dashboard providing live telemetry on incoming WhatsApp
messages, dual-brain persona synthesis, ChromaDB vector memory retrieval, and
real-time controls (DRY_RUN / LIVE, human pacing, kill switch).
"""

from __future__ import annotations

import html
import json
import os
import sys
import tempfile
import textwrap
from datetime import datetime
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
RELATIONSHIP_MAP_PATH = ROOT / "config" / "relationship_map.json"
CONN_STATUS_PATH = ROOT / "logs" / "connection_status.json"
QR_IMAGE_PATH = ROOT / "qr.png"

DEFAULT_SETTINGS = {
    "dry_run": False,
    "min_delay_seconds": 3,
    "max_delay_seconds": 10,
}

# --- Page Setup ---
st.set_page_config(
    page_title="Cruise Control // Glass Console",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

if st_autorefresh is not None:
    st_autorefresh(interval=2000, key="glass_live_feed")

# --- Glassmorphism Design Tokens & CSS ---
GLASS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-dark: #090d16;
    --glass-bg: rgba(255, 255, 255, 0.04);
    --glass-bg-hover: rgba(255, 255, 255, 0.07);
    --glass-border: rgba(255, 255, 255, 0.12);
    --glass-highlight: rgba(255, 255, 255, 0.22);
    --accent-emerald: #10b981;
    --accent-indigo: #6366f1;
    --accent-purple: #a855f7;
    --accent-rose: #f43f5e;
    --accent-cyan: #06b6d4;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
}

/* Vibrant Radial Mesh Background Behind Frosted Glass */
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg-dark) !important;
    background-image: 
        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.18) 0px, transparent 50%),
        radial-gradient(at 100% 0%, rgba(168, 85, 247, 0.15) 0px, transparent 50%),
        radial-gradient(at 50% 50%, rgba(6, 182, 212, 0.08) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.12) 0px, transparent 50%),
        radial-gradient(at 0% 100%, rgba(244, 63, 94, 0.12) 0px, transparent 50%) !important;
    background-attachment: fixed !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Translucent Frosted Sidebar */
[data-testid="stSidebar"] {
    background: rgba(13, 18, 30, 0.65) !important;
    backdrop-filter: blur(24px) saturate(190%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(190%) !important;
    border-right: 1px solid var(--glass-border) !important;
    box-shadow: 4px 0 30px rgba(0, 0, 0, 0.4) !important;
}

/* Typography Hierarchy */
h1, h2, h3 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

h1 {
    font-size: 2.2rem !important;
    background: linear-gradient(135deg, #ffffff 30%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem !important;
}

h2, h3 {
    color: #ffffff !important;
    font-size: 1.25rem !important;
}

/* Monospace & Code */
code, pre, [data-testid="stCode"] {
    font-family: 'JetBrains Mono', monospace !important;
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 8px !important;
    color: #38bdf8 !important;
    font-size: 0.85rem !important;
}

/* Primary Glass Card Container */
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(18px) saturate(180%);
    -webkit-backdrop-filter: blur(18px) saturate(180%);
    border: 1px solid var(--glass-border);
    border-top: 1px solid var(--glass-highlight);
    border-radius: 18px;
    padding: 22px 26px;
    margin-bottom: 22px;
    box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.35);
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.glass-card:hover {
    background: var(--glass-bg-hover);
    border-color: rgba(255, 255, 255, 0.22);
    box-shadow: 0 16px 40px -8px rgba(0, 0, 0, 0.5);
    transform: translateY(-2px);
}

/* Pill Badges */
.glass-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}

.badge-reply {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: #34d399;
}

.badge-ignore {
    background: rgba(244, 63, 94, 0.15);
    border: 1px solid rgba(244, 63, 94, 0.35);
    color: #fb7185;
}

.badge-rel {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #818cf8;
}

/* Frosted Interactive Buttons */
.stButton > button {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02)) !important;
    border: 1px solid var(--glass-border) !important;
    border-top: 1px solid var(--glass-highlight) !important;
    color: #ffffff !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    padding: 0.55rem 1.2rem !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.06)) !important;
    border-color: rgba(255, 255, 255, 0.3) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3) !important;
    transform: translateY(-1px) !important;
}

/* Emergency Kill Switch Button */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(244, 63, 94, 0.4), rgba(225, 29, 72, 0.2)) !important;
    border: 1px solid rgba(244, 63, 94, 0.5) !important;
    border-top: 1px solid rgba(255, 140, 160, 0.7) !important;
    color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(244, 63, 94, 0.25) !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, rgba(244, 63, 94, 0.6), rgba(225, 29, 72, 0.4)) !important;
    box-shadow: 0 8px 30px rgba(244, 63, 94, 0.45) !important;
}

/* Glass Inputs */
input, select {
    background: rgba(15, 23, 42, 0.5) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    backdrop-filter: blur(8px) !important;
}

input:focus {
    border-color: rgba(99, 102, 241, 0.6) !important;
    box-shadow: 0 0 14px rgba(99, 102, 241, 0.25) !important;
}

/* Metric Display Cards */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 14px !important;
    padding: 12px 18px !important;
    backdrop-filter: blur(12px) !important;
}

[data-testid="stMetricValue"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 800 !important;
    color: #ffffff !important;
    font-size: 1.8rem !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.02em !important;
}

/* Expander Styling */
[data-testid="stExpander"] {
    background: rgba(15, 23, 42, 0.35) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    margin-top: 10px !important;
}
</style>
"""
st.markdown(GLASS_CSS, unsafe_allow_html=True)


# --- Helpers & Atomic Settings ---
def load_settings() -> dict:
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
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=SETTINGS_PATH.parent, prefix="settings_", suffix=".tmp")
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


def load_logs() -> list[dict]:
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
                        jid = str(entry.get("jid", ""))
                        if jid.endswith("@newsletter") or jid == "status@broadcast":
                            continue
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return entries[-50:][::-1]


# --- Header Title & Status Bar ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("<h1>✨ Cruise Control &bull; Live Decision Console</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -6px;'>"
        "Retrieval-Grounded Persona Agent &bull; ChromaDB Semantic Memory &bull; Baileys Live Bridge"
        "</p>",
        unsafe_allow_html=True,
    )
with col_h2:
    st.markdown(
        f'<div style="text-align: right; padding: 8px 16px; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; backdrop-filter: blur(10px); font-size: 0.85rem; color: #cbd5e1;">'
        f'Engine: <span style="color: #34d399; font-weight: 600;">Active</span> &bull; <span>{datetime.now().strftime("%H:%M:%S")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# --- Emergency Kill Switch Banner ---
if KILL_SWITCH_PATH.exists():
    st.markdown(
        '<div style="background: linear-gradient(135deg, rgba(244, 63, 94, 0.2), rgba(225, 29, 72, 0.1)); border: 1px solid rgba(244, 63, 94, 0.4); border-top: 1px solid rgba(255, 140, 160, 0.6); border-radius: 16px; padding: 18px 24px; margin-bottom: 24px; backdrop-filter: blur(16px); box-shadow: 0 10px 30px rgba(244, 63, 94, 0.2);">'
        '<h3 style="color: #fda4af; margin: 0 0 6px 0;">🛑 Emergency Kill Switch Engaged</h3>'
        '<p style="margin: 0; color: #fecdd3; font-size: 0.9rem;">Autonomous processing is completely halted. No incoming WhatsApp messages will receive AI replies while this flag is active.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    col_k1, _ = st.columns([1, 4])
    with col_k1:
        if st.button("🟢 Clear Kill Switch & Resume", key="top_clear_kill", use_container_width=True):
            KILL_SWITCH_PATH.unlink(missing_ok=True)
            st.rerun()

# --- Frosted Sidebar Controls ---
current_settings = load_settings()
is_dry = bool(current_settings.get("dry_run", False))
min_delay = int(current_settings.get("min_delay_seconds", 3))
max_delay = int(current_settings.get("max_delay_seconds", 10))

with st.sidebar:
    st.markdown("### 📱 WhatsApp Uplink")

    # Connection Status Card
    conn_info = {}
    if CONN_STATUS_PATH.exists():
        try:
            conn_info = json.loads(CONN_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if conn_info.get("connected"):
        user_phone = conn_info.get("phone", "LINKED_DEVICE")
        st.markdown(
            f'<div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.05)); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 14px; padding: 12px 16px; margin-bottom: 14px; backdrop-filter: blur(12px);">'
            f'<div style="font-size: 0.8rem; font-weight: 700; color: #34d399; text-transform: uppercase;">🟢 Connected & Ready</div>'
            f'<div style="font-size: 1rem; font-weight: 600; color: #ffffff; margin-top: 4px;">+{user_phone}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif QR_IMAGE_PATH.exists():
        st.markdown(
            '<div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 14px; padding: 12px; margin-bottom: 14px; text-align: center;">'
            '<span style="font-size: 0.85rem; font-weight: 600; color: #38bdf8;">📷 Scan Pairing QR</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.image(str(QR_IMAGE_PATH), caption="WhatsApp > Linked Devices > Link a Device", use_container_width=True)

    # Emergency Kill Switch
    st.markdown("### 🛑 Safety Controls")
    if KILL_SWITCH_PATH.exists():
        st.warning("Kill switch is active.")
        if st.button("🟢 Resume System", key="sidebar_clear_kill", use_container_width=True):
            KILL_SWITCH_PATH.unlink(missing_ok=True)
            st.rerun()
    else:
        if st.button(
            "🛑 KILL SWITCH",
            type="primary",
            use_container_width=True,
            help="Halts message processing across Baileys and Python Bridge instantly",
        ):
            KILL_SWITCH_PATH.write_text("", encoding="utf-8")
            st.rerun()

    st.markdown("---")
    st.markdown("### 👥 Allowlisted Contacts")
    rel_map = {}
    if RELATIONSHIP_MAP_PATH.exists():
        try:
            rel_map = json.loads(RELATIONSHIP_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    allowed_numbers = [k for k, v in rel_map.items() if k != "_default" and v != "unknown"]
    for num in allowed_numbers:
        st.markdown(
            f"<div style='font-size: 0.85rem; color: #cbd5e1; padding: 3px 0;'>"
            f"📞 <code>+{num}</code> <span style='color: #818cf8;'>({rel_map.get(num, 'friend')})</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    new_phone = st.text_input("Add Contact Phone", placeholder="e.g. 919100240439")
    if st.button("➕ Allow Number", use_container_width=True):
        cleaned = "".join(filter(str.isdigit, new_phone))
        if cleaned:
            rel_map[cleaned] = "friend"
            RELATIONSHIP_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
            RELATIONSHIP_MAP_PATH.write_text(json.dumps(rel_map, indent=2), encoding="utf-8")
            Path("relationship_map.json").write_text(json.dumps(rel_map, indent=2), encoding="utf-8")
            st.success(f"Added +{cleaned} to allowlist!")
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Dispatch Parameters")

    mode_selection = st.radio(
        "Operating Mode",
        ["LIVE", "DRY_RUN"],
        index=0 if not is_dry else 1,
        help="LIVE: Sends actual WhatsApp replies. DRY_RUN: Simulates decisions safely without sending.",
    )
    new_dry_run = (mode_selection == "DRY_RUN")
    if new_dry_run != is_dry:
        current_settings["dry_run"] = new_dry_run
        save_settings(current_settings)
        st.success(f"Mode set to {mode_selection}!")
        st.rerun()

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        new_min_delay = st.number_input("Min Delay (s)", min_value=1, max_value=60, value=min_delay)
    with col_d2:
        new_max_delay = st.number_input("Max Delay (s)", min_value=1, max_value=60, value=max_delay)

    if new_min_delay < new_max_delay and (new_min_delay != min_delay or new_max_delay != max_delay):
        current_settings["min_delay_seconds"] = int(new_min_delay)
        current_settings["max_delay_seconds"] = int(new_max_delay)
        save_settings(current_settings)
        st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Activity Metrics")
    log_entries = load_logs()
    total_messages = len(log_entries)
    total_replies = sum(1 for e in log_entries if str(e.get("decision", "ignore")).lower() == "reply")
    total_ignored = total_messages - total_replies

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Delivered", total_replies)
    with col_m2:
        st.metric("Ignored", total_ignored)

    if st.button("🧹 Clear Live Feed", use_container_width=True):
        if LOG_PATH.exists():
            LOG_PATH.write_text("", encoding="utf-8")
        st.rerun()

# --- Main Live Stream Feed ---
st.markdown("### 💬 Live Message Stream")

if not log_entries:
    st.markdown(
        '<div class="glass-card" style="text-align: center; padding: 48px 24px;">'
        '<div style="font-size: 2rem; margin-bottom: 10px;">✨</div>'
        '<h3 style="color: #ffffff; margin-bottom: 8px;">Waiting for Messages</h3>'
        '<p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">'
        'The Baileys WhatsApp client is active. Send a message to your WhatsApp number to watch the decision engine process it live.'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

for entry in log_entries:
    timestamp = entry.get("timestamp", "unknown")
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M:%S")
    except Exception:
        time_str = str(timestamp)[:19] if len(str(timestamp)) >= 19 else str(timestamp)

    jid = entry.get("jid", "unknown")
    incoming_text = entry.get("text", "")
    relationship = str(entry.get("relationship", "unknown")).lower()
    decision = str(entry.get("decision", "ignore")).lower()
    reason = entry.get("reason", "no reason provided")
    reply = entry.get("reply")
    retrieval_trace = entry.get("retrieval_trace") or []

    badge_class = "badge-reply" if decision == "reply" else "badge-ignore"
    decision_text = "🟢 Replied" if decision == "reply" else "⚪ Ignored"

    safe_jid = html.escape(str(jid))
    safe_time = html.escape(str(time_str))
    safe_text = html.escape(str(incoming_text)) if incoming_text else '<em style="color: #64748b;">[No text payload / media attachment]</em>'
    safe_reason = html.escape(str(reason))
    safe_rel = html.escape(str(relationship).upper())
    reason_color = "#34d399" if decision == "reply" else "#fb7185"

    reply_block = ""
    if reply:
        safe_reply = html.escape(str(reply))
        reply_block = (
            f'<div style="background: linear-gradient(135deg, rgba(99, 102, 241, 0.14), rgba(168, 85, 247, 0.08)); '
            f'border-left: 3px solid #818cf8; border-radius: 0 12px 12px 0; padding: 12px 18px; margin: 14px 0 6px 0;">'
            f'<div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: #a5b4fc; letter-spacing: 0.04em; margin-bottom: 4px;">'
            f'✨ Generated Persona Reply (Gemini)'
            f'</div>'
            f'<div style="font-size: 1.05rem; color: #ffffff; font-weight: 500;">'
            f'{safe_reply}'
            f'</div>'
            f'</div>'
        )

    card_html = (
        f'<div class="glass-card">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 10px;">'
        f'<div style="font-size: 0.85rem; color: #94a3b8;">'
        f'🕒 {safe_time} &bull; 👤 <code>{safe_jid}</code>'
        f'</div>'
        f'<div>'
        f'<span class="glass-badge badge-rel">{safe_rel}</span>&nbsp;'
        f'<span class="glass-badge {badge_class}">{decision_text}</span>'
        f'</div>'
        f'</div>'
        f'<div style="margin-bottom: 12px;">'
        f'<div style="font-size: 0.78rem; font-weight: 600; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.04em; margin-bottom: 4px;">'
        f'Incoming Message'
        f'</div>'
        f'<div style="font-size: 1.18rem; color: #f8fafc; font-weight: 600; margin: 4px 0 8px 0; line-height: 1.4;">'
        f'{safe_text}'
        f'</div>'
        f'<div style="font-size: 0.85rem; color: #94a3b8;">'
        f'Gate Reason: <span style="color: {reason_color}; font-weight: 500;">{safe_reason}</span>'
        f'</div>'
        f'</div>'
        f'{reply_block}'
        f'</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)

    if retrieval_trace:
        with st.expander(f"🔍 ChromaDB Vector Memory ({len(retrieval_trace)} dialogue matches)"):
            for idx, item in enumerate(retrieval_trace, start=1):
                if isinstance(item, dict):
                    their_msg = item.get("their_message") or item.get("message") or "N/A"
                    my_rep = item.get("my_reply") or item.get("reply") or "N/A"
                    dist = item.get("distance")
                    st.markdown(f"**Dialogue Match #{idx}**")
                    st.code(f"Contact: {their_msg}\nYou:     {my_rep}", language="text")
                    if dist is not None:
                        st.caption(f"Cosine Distance: {dist:.4f}")
                else:
                    st.write(item)
