#!/usr/bin/env python3
"""
WhatsApp Cruise Control - Cyberpunk Netrunner Console (console/app.py).
High-tech neural HUD interface displaying live incoming WhatsApp transmissions,
AI safety gating protocols, ChromaDB vector memory retrieval, and real-time
cybernetic runtime controls (DRY_RUN / LIVE, randomized pacing, emergency kill switch).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
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

# --- Page Setup & Cyberpunk HUD Meta ---
st.set_page_config(
    page_title="CRUISE CONTROL // NEURAL HUD",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

if st_autorefresh is not None:
    st_autorefresh(interval=2000, key="cyberpunk_live_feed")

# --- Custom Cyberpunk Styling Injection ---
CYBERPUNK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Orbitron:wght@600;800;900&family=Share+Tech+Mono&display=swap');

:root {
    --neon-cyan: #00f0ff;
    --neon-pink: #ff0055;
    --neon-yellow: #ffe600;
    --neon-green: #00ff66;
    --cyber-dark: #05060f;
    --cyber-panel: rgba(10, 14, 28, 0.85);
    --cyber-border: rgba(0, 240, 255, 0.35);
}

/* Overall Theme Overrides */
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--cyber-dark) !important;
    background-image: 
        radial-gradient(circle at 10% 20%, rgba(255, 0, 85, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(0, 240, 255, 0.08) 0%, transparent 40%),
        linear-gradient(rgba(5, 6, 15, 0.95), rgba(5, 6, 15, 0.95)),
        repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 240, 255, 0.02) 2px, rgba(0, 240, 255, 0.02) 4px) !important;
    color: #e0e6ed !important;
    font-family: 'Chakra Petch', sans-serif !important;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: rgba(6, 8, 20, 0.95) !important;
    border-right: 1px solid var(--cyber-border) !important;
    box-shadow: 2px 0 20px rgba(0, 240, 255, 0.15) !important;
}

/* Headings */
h1, h2, h3 {
    font-family: 'Orbitron', monospace !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}

h1 {
    color: var(--neon-cyan) !important;
    text-shadow: 0 0 10px rgba(0, 240, 255, 0.6), 0 0 25px rgba(0, 240, 255, 0.3) !important;
    font-size: 2.2rem !important;
}

h2, h3 {
    color: #ffffff !important;
    border-left: 3px solid var(--neon-pink);
    padding-left: 10px;
    margin-top: 15px !important;
}

/* Code & Monospace Blocks */
code, pre, [data-testid="stCode"] {
    font-family: 'Share Tech Mono', monospace !important;
    background-color: rgba(2, 4, 10, 0.8) !important;
    border: 1px solid rgba(0, 240, 255, 0.25) !important;
    color: var(--neon-cyan) !important;
}

/* Cyberpunk Card Container */
.cyber-card {
    background: var(--cyber-panel);
    border: 1px solid var(--cyber-border);
    clip-path: polygon(0 0, calc(100% - 15px) 0, 100% 15px, 100% 100%, 15px 100%, 0 calc(100% - 15px));
    box-shadow: 0 0 15px rgba(0, 240, 255, 0.08), inset 0 0 15px rgba(0, 240, 255, 0.03);
    padding: 18px 24px;
    margin-bottom: 20px;
    position: relative;
    backdrop-filter: blur(10px);
}

.cyber-card::before {
    content: "SYS.MSG // TRACE_OK";
    position: absolute;
    top: 3px;
    right: 18px;
    font-size: 0.65rem;
    color: rgba(0, 240, 255, 0.5);
    font-family: 'Share Tech Mono', monospace;
    letter-spacing: 1px;
}

/* Status Badges */
.cyber-badge {
    display: inline-block;
    padding: 3px 10px;
    font-family: 'Orbitron', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    border: 1px solid;
    clip-path: polygon(0 0, calc(100% - 6px) 0, 100% 6px, 100% 100%, 6px 100%, 0 calc(100% - 6px));
}

.badge-reply {
    color: #00ff66;
    background: rgba(0, 255, 102, 0.12);
    border-color: #00ff66;
    box-shadow: 0 0 8px rgba(0, 255, 102, 0.3);
}

.badge-ignore {
    color: #ff0055;
    background: rgba(255, 0, 85, 0.12);
    border-color: #ff0055;
    box-shadow: 0 0 8px rgba(255, 0, 85, 0.3);
}

.badge-rel {
    color: var(--neon-cyan);
    background: rgba(0, 240, 255, 0.12);
    border-color: var(--neon-cyan);
    box-shadow: 0 0 8px rgba(0, 240, 255, 0.3);
}

/* Metric Display */
[data-testid="stMetricValue"] {
    font-family: 'Orbitron', monospace !important;
    color: var(--neon-cyan) !important;
    text-shadow: 0 0 10px rgba(0, 240, 255, 0.5) !important;
    font-size: 2rem !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'Share Tech Mono', monospace !important;
    color: #8899aa !important;
    text-transform: uppercase !important;
}

/* Buttons */
.stButton > button {
    font-family: 'Orbitron', monospace !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border: 1px solid var(--neon-cyan) !important;
    background: rgba(0, 240, 255, 0.1) !important;
    color: var(--neon-cyan) !important;
    border-radius: 0px !important;
    clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px)) !important;
    transition: all 0.25s ease-in-out !important;
}

.stButton > button:hover {
    background: var(--neon-cyan) !important;
    color: #000000 !important;
    box-shadow: 0 0 18px rgba(0, 240, 255, 0.8) !important;
}

/* Danger / Kill Switch Button */
.stButton > button[kind="primary"] {
    border-color: var(--neon-pink) !important;
    background: rgba(255, 0, 85, 0.2) !important;
    color: #ff3377 !important;
}

.stButton > button[kind="primary"]:hover {
    background: var(--neon-pink) !important;
    color: #ffffff !important;
    box-shadow: 0 0 20px rgba(255, 0, 85, 0.9) !important;
}

/* Input Fields */
input, select {
    background: rgba(4, 7, 18, 0.8) !important;
    border: 1px solid var(--cyber-border) !important;
    color: #ffffff !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #05060f;
}
::-webkit-scrollbar-thumb {
    background: var(--neon-cyan);
    box-shadow: 0 0 6px var(--neon-cyan);
}
</style>
"""
st.markdown(CYBERPUNK_CSS, unsafe_allow_html=True)


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
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return entries[-50:][::-1]


# --- Header Title & HUD Status ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("<h1>⚡ CRUISE CONTROL // NEURAL HUD</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-family: \"Share Tech Mono\", monospace; color: #00f0ff; letter-spacing: 1px;'>"
        "// PROTOCOL: AUTONOMOUS PERSONA GROUNDED ENGINE • DUAL-BRAIN ARCHITECTURE //"
        "</p>",
        unsafe_allow_html=True,
    )
with col_h2:
    st.markdown(
        f"<div style='text-align: right; padding-top: 15px; font-family: \"Share Tech Mono\", monospace; color: #8899aa;'>"
        f"SYS_TIME: <span style='color: #00f0ff;'>{datetime.now().strftime('%H:%M:%S')}</span><br>"
        f"GRID_STATUS: <span style='color: #00ff66;'>ONLINE</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

# --- Emergency Kill Switch Warning Banner ---
if KILL_SWITCH_PATH.exists():
    st.markdown(
        """
        <div style="
            background: rgba(255, 0, 85, 0.15);
            border: 2px solid #ff0055;
            box-shadow: 0 0 25px rgba(255, 0, 85, 0.4);
            padding: 16px 22px;
            margin-bottom: 25px;
            clip-path: polygon(0 0, calc(100% - 15px) 0, 100% 15px, 100% 100%, 15px 100%, 0 calc(100% - 15px));
        ">
            <h3 style="color: #ff0055 !important; margin: 0 0 5px 0; border: none; padding: 0;">
                ⚠️ EMERGENCY DISCONNECT ENGAGED // NEURAL KILL SWITCH ACTIVE
            </h3>
            <p style="margin: 0; color: #ff99bb; font-family: 'Share Tech Mono', monospace;">
                All incoming transmissions are actively dropped. No AI synthesis or WhatsApp replies will be dispatched.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_k1, _ = st.columns([1, 4])
    with col_k1:
        if st.button("🟢 RE-ENGAGE NEURAL PROTOCOL (CLEAR)", key="top_clear_kill", use_container_width=True):
            KILL_SWITCH_PATH.unlink(missing_ok=True)
            st.rerun()

# --- Sidebar Cyberpunk Controls ---
current_settings = load_settings()
is_dry = bool(current_settings.get("dry_run", False))
min_delay = int(current_settings.get("min_delay_seconds", 3))
max_delay = int(current_settings.get("max_delay_seconds", 10))

with st.sidebar:
    st.markdown("### 🔌 NEURAL UPLINK")

    # Connection Status
    conn_info = {}
    if CONN_STATUS_PATH.exists():
        try:
            conn_info = json.loads(CONN_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if conn_info.get("connected"):
        user_phone = conn_info.get("phone", "LINKED_DEVICE")
        st.markdown(
            f"""
            <div style="
                background: rgba(0, 255, 102, 0.1);
                border: 1px solid #00ff66;
                padding: 10px 14px;
                margin-bottom: 12px;
                box-shadow: 0 0 12px rgba(0, 255, 102, 0.2);
            ">
                <span style="color: #00ff66; font-family: 'Orbitron', monospace; font-size: 0.8rem; font-weight: 700;">
                    🟢 WHATSAPP LINKED
                </span><br>
                <code style="color: #ffffff !important;">+{user_phone}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif QR_IMAGE_PATH.exists():
        st.markdown(
            """
            <div style="background: rgba(0, 240, 255, 0.08); border: 1px solid #00f0ff; padding: 10px; margin-bottom: 12px;">
                <span style="color: #00f0ff; font-family: 'Orbitron', monospace; font-size: 0.75rem;">
                    📱 SCAN NEURAL QR CODE
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.image(str(QR_IMAGE_PATH), caption="Link via WhatsApp > Linked Devices", use_container_width=True)

    # Emergency Controls
    st.markdown("### 🛑 PROTOCOL KILL SWITCH")
    if KILL_SWITCH_PATH.exists():
        st.warning("NEURAL CUTOFF ACTIVE")
        if st.button("🟢 RESUME TRANSMISSIONS", key="sidebar_clear_kill", use_container_width=True):
            KILL_SWITCH_PATH.unlink(missing_ok=True)
            st.rerun()
    else:
        if st.button(
            "🛑 EMERGENCY CUTOFF",
            type="primary",
            use_container_width=True,
            help="Halts message processing across Baileys and Python Bridge instantly",
        ):
            KILL_SWITCH_PATH.write_text("", encoding="utf-8")
            st.rerun()

    st.markdown("---")
    st.markdown("### 👥 AUTHORIZED TARGETS")
    rel_map = {}
    if RELATIONSHIP_MAP_PATH.exists():
        try:
            rel_map = json.loads(RELATIONSHIP_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    allowed_numbers = [k for k, v in rel_map.items() if k != "_default" and v != "unknown"]
    for num in allowed_numbers:
        st.markdown(
            f"<div style='font-family: \"Share Tech Mono\", monospace; color: #00f0ff; padding: 2px 0;'>"
            f"⚡ <code>+{num}</code> <span style='color: #8899aa;'>[{rel_map.get(num, 'friend')}]</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    new_phone = st.text_input("AUTHORIZE NEW NUMBER", placeholder="e.g. 919100240439")
    if st.button("➕ GRANT CLEARANCE", use_container_width=True):
        cleaned = "".join(filter(str.isdigit, new_phone))
        if cleaned:
            rel_map[cleaned] = "friend"
            RELATIONSHIP_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
            RELATIONSHIP_MAP_PATH.write_text(json.dumps(rel_map, indent=2), encoding="utf-8")
            Path("relationship_map.json").write_text(json.dumps(rel_map, indent=2), encoding="utf-8")
            st.success(f"Clearance granted: +{cleaned}")
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ DISPATCH PARAMETERS")

    mode_selection = st.radio(
        "OPERATING MODE",
        ["LIVE", "DRY_RUN"],
        index=0 if not is_dry else 1,
        help="LIVE: Dispatches actual WhatsApp replies. DRY_RUN: Simulates decisions safely.",
    )
    new_dry_run = (mode_selection == "DRY_RUN")
    if new_dry_run != is_dry:
        current_settings["dry_run"] = new_dry_run
        save_settings(current_settings)
        st.success(f"MODE SET TO {mode_selection}")
        st.rerun()

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        new_min_delay = st.number_input("MIN PACING (S)", min_value=1, max_value=60, value=min_delay)
    with col_d2:
        new_max_delay = st.number_input("MAX PACING (S)", min_value=1, max_value=60, value=max_delay)

    if new_min_delay < new_max_delay and (new_min_delay != min_delay or new_max_delay != max_delay):
        current_settings["min_delay_seconds"] = int(new_min_delay)
        current_settings["max_delay_seconds"] = int(new_max_delay)
        save_settings(current_settings)
        st.rerun()

    st.markdown("---")
    st.markdown("### 📊 NEURAL METRICS")
    log_entries = load_logs()
    total_messages = len(log_entries)
    total_replies = sum(1 for e in log_entries if str(e.get("decision", "ignore")).lower() == "reply")
    total_ignored = total_messages - total_replies

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("DISPATCHES", total_replies)
    with col_m2:
        st.metric("BLOCKED", total_ignored)

    if st.button("🧹 PURGE TELEMETRY", use_container_width=True):
        if LOG_PATH.exists():
            LOG_PATH.write_text("", encoding="utf-8")
        st.rerun()

# --- Main Transmission Stream ---
st.markdown("### 📡 REAL-TIME TRANSMISSION FEED")

if not log_entries:
    st.markdown(
        """
        <div class="cyber-card" style="text-align: center; padding: 40px 20px;">
            <p style="font-family: 'Orbitron', monospace; font-size: 1.1rem; color: #00f0ff; margin-bottom: 8px;">
                // AWAITING INCOMING TRANSMISSIONS //
            </p>
            <p style="font-family: 'Share Tech Mono', monospace; color: #8899aa; margin: 0;">
                WhatsApp Baileys socket is actively listening. Send a message to see it decode and respond in real-time.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

for entry in log_entries:
    timestamp = entry.get("timestamp", "unknown")
    jid = entry.get("jid", "unknown")
    incoming_text = entry.get("text", "")
    relationship = str(entry.get("relationship", "unknown")).upper()
    decision = str(entry.get("decision", "ignore")).upper()
    reason = entry.get("reason", "no reason provided")
    reply = entry.get("reply")
    retrieval_trace = entry.get("retrieval_trace") or []

    badge_class = "badge-reply" if decision == "REPLY" else "badge-ignore"

    st.markdown(
        f"""
        <div class="cyber-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid rgba(0, 240, 255, 0.15); padding-bottom: 8px;">
                <div>
                    <span style="font-family: 'Share Tech Mono', monospace; color: #8899aa; font-size: 0.8rem;">
                        TIMESTAMP: <span style="color: #ffffff;">{timestamp}</span>
                    </span>
                    &nbsp;&nbsp;•&nbsp;&nbsp;
                    <span style="font-family: 'Share Tech Mono', monospace; color: #00f0ff; font-size: 0.85rem;">
                        SOURCE: <code>{jid}</code>
                    </span>
                </div>
                <div>
                    <span class="cyber-badge badge-rel">{relationship}</span>
                    &nbsp;
                    <span class="cyber-badge {badge_class}">{decision}</span>
                </div>
            </div>
            
            <div style="margin-bottom: 10px;">
                <span style="font-family: 'Orbitron', monospace; font-size: 0.75rem; color: #8899aa; letter-spacing: 1px;">
                    // INCOMING PAYLOAD:
                </span>
                <p style="font-family: 'Chakra Petch', sans-serif; font-size: 1.15rem; color: #ffffff; margin: 4px 0 8px 0; font-weight: 600;">
                    {incoming_text if incoming_text else "<em>[EMPTY OR RAW MEDIA TRANSMISSION]</em>"}
                </p>
                <div style="font-family: 'Share Tech Mono', monospace; font-size: 0.8rem; color: rgba(255, 255, 255, 0.6);">
                    PROTOCOL REASON: <span style="color: {'#00ff66' if decision == 'REPLY' else '#ff0055'};">{reason}</span>
                </div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    if reply:
        st.markdown(
            f"""
            <div style="
                background: rgba(0, 240, 255, 0.05);
                border-left: 3px solid var(--neon-cyan);
                padding: 10px 16px;
                margin: 12px 0;
            ">
                <span style="font-family: 'Orbitron', monospace; font-size: 0.7rem; color: var(--neon-cyan); letter-spacing: 1px;">
                    // AUTONOMOUS SYNTHESIS (GEMINI PERSONA):
                </span>
                <p style="font-family: 'Chakra Petch', sans-serif; font-size: 1.1rem; color: #00ffcc; margin: 4px 0 0 0; font-weight: 600;">
                    {reply}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("⚡ CHROMADB NEURAL MEMORY TRACE (TOP K)"):
        if not retrieval_trace:
            st.caption("No vector dialogue retrieved for this transmission.")
        else:
            for idx, item in enumerate(retrieval_trace, start=1):
                if isinstance(item, dict):
                    their_msg = item.get("their_message") or item.get("message") or "N/A"
                    my_rep = item.get("my_reply") or item.get("reply") or "N/A"
                    dist = item.get("distance")
                    st.markdown(f"**// VECTOR MATCH #{idx} //**")
                    st.code(f"THEIR: {their_msg}\nYOU:   {my_rep}", language="text")
                    if dist is not None:
                        st.caption(f"Cosine Distance Metric: {dist:.4f}")
                else:
                    st.write(item)

    st.markdown("</div>", unsafe_allow_html=True)
