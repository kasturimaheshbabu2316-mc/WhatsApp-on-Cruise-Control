#!/usr/bin/env python3
"""
WhatsApp on Cruise Control - Streamlit Interactive Web Application.
A two-brain autonomous AI agent for personal WhatsApp replies with RAG and safety gates.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# Set root directory in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure environment variables are loaded
load_dotenv()

CONSOLE_FEED_PATH = ROOT_DIR / "logs" / "console_feed.jsonl"
MODE_PATH = ROOT_DIR / "config" / "mode.txt"


# Streamlit Page Config
st.set_page_config(
    page_title="WhatsApp on Cruise Control",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern WhatsApp dark theme aesthetics
st.markdown(
    """
    <style>
    /* Global styles */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* WhatsApp Theme Colors */
    :root {
        --wa-dark-bg: #0b141a;
        --wa-card-bg: #111b21;
        --wa-border: #222e35;
        --wa-green: #00a884;
        --wa-green-light: #25d366;
        --wa-incoming-bubble: #202c33;
        --wa-outgoing-bubble: #005c4b;
        --wa-text-primary: #e9edef;
        --wa-text-secondary: #8696a0;
    }

    /* Card styling */
    .metric-card {
        background: #111b21;
        border: 1px solid #222e35;
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* WhatsApp Chat Preview Window */
    .wa-chat-container {
        background: #0b141a;
        background-image: radial-gradient(#1f2c34 1px, transparent 1px);
        background-size: 20px 20px;
        border: 1px solid #222e35;
        border-radius: 16px;
        padding: 24px;
        margin-top: 15px;
        margin-bottom: 20px;
    }

    .wa-chat-header {
        display: flex;
        align-items: center;
        gap: 14px;
        padding-bottom: 16px;
        border-bottom: 1px solid #222e35;
        margin-bottom: 20px;
    }

    .wa-avatar {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: linear-gradient(135deg, #128c7e, #075e54);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 18px;
        color: white;
    }

    .wa-contact-info h4 {
        margin: 0;
        color: #e9edef;
        font-size: 16px;
        font-weight: 600;
    }

    .wa-contact-info p {
        margin: 0;
        color: #00a884;
        font-size: 12px;
    }

    /* Message Bubbles */
    .wa-bubble-incoming {
        background-color: #202c33;
        color: #e9edef;
        padding: 10px 16px;
        border-radius: 12px 12px 12px 2px;
        max-width: 75%;
        margin-bottom: 14px;
        display: inline-block;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
        position: relative;
    }

    .wa-bubble-incoming .sender-label {
        font-size: 11px;
        color: #53bdeb;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .wa-bubble-incoming .bubble-text {
        font-size: 14.5px;
        line-height: 1.45;
    }

    .wa-bubble-incoming .bubble-time {
        font-size: 10px;
        color: #8696a0;
        float: right;
        margin-left: 14px;
        margin-top: 4px;
    }

    .wa-bubble-outgoing {
        background-color: #005c4b;
        color: #e9edef;
        padding: 10px 16px;
        border-radius: 12px 12px 2px 12px;
        max-width: 75%;
        margin-bottom: 14px;
        float: right;
        clear: both;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }

    .wa-bubble-outgoing .sender-label {
        font-size: 11px;
        color: #25d366;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .wa-bubble-outgoing .bubble-text {
        font-size: 14.5px;
        line-height: 1.45;
    }

    .wa-bubble-outgoing .bubble-time {
        font-size: 10px;
        color: #8696a0;
        float: right;
        margin-left: 14px;
        margin-top: 4px;
    }

    /* Badges */
    .badge-approved {
        background: rgba(0, 168, 132, 0.15);
        color: #25d366;
        border: 1px solid rgba(37, 211, 102, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-ignored {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-neutral {
        background: rgba(134, 150, 160, 0.15);
        color: #8696a0;
        border: 1px solid rgba(134, 150, 160, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    
    .gate-card {
        background: #111b21;
        border: 1px solid #222e35;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cached Resource for ChromaDB Client and Embedding Model
@st.cache_resource(show_spinner="Initializing ChromaDB & Multilingual Embedding Engine...")
def get_cached_rag_resources():
    import chromadb
    from sentence_transformers import SentenceTransformer

    chroma_path = ROOT_DIR / "chroma_data"
    client = chromadb.PersistentClient(path=str(chroma_path))
    model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return client, model


# Helper functions
def load_json(file_path: Path | str) -> dict:
    p = Path(file_path)
    if p.exists():
        try:
            with p.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def cached_retrieve_similar(relationship: str, text: str, k: int = 3) -> list[dict]:
    if not text or not text.strip():
        return []
    try:
        client, model = get_cached_rag_resources()
        collection_name = f"history_{relationship}"
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            return []
        count = collection.count()
        if count == 0:
            return []
        query_embedding = model.encode([text.strip()], show_progress_bar=False)[0].tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, count),
            include=["documents", "metadatas", "distances"],
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        pairs = []
        for d, m, dist in zip(docs, metas, dists):
            reply = m.get("my_reply", "") if isinstance(m, dict) else ""
            pairs.append({"their_message": d, "my_reply": reply, "distance": float(dist)})
        return pairs
    except Exception as e:
        st.warning(f"RAG retrieval fallback: {e}")
        return []


# Lazy import core modules
from agent.decision_engine import should_reply
from agent.generator import generate_reply
from agent.router import resolve_relationship


def read_operating_mode() -> str:
    try:
        text = MODE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "DRY_RUN"
    val = text.upper().strip()
    return val if val in {"DRY_RUN", "LIVE"} else "DRY_RUN"


def set_operating_mode(mode: str) -> None:
    MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODE_PATH.write_text(mode.strip().upper() + "\n", encoding="utf-8")


def load_console_logs(limit: int = 50) -> list[dict]:
    if not CONSOLE_FEED_PATH.exists():
        return []
    entries = []
    with CONSOLE_FEED_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
                if isinstance(item, dict):
                    entries.append(item)
            except Exception:
                continue
    return entries[-limit:][::-1]


def check_bridge_status() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:5001/health", timeout=0.8) as res:
            return res.status == 200
    except Exception:
        return False


# Sidebar Configuration & Diagnostics
with st.sidebar:
    st.markdown("## 🚗 WhatsApp on Cruise Control")
    st.caption("Autonomous WhatsApp AI Agent • RAG + Safety Gates")
    st.markdown("---")

    nav_option = st.radio(
        "Navigation",
        [
            "🔴 Live WhatsApp Decision Feed",
            "💬 Live Auto-Reply Simulator",
            "🧪 Batch Safety Test Suite",
            "🧠 Two-Brain Architecture",
            "🗂️ Contacts & Allowlist",
            "📜 Decision Audit Log",
        ],
        index=0,
    )

    st.markdown("---")
    st.markdown("### 🔍 System Diagnostics")

    # Check Bridge
    if check_bridge_status():
        st.success("🟢 Flask Bridge: Connected (Port 5001)")
    else:
        st.caption("⚪ Flask Bridge: Offline (`python bridge.py`)")

    # Check Gemini API Key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        st.success("🟢 Gemini API: Connected")
    else:
        st.error("🔴 Gemini API: Key Missing in .env")

    # Check ChromaDB
    try:
        c_client, _ = get_cached_rag_resources()
        friend_col = c_client.get_collection("history_friend")
        st.success(f"🟢 ChromaDB: {friend_col.count()} Dialogue Pairs")
    except Exception as e:
        st.warning(f"🟡 ChromaDB Status: {e}")

    # Mode in sidebar
    curr_op_mode = read_operating_mode()
    mode_badge_color = "#f59e0b" if curr_op_mode == "DRY_RUN" else "#22c55e"
    st.markdown(
        f"**Active Mode:** <span style='background: {mode_badge_color}22; color: {mode_badge_color}; padding: 3px 8px; border-radius: 6px; font-weight: 600;'>{curr_op_mode}</span>",
        unsafe_allow_html=True,
    )

    st.info("💡 **Model**: `gemini-2.5-flash`\n\n🧠 **Embeddings**: `paraphrase-multilingual-mpnet-base-v2`")

    st.markdown("---")
    st.caption("Built with Google GenAI SDK & Streamlit")


# ==============================================================================
# TAB 0: LIVE DECISION FEED & CONSOLE (WEEK 4 PUPPETMASTER)
# ==============================================================================
if nav_option == "🔴 Live WhatsApp Decision Feed":
    if st_autorefresh is not None:
        st_autorefresh(interval=2000, key="console_feed_autorefresh")

    st.title("🔴 Live WhatsApp Decision Feed & Cruise Control Console")
    st.markdown(
        "Live autonomous decision stream receiving incoming messages via **Baileys WhatsApp Client** "
        "and processing them through the **Flask Bridge API**."
    )

    curr_mode = read_operating_mode()
    col_mode, col_actions = st.columns([2, 3])
    with col_mode:
        selected_mode = st.radio(
            "Cruise Control Mode",
            ["DRY_RUN", "LIVE"],
            index=0 if curr_mode == "DRY_RUN" else 1,
            horizontal=True,
            help="DRY_RUN: Simulate & log without sending actual WhatsApp messages. LIVE: Dispatches real replies via WhatsApp.",
        )
        if selected_mode != curr_mode:
            set_operating_mode(selected_mode)
            st.success(f"Mode set to {selected_mode}")
            st.rerun()

    with col_actions:
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🚀 Ping Bridge with Test Message", use_container_width=True):
                import json
                import urllib.request
                try:
                    test_payload = json.dumps({
                        "jid": "919812345670@s.whatsapp.net",
                        "text": "Are you free for coffee later?",
                        "message_type": "text",
                        "is_forwarded": False,
                        "from_me": False,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        "http://localhost:5001/process",
                        data=test_payload,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=20) as res:
                        res_data = json.loads(res.read().decode("utf-8"))
                        st.success(f"Bridge reply: {res_data.get('reply') or 'Ignored'}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Bridge ping failed: {e}. Is `python bridge.py` running?")
        with btn_c2:
            if st.button("🧹 Clear Feed History", use_container_width=True):
                if CONSOLE_FEED_PATH.exists():
                    CONSOLE_FEED_PATH.write_text("", encoding="utf-8")
                st.rerun()

    st.markdown("---")

    # Metrics
    logs = load_console_logs(limit=50)
    total_msgs = len(logs)
    replies_count = sum(1 for e in logs if str(e.get("decision", "")).lower() == "reply")
    ignored_count = total_msgs - replies_count

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Messages Streamed", total_msgs)
    with m2:
        st.metric("Automated Replies", replies_count)
    with m3:
        st.metric("Safe Ignores", ignored_count)
    with m4:
        st.metric("Operating Policy", curr_mode)

    if not logs:
        st.info("⏳ Waiting for incoming WhatsApp messages... Start `python bridge.py` and `node baileys_client.js`, or click **Ping Bridge with Test Message** above!")
    else:
        st.markdown("### 📋 Live Stream Events")
        for entry in logs:
            timestamp = entry.get("timestamp", "unknown")
            jid = entry.get("jid", "unknown")
            incoming_text = entry.get("text", "")
            relationship = str(entry.get("relationship", "unknown")).lower()
            decision = str(entry.get("decision", "ignore")).lower()
            reason = entry.get("reason", "no reason provided")
            reply = entry.get("reply")
            retrieval_trace = entry.get("retrieval_trace") or []

            with st.container():
                st.markdown(
                    f"""
                    <div style="background: #111b21; border: 1px solid #222e35; border-radius: 12px; padding: 16px 20px; margin-bottom: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div>
                                <span style="color: #8696a0; font-size: 13px;">🕒 {timestamp}</span>
                                <span style="margin-left: 12px; color: #53bdeb; font-weight: 600; font-size: 13px;">👤 {jid}</span>
                            </div>
                            <div>
                                <span class="badge-neutral" style="margin-right: 8px;">{relationship.upper()}</span>
                                <span class="{'badge-approved' if decision == 'reply' else 'badge-ignored'}">{'🟢 REPLY' if decision == 'reply' else '⚪ IGNORED'}</span>
                            </div>
                        </div>
                    """,
                    unsafe_allow_html=True,
                )
                if incoming_text:
                    st.markdown(f"**Incoming:** `{incoming_text}`")
                st.markdown(f"**Gate Reason:** *{reason}*")

                if reply:
                    st.markdown("**Generated In-Character Reply:**")
                    st.success(reply)

                if retrieval_trace and isinstance(retrieval_trace, list):
                    with st.expander(f"🔍 ChromaDB Retrieval Trace ({len(retrieval_trace)} historical pairs)"):
                        for idx, item in enumerate(retrieval_trace, start=1):
                            if isinstance(item, dict):
                                past_msg = item.get("their_message") or item.get("text") or ""
                                past_rep = item.get("my_reply") or item.get("reply") or ""
                                dist = item.get("distance")
                                dist_str = f"{dist:.4f}" if isinstance(dist, (int, float)) else "N/A"
                                st.markdown(f"**Match #{idx}** (Distance: `{dist_str}`)")
                                st.code(f"They: {past_msg}\nMe:   {past_rep}", language="text")

                st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# TAB 1: LIVE SIMULATOR
# ==============================================================================
elif nav_option == "💬 Live Auto-Reply Simulator":
    st.title("💬 WhatsApp Live Simulator & Auto-Reply Pipeline")

    st.markdown(
        "Simulate an incoming WhatsApp message and watch the **Router**, **Safety Gates**, "
        "**ChromaDB Vector Retrieval**, and **Persona Brain** make an authentic autonomous decision."
    )

    col_input, col_meta = st.columns([2, 1])

    with col_meta:
        st.markdown("#### 👤 Sender & Context")
        contact_preset = st.selectbox(
            "Select Contact",
            [
                "Friend: D.N.K (1-on-1 friend)",
                "Group: The BOYS🔥 (Friends group)",
                "Unknown Number (+91 98999 99999)",
                "Custom JID / Number",
            ],
        )

        if "D.N.K" in contact_preset:
            jid = "919812345670@s.whatsapp.net"
            contact_name = "D.N.K (Friend)"
        elif "BOYS" in contact_preset:
            jid = "120363000000000000@g.us"
            contact_name = "The BOYS🔥"
        elif "Unknown" in contact_preset:
            jid = "919899999999@s.whatsapp.net"
            contact_name = "Unknown (+91 98999 99999)"
        else:
            jid = st.text_input("Custom WhatsApp JID", value="919812345670@s.whatsapp.net")
            contact_name = "Custom Contact"

        message_type = st.selectbox("Message Type", ["text", "image", "audio", "video"])
        is_forwarded = st.checkbox("Forwarded Message", value=False)
        from_me = st.checkbox("From Me (Outgoing message)", value=False)

    with col_input:
        st.markdown("#### 📝 Incoming WhatsApp Message")
        
        # Quick Preset Buttons
        st.markdown("<span style='font-size:12px; color:#8696a0;'>Quick Presets:</span>", unsafe_allow_html=True)
        q_cols = st.columns(4)
        quick_msg = None
        if q_cols[0].button("📞 Friend Call"):
            quick_msg = "Bhai free aa ippudu? Call cheyyi urgent ga."
        if q_cols[1].button("💸 Money Request"):
            quick_msg = "Can you send me 5000 rupees?"
        if q_cols[2].button("🍕 Weekend Plan"):
            quick_msg = "Are you free for dinner tonight?"
        if q_cols[3].button("👍 Ack ('thanks')"):
            quick_msg = "thanks"

        default_text = quick_msg if quick_msg else "Bhai free aa ippudu? Call cheyyi urgent ga."
        incoming_text = st.text_area(
            "Message Content",
            value=default_text,
            height=100,
            placeholder="Type WhatsApp message here...",
        )

        run_btn = st.button("🚀 Process Message through Cruise Control", type="primary", use_container_width=True)

    if run_btn:
        st.markdown("---")
        
        # 1. Routing
        relationship, collection = resolve_relationship(jid)
        
        message_dict = {
            "text": incoming_text,
            "message_type": message_type,
            "is_forwarded": is_forwarded,
            "from_me": from_me,
        }

        # 2. Decision Engine
        t_start = time.time()
        should_rep, reason = should_reply(message_dict, relationship)
        elapsed_decision = round(time.time() - t_start, 2)

        # 3. RAG & Generation if approved
        retrieved_examples = []
        generated_response = ""
        elapsed_gen = 0.0

        if should_rep:
            t_gen = time.time()
            retrieved_examples = cached_retrieve_similar(relationship, incoming_text, k=3)
            generated_response = generate_reply(incoming_text, relationship)
            elapsed_gen = round(time.time() - t_gen, 2)

        # Pipeline Visual Display
        st.markdown("### 🔄 4-Stage Pipeline Execution")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"**Stage 1: Router**\n- Contact: `{relationship.upper()}`\n- Collection: `{collection or 'None'}`")
        with c2:
            verdict_badge = "🟢 **REPLY**" if should_rep else "🔴 **IGNORE**"
            st.markdown(f"**Stage 2: Gatekeeper**\n- Decision: {verdict_badge}\n- Latency: `{elapsed_decision}s`")
        with c3:
            st.markdown(f"**Stage 3: RAG Retrieval**\n- Retrieved: `{len(retrieved_examples)} pairs`\n- Vector: `ChromaDB`")
        with c4:
            st.markdown(f"**Stage 4: Persona Brain**\n- Status: `{'Generated' if should_rep else 'Skipped'}`\n- Latency: `{elapsed_gen}s`")

        st.markdown("---")

        # Chat Simulator UI
        col_chat, col_details = st.columns([3, 2])

        with col_chat:
            st.markdown("#### 📱 Live WhatsApp Chat Simulation")
            now_str = datetime.now().strftime("%I:%M %p")
            
            chat_html = f"""
            <div class="wa-chat-container">
                <div class="wa-chat-header">
                    <div class="wa-avatar">{contact_name[0]}</div>
                    <div class="wa-contact-info">
                        <h4>{contact_name}</h4>
                        <p>● online • Cruise Control Active</p>
                    </div>
                </div>
                <div style="min-height: 180px;">
                    <div class="wa-bubble-incoming">
                        <div class="sender-label">{contact_name}</div>
                        <div class="bubble-text">
                            {f'<i>[Media: {message_type}]</i><br>' if message_type != 'text' else ''}
                            {f'<span style="font-size:11px; color:#8696a0;">↪ Forwarded</span><br>' if is_forwarded else ''}
                            {incoming_text if incoming_text else '<i>(No text caption)</i>'}
                        </div>
                        <span class="bubble-time">{now_str}</span>
                    </div>
            """

            if should_rep:
                chat_html += f"""
                    <div class="wa-bubble-outgoing">
                        <div class="sender-label">You (AI Cruise Control 🤖)</div>
                        <div class="bubble-text">{generated_response}</div>
                        <span class="bubble-time">{now_str} ✓✓</span>
                    </div>
                """
            else:
                chat_html += f"""
                    <div style="clear: both; text-align: center; padding: 12px; margin-top: 20px;">
                        <span class="badge-ignored">🚫 Message Ignored by AI: {reason}</span>
                    </div>
                """

            chat_html += """
                </div>
            </div>
            """
            st.markdown(chat_html, unsafe_allow_html=True)

        with col_details:
            st.markdown("#### 🛡️ Gate Evaluation Breakdown")
            
            # Show individual gate statuses
            gates = [
                ("1. Outgoing Message (`from_me`)", not from_me, "Ignored: own message"),
                ("2. Media-Only Caption Check", not (message_type in ("image", "audio", "video") and not incoming_text.strip()), "Ignored: media without text"),
                ("3. Forwarded Content Filter", not is_forwarded, "Ignored: forwarded content"),
                ("4. One-Word Ack Filter", incoming_text.strip().lower() not in {"ok", "okay", "k", "kk", "thanks", "cool"}, "Ignored: low-signal ack"),
                ("5. Allowlist & Relationship Check", relationship != "unknown" and relationship != "group", f"Status: {relationship}"),
                ("6. Financial / Serious Intent Safety", should_rep or "passed" in reason, reason),
            ]

            for g_name, g_passed, g_info in gates:
                chip = "✅ PASS" if g_passed else "❌ TRIGGERED"
                chip_class = "badge-approved" if g_passed else "badge-ignored"
                st.markdown(
                    f"""
                    <div class="gate-card">
                        <div>
                            <span style="font-size:13px; font-weight:500;">{g_name}</span><br>
                            <span style="font-size:11px; color:#8696a0;">{g_info}</span>
                        </div>
                        <span class="{chip_class}">{chip}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if retrieved_examples:
                with st.expander(f"📚 Retrieved Context from ChromaDB ({len(retrieved_examples)} pairs)", expanded=True):
                    for idx, p in enumerate(retrieved_examples, 1):
                        st.markdown(f"**Example {idx}** (Distance: `{p['distance']:.3f}`):")
                        st.markdown(f"> **Their message:** {p['their_message']}")
                        st.markdown(f"> **My authentic reply:** `{p['my_reply']}`")
                        st.markdown("---")


# ==============================================================================
# TAB 2: BATCH SAFETY TEST SUITE
# ==============================================================================
elif nav_option == "🧪 Batch Safety Test Suite":
    st.title("🧪 Batch Safety Test Suite & Gate Regression Matrix")
    st.markdown(
        "Run the complete multi-gate test benchmark to verify that no safety constraints are violated, "
        "financial requests are strictly guarded, and authentic personal banter is approved."
    )

    from batch_test import TEST_CASES

    if st.button("▶️ Execute Full 10-Case Benchmark", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        for i, tc in enumerate(TEST_CASES):
            status_text.text(f"Running test {i+1}/{len(TEST_CASES)}: {tc['name']}...")
            rel, _ = resolve_relationship(tc["jid"])
            msg_data = {
                "from_me": tc["from_me"],
                "text": tc["text"],
                "message_type": tc["message_type"],
                "is_forwarded": tc["is_forwarded"],
            }
            t0 = time.time()
            s_reply, reason = should_reply(msg_data, rel)
            reply = ""
            if s_reply:
                reply = generate_reply(tc["text"], rel)
            t_taken = round(time.time() - t0, 2)

            results.append({
                "Case Name": tc["name"],
                "Incoming Text": tc["text"] if tc["text"] else f"[{tc['message_type']}]",
                "Relationship": rel,
                "Decision": "REPLY" if s_reply else "IGNORE",
                "Reason": reason,
                "Generated Reply": reply,
                "Time (s)": t_taken,
            })
            progress_bar.progress((i + 1) / len(TEST_CASES))

        status_text.text("Benchmark complete!")
        df = pd.DataFrame(results)

        # Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        total = len(df)
        replies = (df["Decision"] == "REPLY").sum()
        ignores = (df["Decision"] == "IGNORE").sum()
        money_blocked = df[df["Case Name"].str.contains("money", case=False)]["Decision"].values[0] == "IGNORE"

        m1.metric("Total Test Cases", total)
        m2.metric("Autonomous Replies", replies)
        m3.metric("Safely Ignored / Guarded", ignores)
        m4.metric("Financial Protection", "100% BLOCKED" if money_blocked else "FAILED")

        st.markdown("### 📊 Test Matrix Results")
        
        for r in results:
            decision_badge = "badge-approved" if r["Decision"] == "REPLY" else "badge-ignored"
            with st.container():
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h4 style="margin:0;">{r['Case Name']} <span style="font-size:12px; color:#8696a0;">({r['Relationship']})</span></h4>
                            <span class="{decision_badge}">{r['Decision']}</span>
                        </div>
                        <p style="margin: 8px 0 4px 0; color:#e9edef;"><b>Input:</b> {r['Incoming Text']}</p>
                        <p style="margin: 0; color:#8696a0; font-size:13px;"><b>Gate Reason:</b> {r['Reason']}</p>
                        {f'<p style="margin: 8px 0 0 0; color:#25d366; font-size:14px;"><b>↳ Generated Reply:</b> {r["Generated Reply"]}</p>' if r["Generated Reply"] else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ==============================================================================
# TAB 3: TWO-BRAIN ARCHITECTURE
# ==============================================================================
elif nav_option == "🧠 Two-Brain Architecture":
    st.title("🧠 Two-Brain Architecture Explorer")
    st.markdown(
        "WhatsApp on Cruise Control combines two distinct cognitive layers: "
        "the **Persona Brain** (prompt-based voice, tone, and unvarnished style signals) and "
        "the **History Brain** (ChromaDB multilingual semantic memory)."
    )

    t1, t2 = st.tabs(["🎭 Persona Brain", "📚 History Brain (ChromaDB RAG)"])

    with t1:
        st.markdown("### 🎭 Persona Brain: Voice & Style Signals")
        persona_data = load_json("persona.json")
        friend_signals = load_json("style_signals_friend.json")
        group_signals = load_json("style_signals_group.json")

        col_id, col_stats = st.columns([3, 2])
        with col_id:
            st.markdown(f"**Identity:**\n> {persona_data.get('identity', 'Personal WhatsApp Assistant')}")
            
            st.markdown("#### 🗣️ Relationship Tone Guidelines")
            rels = persona_data.get("relationships", {})
            for rel_name, rel_info in rels.items():
                st.markdown(f"**{rel_name.title()}**:")
                st.markdown(f"- **Tone**: {rel_info.get('tone')}")
                st.markdown(f"- **Avg Word Length**: `{rel_info.get('avg_message_length_words')} words`")

        with col_stats:
            st.markdown("#### 📊 Extracted Style Metrics")
            st.metric("Friend Avg Message Length", f"{friend_signals.get('avg_message_length_words', 2.58)} words")
            st.metric("Group Avg Message Length", f"{group_signals.get('avg_message_length_words', 3.49)} words")
            
            st.markdown("#### 🎨 Top Emojis Extracted")
            def _extract_emojis(data):
                res = []
                for item in (data or []):
                    if isinstance(item, dict):
                        res.append(item.get("emoji", ""))
                    elif isinstance(item, str):
                        res.append(item)
                return " ".join([e for e in res[:8] if e])

            top_emojis_friend = friend_signals.get("top_emojis", ["🙄", "😳", "🖕", "🤦", "🍺"])
            st.markdown(" **Friend (D.N.K):** " + _extract_emojis(top_emojis_friend))
            top_emojis_group = group_signals.get("top_emojis", ["😅", "😎", "🔥", "🙄", "🤫"])
            st.markdown(" **Group (The BOYS):** " + _extract_emojis(top_emojis_group))

        with st.expander("📄 View Raw persona.json"):
            st.json(persona_data)

    with t2:
        st.markdown("### 📚 History Brain: Multilingual Semantic Search")
        st.markdown("Test the vector database directly by typing any phrase to retrieve closest real conversational turns from ChromaDB.")

        query_text = st.text_input("Semantic Search Query", value="are you free to meet up today?")
        rel_choice = st.selectbox("Search Collection", ["friend", "family", "professional", "unknown"])
        k_val = st.slider("Number of pairs (k)", 1, 5, 3)

        if st.button("🔍 Search ChromaDB History"):
            with st.spinner("Searching vector index..."):
                results = cached_retrieve_similar(rel_choice, query_text, k=k_val)
                if not results:
                    st.info(f"No pairs found in collection `history_{rel_choice}`.")
                else:
                    for i, r in enumerate(results, 1):
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <b>Match #{i}</b> (Semantic Distance: <code>{r['distance']:.4f}</code>)<br>
                                <p style="margin: 8px 0 4px 0;"><b>Their Message:</b> {r['their_message']}</p>
                                <p style="margin: 0; color:#25d366;"><b>My Historical Reply:</b> {r['my_reply']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )


# ==============================================================================
# TAB 4: CONTACTS & ALLOWLIST
# ==============================================================================
elif nav_option == "🗂️ Contacts & Allowlist":
    st.title("🗂️ Contact Allowlist & JID Routing")
    st.markdown("Manage phone numbers and group IDs mapped to relationships in `config/relationship_map.json`.")

    map_path = ROOT_DIR / "config" / "relationship_map.json"
    rel_map = load_json(map_path)

    col_tbl, col_add = st.columns([3, 2])

    with col_tbl:
        st.markdown("#### 📋 Current Mappings")
        data_rows = [{"Phone Number / Identifier": k, "Relationship": v} for k, v in rel_map.items()]
        st.dataframe(pd.DataFrame(data_rows), use_container_width=True)

    with col_add:
        st.markdown("#### ➕ Add or Update Contact")
        new_number = st.text_input("Phone Number (without @...)", placeholder="e.g. 919876543210")
        new_rel = st.selectbox("Relationship", ["friend", "group", "family", "professional", "unknown"])
        
        if st.button("Save Contact Mapping", type="primary"):
            if new_number.strip():
                rel_map[new_number.strip()] = new_rel
                with open(map_path, "w", encoding="utf-8") as f:
                    json.dump(rel_map, f, indent=2)
                st.success(f"Saved `{new_number}` as `{new_rel}`!")
                st.rerun()


# ==============================================================================
# TAB 5: DECISION AUDIT LOG
# ==============================================================================
elif nav_option == "📜 Decision Audit Log":
    st.title("📜 Decision Audit Log & Analytics")
    st.markdown("Audit log of all decisions evaluated by the Cruise Control decision engine (`logs/decision_log.jsonl`).")

    log_path = ROOT_DIR / "logs" / "decision_log.jsonl"
    if not log_path.exists():
        st.info("No decision logs recorded yet.")
    else:
        entries = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass

        if not entries:
            st.info("Log file is empty.")
        else:
            df_logs = pd.DataFrame(entries)
            
            # Filters
            f_col1, f_col2 = st.columns(2)
            dec_filter = f_col1.multiselect("Filter Decision", options=list(df_logs["decision"].unique()), default=list(df_logs["decision"].unique()))
            search_kw = f_col2.text_input("Search Message Text", "")

            filtered = df_logs[df_logs["decision"].isin(dec_filter)]
            if search_kw:
                filtered = filtered[filtered["message"].str.contains(search_kw, case=False, na=False)]

            st.markdown(f"**Showing {len(filtered)} of {len(df_logs)} audit records**")
            st.dataframe(filtered, use_container_width=True)
