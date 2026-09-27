#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Professional Glassmorphic Command Center (console/app.py).
Designed with a state-of-the-art Glassmorphic UI design system, frosted blur panels,
live WhatsApp message stream, interactive AI simulator sandbox, allowlist manager,
and safety controls.
"""

from __future__ import annotations

import html
import json
import os
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "logs" / "console_feed.jsonl"
SETTINGS_PATH = ROOT / "config" / "settings.json"
KILL_SWITCH_PATH = ROOT / "kill_switch.flag"
RELATIONSHIP_MAP_PATH = ROOT / "config" / "relationship_map.json"
CONN_STATUS_PATH = ROOT / "logs" / "connection_status.json"
QR_IMAGE_PATH = ROOT / "qr.png"
PERSONA_PATH = ROOT / "persona" / "persona.json"
BRIDGE_URL = "http://localhost:5001"

DEFAULT_SETTINGS = {
    "dry_run": True,
    "min_delay_seconds": 3,
    "max_delay_seconds": 10,
}

# --- Page Setup & Modern Meta ---
st.set_page_config(
    page_title="Cruise Control // Autonomous WhatsApp Hub",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

if st_autorefresh is not None:
    st_autorefresh(interval=2500, key="glass_live_autorefresh")

# --- Glassmorphism Design Tokens & CSS Architecture ---
GLASS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Outfit:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-dark: #070a13;
    --glass-bg: rgba(255, 255, 255, 0.035);
    --glass-bg-hover: rgba(255, 255, 255, 0.065);
    --glass-card-bg: rgba(18, 24, 38, 0.65);
    --glass-border: rgba(255, 255, 255, 0.10);
    --glass-border-light: rgba(255, 255, 255, 0.18);
    --glass-highlight: rgba(255, 255, 255, 0.25);
    --accent-emerald: #10b981;
    --accent-indigo: #6366f1;
    --accent-violet: #8b5cf6;
    --accent-cyan: #06b6d4;
    --accent-rose: #f43f5e;
    --accent-amber: #f59e0b;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
}

/* Radiant Ambient Mesh Backdrop */
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg-dark) !important;
    background-image: 
        radial-gradient(at 10% 10%, rgba(99, 102, 241, 0.20) 0px, transparent 45%),
        radial-gradient(at 90% 12%, rgba(139, 92, 246, 0.18) 0px, transparent 45%),
        radial-gradient(at 50% 50%, rgba(6, 182, 212, 0.09) 0px, transparent 50%),
        radial-gradient(at 88% 88%, rgba(16, 185, 129, 0.14) 0px, transparent 50%),
        radial-gradient(at 12% 88%, rgba(244, 63, 94, 0.12) 0px, transparent 50%) !important;
    background-attachment: fixed !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Translucent Frosted Glass Sidebar */
[data-testid="stSidebar"] {
    background: rgba(10, 15, 26, 0.72) !important;
    backdrop-filter: blur(28px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(28px) saturate(200%) !important;
    border-right: 1px solid var(--glass-border) !important;
    box-shadow: 4px 0 32px rgba(0, 0, 0, 0.45) !important;
}

/* Sleek Navigation Tabs */
[data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.035) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 16px !important;
    padding: 6px !important;
    gap: 8px !important;
    backdrop-filter: blur(18px) !important;
    -webkit-backdrop-filter: blur(18px) !important;
    margin-bottom: 24px !important;
}

[data-baseweb="tab"] {
    border-radius: 12px !important;
    padding: 8px 18px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    color: var(--text-secondary) !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.25s ease !important;
}

[data-baseweb="tab"]:hover {
    color: #ffffff !important;
    background: rgba(255, 255, 255, 0.05) !important;
}

[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.28), rgba(139, 92, 246, 0.22)) !important;
    color: #ffffff !important;
    border: 1px solid rgba(139, 92, 246, 0.45) !important;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25) !important;
}

/* Glass Card Architecture */
.glass-panel {
    background: var(--glass-card-bg);
    backdrop-filter: blur(22px) saturate(180%);
    -webkit-backdrop-filter: blur(22px) saturate(180%);
    border: 1px solid var(--glass-border);
    border-top: 1px solid var(--glass-highlight);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 14px 40px -10px rgba(0, 0, 0, 0.45);
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.glass-panel:hover {
    border-color: var(--glass-border-light);
    box-shadow: 0 18px 48px -10px rgba(0, 0, 0, 0.6);
}

/* Metric Display Blocks */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.035) !important;
    border: 1px solid var(--glass-border) !important;
    border-top: 1px solid rgba(255, 255, 255, 0.2) !important;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    backdrop-filter: blur(16px) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25) !important;
}

[data-testid="stMetricValue"] {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    font-size: 1.9rem !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
}

/* Buttons */
.stButton > button {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03)) !important;
    border: 1px solid var(--glass-border) !important;
    border-top: 1px solid var(--glass-highlight) !important;
    color: #ffffff !important;
    backdrop-filter: blur(14px) !important;
    padding: 0.55rem 1.25rem !important;
    transition: all 0.22s ease !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2) !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.06)) !important;
    border-color: rgba(255, 255, 255, 0.35) !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35) !important;
    transform: translateY(-1px) !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(244, 63, 94, 0.45), rgba(225, 29, 72, 0.25)) !important;
    border: 1px solid rgba(244, 63, 94, 0.6) !important;
    border-top: 1px solid rgba(255, 160, 180, 0.8) !important;
    color: #ffffff !important;
    box-shadow: 0 6px 22px rgba(244, 63, 94, 0.3) !important;
}

/* Input Fields */
input, select, textarea {
    background: rgba(15, 23, 42, 0.55) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    color: #ffffff !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    backdrop-filter: blur(12px) !important;
}

input:focus, select:focus, textarea:focus {
    border-color: rgba(99, 102, 241, 0.7) !important;
    box-shadow: 0 0 16px rgba(99, 102, 241, 0.25) !important;
}

/* Monospace & Code */
code, pre, [data-testid="stCode"] {
    font-family: 'JetBrains Mono', monospace !important;
    background: rgba(15, 23, 42, 0.7) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 10px !important;
    color: #38bdf8 !important;
    font-size: 0.84rem !important;
}

/* Expander Containers */
[data-testid="stExpander"] {
    background: rgba(15, 23, 42, 0.4) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 14px !important;
    margin-top: 10px !important;
}

/* Pill Badges */
.glass-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.badge-reply {
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
}

.badge-ignore {
    background: rgba(244, 63, 94, 0.16);
    border: 1px solid rgba(244, 63, 94, 0.4);
    color: #fb7185;
}

.badge-friend {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: #a5b4fc;
}

.badge-family {
    background: rgba(245, 158, 11, 0.16);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #fcd34d;
}

.badge-vip {
    background: rgba(236, 72, 153, 0.16);
    border: 1px solid rgba(236, 72, 153, 0.4);
    color: #f472b6;
}

.badge-unknown {
    background: rgba(100, 116, 139, 0.2);
    border: 1px solid rgba(100, 116, 139, 0.4);
    color: #94a3b8;
}

/* Chat Bubble Container */
.wa-chat-window {
    background: rgba(11, 17, 28, 0.65);
    background-image: radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px);
    background-size: 24px 24px;
    border: 1px solid var(--glass-border);
    border-radius: 18px;
    padding: 20px;
    margin: 14px 0;
}

.bubble-in {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px 16px 16px 3px;
    padding: 12px 18px;
    max-width: 80%;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.bubble-out {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.22), rgba(6, 182, 212, 0.15));
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-top: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 16px 16px 3px 16px;
    padding: 12px 18px;
    max-width: 80%;
    margin-left: auto;
    margin-top: 8px;
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.15);
}
</style>
"""
st.markdown(GLASS_CSS, unsafe_allow_html=True)


# --- Atomic Persistence Helpers ---
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


def load_relationship_map() -> dict[str, str]:
    for path_candidate in [RELATIONSHIP_MAP_PATH, ROOT / "relationship_map.json"]:
        if path_candidate.exists():
            try:
                data = json.loads(path_candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return {"_default": "unknown"}


def save_relationship_map(mapping: dict[str, str]) -> None:
    RELATIONSHIP_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(mapping, indent=2)
    RELATIONSHIP_MAP_PATH.write_text(serialized, encoding="utf-8")
    root_map = ROOT / "relationship_map.json"
    root_map.write_text(serialized, encoding="utf-8")


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
    return entries[-60:][::-1]


def load_persona_data() -> dict:
    if PERSONA_PATH.exists():
        try:
            return json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# --- Header Title & Real-Time Status Bar ---
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown(
        '<h1 style="font-family: \'Outfit\', sans-serif; font-size: 2.2rem; font-weight: 800; '
        'background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%); '
        '-webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 2px;">'
        '✨ WhatsApp on Cruise Control</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color: #94a3b8; font-size: 0.95rem; margin-top: -4px;">'
        'Autonomous AI Personal Messaging Engine &bull; Dual-Brain Architecture &bull; Retrieval-Grounded Persona'
        '</p>',
        unsafe_allow_html=True,
    )
with col_head2:
    st.markdown(
        f'<div style="text-align: right; padding: 10px 18px; background: rgba(255, 255, 255, 0.04); '
        f'border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 14px; backdrop-filter: blur(14px); '
        f'font-size: 0.85rem; color: #cbd5e1; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">'
        f'Engine: <span style="color: #34d399; font-weight: 700;">Active 🟢</span> &bull; '
        f'<span style="font-family: \'JetBrains Mono\';">{datetime.now().strftime("%H:%M:%S")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# --- Emergency Kill Switch Banner ---
if KILL_SWITCH_PATH.exists():
    st.markdown(
        '<div style="background: linear-gradient(135deg, rgba(244, 63, 94, 0.25), rgba(225, 29, 72, 0.15)); '
        'border: 1px solid rgba(244, 63, 94, 0.5); border-top: 1px solid rgba(255, 140, 160, 0.7); '
        'border-radius: 18px; padding: 18px 24px; margin-bottom: 24px; backdrop-filter: blur(18px); '
        'box-shadow: 0 10px 30px rgba(244, 63, 94, 0.25);">'
        '<h3 style="color: #fda4af; margin: 0 0 6px 0;">🛑 Emergency Kill Switch Engaged</h3>'
        '<p style="margin: 0; color: #fecdd3; font-size: 0.92rem;">'
        'Autonomous replies are completely frozen. Incoming messages will not be answered while this flag is active.'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    col_k1, _ = st.columns([1, 4])
    with col_k1:
        if st.button("🟢 Disengage Kill Switch & Resume", key="top_clear_kill", use_container_width=True):
            KILL_SWITCH_PATH.unlink(missing_ok=True)
            st.rerun()

# --- Sidebar: WhatsApp Uplink & Direct Controls ---
current_settings = load_settings()
is_dry = bool(current_settings.get("dry_run", True))
min_delay = int(current_settings.get("min_delay_seconds", 3))
max_delay = int(current_settings.get("max_delay_seconds", 10))

with st.sidebar:
    st.markdown("### 📱 WhatsApp Uplink")

    # Connection Status Detection
    conn_info = {}
    if CONN_STATUS_PATH.exists():
        try:
            conn_info = json.loads(CONN_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    is_connected = bool(conn_info.get("connected", False))

    if is_connected:
        user_phone = conn_info.get("phone", "LINKED_DEVICE")
        st.markdown(
            f'<div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.18), rgba(5, 150, 105, 0.08)); '
            f'border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 16px; padding: 14px 18px; margin-bottom: 16px; '
            f'backdrop-filter: blur(14px); box-shadow: 0 4px 18px rgba(16, 185, 129, 0.15);">'
            f'<div style="display: flex; align-items: center; justify-content: space-between;">'
            f'<span style="font-size: 0.78rem; font-weight: 700; color: #34d399; letter-spacing: 0.04em;">UPLINK ONLINE</span>'
            f'<span style="height: 10px; width: 10px; background-color: #34d399; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px #34d399;"></span>'
            f'</div>'
            f'<div style="font-size: 1.12rem; font-weight: 700; color: #ffffff; margin-top: 6px; font-family: \'JetBrains Mono\';">+{user_phone}</div>'
            f'<div style="font-size: 0.78rem; color: #94a3b8; margin-top: 2px;">Session paired & listening</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif QR_IMAGE_PATH.exists():
        st.markdown(
            '<div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.16); '
            'border-radius: 16px; padding: 14px; margin-bottom: 16px; text-align: center;">'
            '<span style="font-size: 0.88rem; font-weight: 700; color: #38bdf8;">📷 Scan WhatsApp QR to Link</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.image(str(QR_IMAGE_PATH), caption="WhatsApp > Linked Devices > Link a Device", use_container_width=True)
    else:
        st.markdown(
            '<div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3); '
            'border-radius: 14px; padding: 12px 16px; margin-bottom: 16px;">'
            '<span style="font-size: 0.82rem; color: #fcd34d; font-weight: 600;">🟡 Baileys Client Initializing...</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Master Mode Toggle
    st.markdown("### 🎛️ Operational Mode")
    mode_selection = st.radio(
        "Autonomous Mode",
        ["DRY_RUN (Safe / Log Only)", "LIVE (Active Dispatch)"],
        index=0 if is_dry else 1,
        help="DRY_RUN logs decisions without sending WhatsApp replies. LIVE sends autonomous replies.",
    )
    new_dry_run = "DRY_RUN" in mode_selection
    if new_dry_run != is_dry:
        current_settings["dry_run"] = new_dry_run
        save_settings(current_settings)
        st.success(f"Mode updated to: {'DRY_RUN' if new_dry_run else 'LIVE'}")
        st.rerun()

    st.markdown("---")

    # Safety Kill Switch
    st.markdown("### 🛑 Emergency Guard")
    if KILL_SWITCH_PATH.exists():
        st.error("Kill Switch is ENGAGED")
        if st.button("🟢 Resume System", key="side_resume", use_container_width=True):
            KILL_SWITCH_PATH.unlink(missing_ok=True)
            st.rerun()
    else:
        if st.button(
            "🛑 ENGAGE KILL SWITCH",
            type="primary",
            use_container_width=True,
            help="Halts message processing across Baileys and Python Bridge instantly",
        ):
            KILL_SWITCH_PATH.write_text("", encoding="utf-8")
            st.rerun()

    st.markdown("---")

    # Delay Pacing
    st.markdown("### ⏱️ Human Typing Delays")
    with st.form("delay_settings_form"):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            form_min = st.number_input("Min (s)", min_value=1, max_value=60, value=min_delay)
        with col_s2:
            form_max = st.number_input("Max (s)", min_value=1, max_value=60, value=max_delay)
        if st.form_submit_button("Save Pacing", use_container_width=True):
            if form_min <= form_max:
                current_settings["min_delay_seconds"] = int(form_min)
                current_settings["max_delay_seconds"] = int(form_max)
                save_settings(current_settings)
                st.success("Typing pacing updated!")
                st.rerun()
            else:
                st.error("Min delay cannot exceed Max delay.")


# --- Metrics Overview Bar ---
log_entries = load_logs()
total_messages = len(log_entries)
total_replies = sum(1 for e in log_entries if str(e.get("decision", "ignore")).lower() == "reply")
total_ignored = total_messages - total_replies
reply_ratio = f"{round((total_replies / total_messages) * 100)}%" if total_messages > 0 else "0%"

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Total Transmissions", total_messages)
with col_m2:
    st.metric("Auto-Replied", total_replies)
with col_m3:
    st.metric("Filtered / Ignored", total_ignored)
with col_m4:
    st.metric("Autonomous Ratio", reply_ratio)

# --- Top Navigation Tabs ---
tab_feed, tab_sim, tab_contacts, tab_persona, tab_settings = st.tabs([
    "📡 Live Message Stream",
    "🧪 AI Simulator Playground",
    "👥 Contact Allowlist Vault",
    "🧠 Persona & Memory Profile",
    "⚙️ Engine Diagnostics",
])


# ==============================================================================
# TAB 1: LIVE MESSAGE STREAM
# ==============================================================================
with tab_feed:
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_query = st.text_input("🔍 Search message content or contact phone", placeholder="Filter by text, phone, or reason...")
    with col_f2:
        filter_status = st.selectbox("Filter Status", ["All Transmissions", "Replied Only", "Ignored Only"])
    with col_f3:
        st.write("")
        st.write("")
        if st.button("🧹 Clear Feed", use_container_width=True):
            if LOG_PATH.exists():
                LOG_PATH.write_text("", encoding="utf-8")
            st.rerun()

    # Filter logic
    filtered_entries = []
    for e in log_entries:
        dec = str(e.get("decision", "ignore")).lower()
        if filter_status == "Replied Only" and dec != "reply":
            continue
        if filter_status == "Ignored Only" and dec == "reply":
            continue
        if search_query:
            query = search_query.lower()
            text_match = query in str(e.get("text", "")).lower()
            jid_match = query in str(e.get("jid", "")).lower()
            reason_match = query in str(e.get("reason", "")).lower()
            if not (text_match or jid_match or reason_match):
                continue
        filtered_entries.append(e)

    if not filtered_entries:
        st.markdown(
            '<div class="glass-panel" style="text-align: center; padding: 48px 20px;">'
            '<div style="font-size: 2.2rem; margin-bottom: 10px;">✨</div>'
            '<h3 style="color: #ffffff; margin-bottom: 6px;">No Messages in Stream</h3>'
            '<p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">'
            'Send a WhatsApp message to your paired device to observe live decision gating, ChromaDB recall, and Gemini synthesis.'
            '</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for entry in filtered_entries:
            timestamp = entry.get("timestamp", "unknown")
            try:
                dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                time_str = str(timestamp)[:19] if len(str(timestamp)) >= 19 else str(timestamp)

            jid = str(entry.get("jid", "unknown"))
            phone_num = jid.split("@", 1)[0]
            incoming_text = entry.get("text", "")
            relationship = str(entry.get("relationship", "unknown")).lower()
            decision = str(entry.get("decision", "ignore")).lower()
            reason = entry.get("reason", "no reason provided")
            reply = entry.get("reply")
            retrieval_trace = entry.get("retrieval_trace") or []

            badge_class = "badge-reply" if decision == "reply" else "badge-ignore"
            decision_text = "🟢 Replied" if decision == "reply" else "⚪ Ignored"

            rel_class = f"badge-{relationship}" if relationship in ["friend", "family", "vip"] else "badge-unknown"

            safe_jid = html.escape(jid)
            safe_phone = html.escape(phone_num)
            safe_time = html.escape(time_str)
            safe_text = html.escape(str(incoming_text)) if incoming_text else '<em style="color: #64748b;">[Media attachment / empty payload]</em>'
            safe_reason = html.escape(str(reason))
            safe_rel = html.escape(relationship.upper())
            reason_color = "#34d399" if decision == "reply" else "#fb7185"

            # Outgoing reply block (WhatsApp bubble style)
            reply_block = ""
            if reply:
                safe_reply = html.escape(str(reply))
                reply_block = (
                    f'<div class="bubble-out">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">'
                    f'<span style="font-size: 0.72rem; font-weight: 700; color: #a7f3d0; letter-spacing: 0.03em;">✨ GEMINI PERSONA REPLY</span>'
                    f'<span style="font-size: 0.72rem; color: #6ee7b7; font-family: \'JetBrains Mono\';">✓✓ Delivered</span>'
                    f'</div>'
                    f'<div style="font-size: 1.05rem; color: #ffffff; font-weight: 500; line-height: 1.4;">{safe_reply}</div>'
                    f'</div>'
                )

            # Master WhatsApp Card
            card_html = (
                f'<div class="glass-panel">'
                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 10px;">'
                f'<div style="display: flex; align-items: center; gap: 10px;">'
                f'<div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #6366f1, #8b5cf6); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; color: white;">{safe_phone[:2]}</div>'
                f'<div>'
                f'<div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; font-family: \'JetBrains Mono\';">+{safe_phone}</div>'
                f'<div style="font-size: 0.75rem; color: #94a3b8;">🕒 {safe_time} &bull; JID: {safe_jid}</div>'
                f'</div>'
                f'</div>'
                f'<div style="display: flex; gap: 8px;">'
                f'<span class="glass-badge {rel_class}">{safe_rel}</span>'
                f'<span class="glass-badge {badge_class}">{decision_text}</span>'
                f'</div>'
                f'</div>'
                f'<div class="wa-chat-window">'
                f'<div class="bubble-in">'
                f'<div style="font-size: 0.72rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">Incoming Message</div>'
                f'<div style="font-size: 1.15rem; color: #f8fafc; font-weight: 600; line-height: 1.4;">{safe_text}</div>'
                f'<div style="font-size: 0.78rem; color: #94a3b8; margin-top: 6px;">Gate Evaluation: <span style="color: {reason_color}; font-weight: 600;">{safe_reason}</span></div>'
                f'</div>'
                f'{reply_block}'
                f'</div>'
                f'</div>'
            )

            st.markdown(card_html, unsafe_allow_html=True)

            if retrieval_trace:
                with st.expander(f"🔍 ChromaDB Dialogue Context ({len(retrieval_trace)} Semantic Memory Matches)"):
                    for idx, item in enumerate(retrieval_trace, start=1):
                        if isinstance(item, dict):
                            their_msg = item.get("their_message") or item.get("message") or "N/A"
                            my_rep = item.get("my_reply") or item.get("reply") or "N/A"
                            dist = item.get("distance")
                            st.markdown(f"**Dialogue Pair #{idx}**")
                            st.code(f"Contact: {their_msg}\nYou:     {my_rep}", language="text")
                            if dist is not None:
                                st.caption(f"Cosine Semantic Distance: {dist:.4f}")


# ==============================================================================
# TAB 2: AI PERSONA SIMULATOR PLAYGROUND
# ==============================================================================
with tab_sim:
    st.markdown("### 🧪 Interactive AI Persona Simulator")
    st.markdown(
        '<p style="color: #94a3b8; font-size: 0.92rem; margin-top: -8px;">'
        'Test how the Cruise Control agent evaluates incoming messages and synthesizes in-character Telugu/English replies '
        'without sending any actual WhatsApp messages.'
        '</p>',
        unsafe_allow_html=True,
    )

    col_presets = st.columns(4)
    preset_choice = ""
    with col_presets[0]:
        if st.button("💬 Friendly Check-in", use_container_width=True):
            st.session_state["sim_text"] = "Rey em chesthunnav ra?"
            st.session_state["sim_rel"] = "friend"
    with col_presets[1]:
        if st.button("💰 Financial Loan Request", use_container_width=True):
            st.session_state["sim_text"] = "Bhai urgently need 5000 rs emergency loan please"
            st.session_state["sim_rel"] = "friend"
    with col_presets[2]:
        if st.button("🤐 Low-Signal Ack", use_container_width=True):
            st.session_state["sim_text"] = "Ok cool"
            st.session_state["sim_rel"] = "friend"
    with col_presets[3]:
        if st.button("📅 Urgent Plan Inquiry", use_container_width=True):
            st.session_state["sim_text"] = "Repu shoot ki osthava leka drop aa?"
            st.session_state["sim_rel"] = "friend"

    # Form keeps autorefresh from disrupting input
    with st.form("sim_playground_form"):
        sim_input = st.text_area(
            "Hypothetical Incoming Message",
            value=st.session_state.get("sim_text", "Em chesthundhi adhi"),
            placeholder="Type any message to test the AI persona...",
            height=100,
        )
        col_s1, col_s2 = st.columns([1, 1])
        with col_s1:
            sim_relation = st.selectbox(
                "Contact Relationship Tier",
                ["friend", "family", "colleague", "vip", "unknown"],
                index=["friend", "family", "colleague", "vip", "unknown"].index(
                    st.session_state.get("sim_rel", "friend")
                ),
            )
        with col_s2:
            st.write("")
            st.write("")
            run_sim = st.form_submit_button("🚀 Run Decision & Generation Pipeline", use_container_width=True)

    if run_sim and sim_input.strip():
        with st.spinner("Executing Two-Brain pipeline through Flask Bridge..."):
            try:
                payload = {
                    "jid": "simulator_test@s.whatsapp.net",
                    "text": sim_input.strip(),
                    "message_type": "text",
                    "is_forwarded": False,
                    "from_me": False,
                }
                # Directly invoke the live Python bridge
                res = requests.post(f"{BRIDGE_URL}/process", json=payload, timeout=20)
                if res.status_code == 200:
                    sim_res = res.json()
                    should_reply = sim_res.get("should_reply", False)
                    sim_reason = sim_res.get("reason", "no reason")
                    sim_reply = sim_res.get("reply")

                    st.markdown("#### 📊 Simulation Results")
                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        if should_reply:
                            st.success(f"Gate Decision: **APPROVED (Auto-Reply)**\n\nReason: *{sim_reason}*")
                        else:
                            st.warning(f"Gate Decision: **REJECTED (Ignored)**\n\nReason: *{sim_reason}*")
                    with col_res2:
                        if sim_reply:
                            st.markdown(
                                f'<div class="bubble-out" style="max-width: 100%;">'
                                f'<div style="font-size: 0.72rem; font-weight: 700; color: #a7f3d0; margin-bottom: 4px;">SYNTHESIZED REPLY (GEMINI 3.5 FLASH LITE)</div>'
                                f'<div style="font-size: 1.12rem; font-weight: 600; color: white;">{html.escape(sim_reply)}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.info("No reply generated because the message was filtered closed by safety gates.")
                else:
                    st.error(f"Bridge returned status code {res.status_code}: {res.text}")
            except Exception as sim_err:
                st.error(f"Could not reach Python Bridge at {BRIDGE_URL}: {sim_err}")


# ==============================================================================
# TAB 3: CONTACT ALLOWLIST VAULT
# ==============================================================================
with tab_contacts:
    st.markdown("### 👥 Contact Allowlist Manager")
    st.markdown(
        '<p style="color: #94a3b8; font-size: 0.92rem; margin-top: -8px;">'
        'Only allowlisted contacts receive autonomous AI replies. Any number not listed here is guarded and ignored.'
        '</p>',
        unsafe_allow_html=True,
    )

    rel_map = load_relationship_map()
    active_contacts = {k: v for k, v in rel_map.items() if k != "_default" and v != "unknown"}

    st.markdown(f"**Total Allowlisted Contacts:** `{len(active_contacts)}`")

    # Contact Cards Grid
    cols = st.columns(3)
    idx = 0
    for phone, rel in active_contacts.items():
        col = cols[idx % 3]
        with col:
            with st.container():
                st.markdown(
                    f'<div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--glass-border); '
                    f'border-radius: 16px; padding: 16px; margin-bottom: 14px;">'
                    f'<div style="display: flex; align-items: center; justify-content: space-between;">'
                    f'<div style="display: flex; align-items: center; gap: 10px;">'
                    f'<div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #10b981, #06b6d4); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; color: white;">{phone[:2]}</div>'
                    f'<div style="font-family: \'JetBrains Mono\'; font-weight: 700; color: #f8fafc;">+{phone}</div>'
                    f'</div>'
                    f'<span class="glass-badge badge-{rel}">{rel.upper()}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"🗑️ Remove +{phone}", key=f"del_{phone}", use_container_width=True):
                    del rel_map[phone]
                    save_relationship_map(rel_map)
                    st.success(f"Removed +{phone} from allowlist.")
                    st.rerun()
        idx += 1

    st.markdown("---")
    st.markdown("#### ➕ Add Contact to Allowlist")
    with st.form("add_contact_form"):
        col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
        with col_a1:
            new_num = st.text_input("Phone Number or WhatsApp LID", placeholder="e.g. 919100240439 or 149387720323301")
        with col_a2:
            new_tier = st.selectbox("Relationship Tier", ["friend", "family", "colleague", "vip"])
        with col_a3:
            st.write("")
            st.write("")
            submit_contact = st.form_submit_button("Add to Vault", use_container_width=True)

        if submit_contact:
            cleaned = "".join(filter(str.isdigit, new_num))
            if cleaned:
                rel_map[cleaned] = new_tier
                save_relationship_map(rel_map)
                st.success(f"Added +{cleaned} ({new_tier}) to allowlist!")
                st.rerun()
            else:
                st.error("Please enter a valid numeric phone number.")


# ==============================================================================
# TAB 4: PERSONA & SEMANTIC MEMORY VAULT
# ==============================================================================
with tab_persona:
    st.markdown("### 🧠 AI Persona Profile & Memory Vault")
    persona_data = load_persona_data()

    if persona_data:
        identity = persona_data.get("identity", "No identity defined")
        st.markdown(
            f'<div class="glass-panel">'
            f'<div style="font-size: 0.78rem; font-weight: 700; color: #a5b4fc; text-transform: uppercase; margin-bottom: 6px;">Core Identity Profile</div>'
            f'<div style="font-size: 1.12rem; color: #f8fafc; font-weight: 500; line-height: 1.5;">"{identity}"</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        relationships = persona_data.get("relationships", {})
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            friend_data = relationships.get("friend", {})
            st.markdown(
                f'<div class="glass-panel">'
                f'<h4>👫 1-on-1 Friend Persona</h4>'
                f'<p style="color: #94a3b8; font-size: 0.9rem;"><strong>Tone:</strong> {friend_data.get("tone", "N/A")}</p>'
                f'<p style="color: #94a3b8; font-size: 0.9rem;"><strong>Top Emojis:</strong> {" ".join(friend_data.get("top_emojis", []))}</p>'
                f'<p style="color: #94a3b8; font-size: 0.9rem;"><strong>Sample Replies:</strong></p>'
                f'<ul style="color: #cbd5e1; font-size: 0.88rem;">'
                + "".join([f"<li>{rep}</li>" for rep in friend_data.get("example_replies", [])])
                + f'</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_p2:
            group_data = relationships.get("group", {})
            st.markdown(
                f'<div class="glass-panel">'
                f'<h4>🔥 Group Chat Persona</h4>'
                f'<p style="color: #94a3b8; font-size: 0.9rem;"><strong>Tone:</strong> {group_data.get("tone", "N/A")}</p>'
                f'<p style="color: #94a3b8; font-size: 0.9rem;"><strong>Top Emojis:</strong> {" ".join(group_data.get("top_emojis", []))}</p>'
                f'<p style="color: #94a3b8; font-size: 0.9rem;"><strong>Sample Replies:</strong></p>'
                f'<ul style="color: #cbd5e1; font-size: 0.88rem;">'
                + "".join([f"<li>{rep}</li>" for rep in group_data.get("example_replies", [])])
                + f'</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Hard Rules
        hard_rules = persona_data.get("hard_rules", [])
        if hard_rules:
            st.markdown("#### 🛡️ Autonomous Hard Safety Boundaries")
            for rule in hard_rules:
                st.markdown(f"- 🛑 **{rule}**")


# ==============================================================================
# TAB 5: ENGINE DIAGNOSTICS & SYSTEM CONTROLS
# ==============================================================================
with tab_settings:
    st.markdown("### ⚙️ System Diagnostics & Infrastructure Health")

    # Service Health Checks
    bridge_online = False
    try:
        r = requests.get(f"{BRIDGE_URL}/health", timeout=2)
        bridge_online = (r.status_code == 200)
    except Exception:
        bridge_online = False

    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        st.markdown(
            f'<div class="glass-panel" style="text-align: center;">'
            f'<div style="font-size: 1.5rem;">🐍</div>'
            f'<h4 style="margin: 6px 0;">Python Flask Bridge</h4>'
            f'<span class="glass-badge {"badge-reply" if bridge_online else "badge-ignore"}">'
            f'{"ONLINE (PORT 5001)" if bridge_online else "OFFLINE"}'
            f'</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_h2:
        st.markdown(
            f'<div class="glass-panel" style="text-align: center;">'
            f'<div style="font-size: 1.5rem;">📱</div>'
            f'<h4 style="margin: 6px 0;">WhatsApp Baileys</h4>'
            f'<span class="glass-badge {"badge-reply" if is_connected else "badge-ignore"}">'
            f'{"CONNECTED" if is_connected else "WAITING FOR QR"}'
            f'</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_h3:
        st.markdown(
            f'<div class="glass-panel" style="text-align: center;">'
            f'<div style="font-size: 1.5rem;">🧠</div>'
            f'<h4 style="margin: 6px 0;">Gemini 3.5 Flash Lite</h4>'
            f'<span class="glass-badge badge-reply">ACTIVE (HIGH QUOTA)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("#### 📁 File Paths & Config References")
    st.code(
        f"Settings:         {SETTINGS_PATH}\n"
        f"Allowlist:        {RELATIONSHIP_MAP_PATH}\n"
        f"Console Feed Log: {LOG_PATH}\n"
        f"Persona File:     {PERSONA_PATH}\n"
        f"Kill Switch Flag: {KILL_SWITCH_PATH}",
        language="text",
    )
