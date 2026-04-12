"""
app.py — NetRecall ISP Intelligence Command Center (v2)

State machine: IDLE → RINGING → ACTIVE → POSTCALL

Key changes from v1:
  - SQLite CustomerDB replaces hardcoded seed_data
  - System starts empty; data builds through real calls
  - Voice input via browser SpeechRecognition
  - AI note extraction panel (auto-extracts facts from conversation)
  - Decision log with quick action buttons
  - New 3-column active call layout: Co-Pilot | Intelligence | Transcript
  - Unknown callers get a 10-second customer creation form
"""

from __future__ import annotations
import os
import time
from datetime import datetime

import nest_asyncio
nest_asyncio.apply()

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from database         import CustomerDB
from resolution_engine import ResolutionEngine, detect_issue_type
from network_patterns  import PatternDetector
from copilot           import CoPilot
from note_engine       import extract_notes, merge_notes, notes_to_html, should_extract, EMPTY_NOTES
from voice_component   import render_voice_input, poll_voice_input
from agent            import NetRecallAgent
import dashboard as dash_module

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NetRecall — ISP Intelligence",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
/* ═══════════════════════════════════════════════════
   FORCE LIGHT THEME — override Streamlit dark mode
   ═══════════════════════════════════════════════════ */

/* Hide the top black Streamlit header/toolbar bar + remove its space */
[data-testid="stHeader"]  { display:none !important; height:0 !important; }
[data-testid="stToolbar"] { display:none !important; height:0 !important; }
#MainMenu { display:none !important; }
footer    { display:none !important; }
/* Remove the gap the hidden header leaves */
.stApp { margin-top:0 !important; }
.main .block-container {
  padding-top:1.2rem !important;
  padding-bottom:2rem !important;
  max-width:1200px;
}

/* Full app — white background, dark text */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > div,
.main, .block-container { background:#ffffff !important; color:#111827 !important; }

/* Sidebar */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div {
  background:#fafafa !important; color:#111827 !important;
  border-right:1px solid #f0f0f0; }

/* ALL text elements — dark by default */
p, h1, h2, h3, h4, h5, h6, span, div, label, li, td, th {
  color:#111827 !important; }

/* Override back to lighter grays where needed via class */
.text-muted { color:#6b7280 !important; }

/* Markdown containers */
div[data-testid="stMarkdownContainer"],
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stMarkdownContainer"] li,
div[data-testid="stMarkdownContainer"] span,
div[data-testid="stMarkdownContainer"] div { color:#374151 !important; }

/* Widget labels */
label[data-testid="stWidgetLabel"] > p,
label[data-testid="stWidgetLabel"] > div { color:#374151 !important; }

/* Captions */
[data-testid="stCaptionContainer"] p,
.stCaption p { color:#6b7280 !important; }

/* Input fields — white bg, dark text */
.stTextInput input, .stTextArea textarea {
  background:#ffffff !important; color:#111827 !important;
  border:1px solid #e5e7eb !important; border-radius:6px !important; }
.stTextInput input::placeholder,
.stTextArea textarea::placeholder { color:#9ca3af !important; }
[data-baseweb="input"] { background:#ffffff !important; }
[data-baseweb="input"] input { color:#111827 !important; }

/* Selectbox */
[data-baseweb="select"] { background:#ffffff !important; }
[data-baseweb="select"] [data-testid="stSelectboxLabel"] { color:#111827 !important; }
[data-baseweb="select"] div { color:#111827 !important; background:#ffffff !important; }

/* Expander headers */
details summary p, details summary span { color:#111827 !important; }
[data-testid="stExpander"] summary { background:#fafafa !important; }

/* Metrics */
div[data-testid="metric-container"] {
  background:#ffffff !important; border:1px solid #f0f0f0;
  border-radius:8px; padding:10px 14px; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#111827 !important; }
div[data-testid="metric-container"] [data-testid="stMetricLabel"] { color:#6b7280 !important; }

/* Buttons — primary = dark, secondary = outlined */
.stButton > button[kind="primary"] {
  background:#111827 !important; color:#ffffff !important;
  border:none !important; border-radius:6px !important; font-weight:600; }
.stButton > button[kind="secondary"] {
  background:#ffffff !important; color:#111827 !important;
  border:1px solid #e5e7eb !important; border-radius:6px !important; }

/* Info / success / warning / error boxes */
[data-testid="stAlert"] { border-radius:8px !important; }

/* Spinner */
.stSpinner p { color:#374151 !important; }

/* -webkit-font-smoothing */
* { -webkit-font-smoothing:antialiased; }

/* ── Tabs — underline style ──────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background:transparent !important; border-bottom:1px solid #f0f0f0;
  gap:0; padding:0; border-radius:0; }
.stTabs [data-baseweb="tab"] {
  background:transparent !important; color:#6b7280 !important;
  font-weight:500; font-size:0.9rem; padding:10px 20px;
  border:none !important; border-radius:0 !important; }
.stTabs [aria-selected="true"] {
  color:#111827 !important; font-weight:700;
  border-bottom:2px solid #111827 !important; }

/* ── Top bar ─────────────────────────────────────── */
.nr-topbar { display:flex; align-items:center; justify-content:space-between;
  padding:14px 0; border-bottom:1px solid #f0f0f0; margin-bottom:20px; }
.nr-logo { color:#111827; font-size:1.05rem; font-weight:800; letter-spacing:-0.3px; }
.nr-sub  { color:#9ca3af; font-size:0.72rem; margin-left:6px; }
.nr-status { color:#9ca3af; font-size:0.75rem; }

/* ── Ringing ─────────────────────────────────────── */
@keyframes ring-pulse { 0%,100% { opacity:1; } 50% { opacity:0.55; } }
.ring-banner { border-left:4px solid #ef4444; border-radius:0 8px 8px 0;
  padding:16px 20px; background:#fafafa; margin-bottom:16px;
  animation:ring-pulse 1.5s ease-in-out infinite; }
.ring-title   { color:#111827; font-size:1.05rem; font-weight:800; }
.ring-sub     { color:#6b7280; font-size:0.82rem; margin-top:4px; }
.ring-preview { color:#6b7280; font-size:0.76rem; margin-top:6px; }

/* ── Active call ─────────────────────────────────── */
.call-active-bar { background:#111827; border-radius:10px;
  padding:10px 18px; display:flex; align-items:center;
  justify-content:space-between; margin-bottom:14px; }
.call-cname { color:#f9fafb; font-size:1rem; font-weight:700; }
.call-timer { color:#d1d5db; font-size:0.85rem; }
.call-meta  { color:#6b7280; font-size:0.75rem; }

/* ── Co-pilot ────────────────────────────────────── */
.cp-what-to-say { border-left:3px solid #111827; background:#fafafa;
  border-radius:0 8px 8px 0; padding:12px 14px; margin-bottom:10px; }
.cp-wts-label { color:#9ca3af; font-size:0.65rem; font-weight:700;
  text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; }
.cp-wts-text  { color:#111827; font-size:0.93rem; font-weight:600; line-height:1.55; }
.cp-section   { background:#fafafa; border:1px solid #f0f0f0;
  border-radius:8px; padding:10px 12px; margin-bottom:8px; }
.cp-sec-title { font-size:0.65rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.8px; margin-bottom:5px; color:#374151; }
.cp-do   { color:#16a34a; font-size:0.77rem; margin:3px 0; }
.cp-dont { color:#dc2626; font-size:0.77rem; margin:3px 0; }
.cp-tp   { color:#6b7280; font-size:0.77rem; margin:3px 0; }
.cp-esc-yes { border-left:3px solid #ef4444; background:#fafafa;
  border-radius:0 8px 8px 0; padding:8px 12px; margin-bottom:8px; }
.cp-esc-no  { border-left:3px solid #16a34a; background:#fafafa;
  border-radius:0 8px 8px 0; padding:8px 12px; margin-bottom:8px; }
.cp-conf-bar { background:#f0f0f0; border-radius:4px; height:4px; margin:4px 0; }
.sentiment-chip { display:inline-block; padding:2px 8px; border-radius:4px;
  font-size:0.68rem; font-weight:600; }

/* ── Intelligence panel ──────────────────────────── */
.intel-card { background:#fff; border:1px solid #f0f0f0;
  border-radius:8px; padding:12px 14px; margin-bottom:8px; }
.intel-head { font-size:0.65rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.8px; margin-bottom:8px; color:#374151; }
.action-log-entry { display:flex; gap:8px; padding:4px 0;
  border-bottom:1px solid #fafafa; }
.action-log-time { color:#9ca3af; font-size:0.65rem; min-width:38px; }
.action-log-text { color:#6b7280; font-size:0.75rem; }

/* ── Transcript ──────────────────────────────────── */
.tx-c { background:#f3f4f6; border-radius:8px 8px 2px 8px;
  padding:9px 12px; margin:4px 0; color:#374151; font-size:0.84rem; }
.tx-a { background:#fff; border:1px solid #e5e7eb; border-radius:8px 8px 8px 2px;
  padding:9px 12px; margin:4px 0; color:#374151; font-size:0.84rem; }
.tx-label { font-size:0.6rem; color:#9ca3af; font-weight:600;
  text-transform:uppercase; letter-spacing:0.8px; margin-bottom:2px; }

/* ── Customer / queue cards ──────────────────────── */
.queue-card { background:#fff; border:1px solid #f0f0f0;
  border-radius:8px; padding:12px 14px; margin:4px 0; }
.queue-name { color:#111827; font-weight:600; font-size:0.87rem; }
.queue-meta { color:#9ca3af; font-size:0.73rem; }

/* ── Alert band ──────────────────────────────────── */
.alert-band { border-left:3px solid #ef4444; background:#fafafa;
  border-radius:0 8px 8px 0; padding:10px 14px; margin-bottom:10px; }
.alert-band-title { color:#dc2626; font-weight:700; font-size:0.8rem; }
.alert-band-body  { color:#6b7280; font-size:0.75rem; margin-top:3px; }

/* ── DNA card ────────────────────────────────────── */
.dna-card { background:#fff; border:1px solid #f0f0f0;
  border-radius:8px; padding:14px; margin-bottom:8px; }
.dna-label { color:#9ca3af; font-size:0.62rem; font-weight:600;
  text-transform:uppercase; letter-spacing:0.8px; }
.dna-value { color:#111827; font-size:0.84rem; font-weight:500; margin-bottom:5px; }

/* ── Post-call ───────────────────────────────────── */
.pc-card { background:#fff; border:1px solid #f0f0f0; border-radius:8px;
  padding:16px 18px; margin-bottom:10px; }
.pc-head { color:#374151; font-weight:700; font-size:0.85rem; margin-bottom:6px; }
.pc-body { color:#6b7280; font-size:0.81rem; line-height:1.6; }

/* ── Animations ──────────────────────────────────── */
@keyframes breathe { 0%,100% { transform:scale(1); } 50% { transform:scale(1.06); } }
@keyframes em-pulse { 0%,100% { transform:scale(1); } 50% { transform:scale(1.08); } }
@keyframes em-shake { 0%,100% { transform:translateX(0); } 25% { transform:translateX(-4px); } 75% { transform:translateX(4px); } }
@keyframes em-tilt  { 0%,100% { transform:rotate(0deg); } 25% { transform:rotate(-8deg); } 75% { transform:rotate(8deg); } }

/* ── Emotion face ────────────────────────────────── */
.emotion-wrap   { background:#fafafa; border:1px solid #f0f0f0; border-radius:8px;
  padding:14px; text-align:center; margin-bottom:10px; }
.emotion-emoji  { font-size:2.8rem; display:block; margin-bottom:4px; }
.emotion-lbl    { font-weight:700; font-size:0.75rem; text-transform:uppercase;
  letter-spacing:0.8px; color:#374151; }
.emotion-bar-bg { background:#f0f0f0; border-radius:4px; height:4px; margin:6px 0 3px; }
.emotion-conf   { font-size:0.62rem; font-weight:600; color:#9ca3af; }

/* ── Pre-call insights ───────────────────────────── */
.pc-insight { background:#fafafa; border:1px solid #f0f0f0;
  border-radius:8px; padding:10px 14px; margin-bottom:8px; }
.pc-insight-ok   { border-left:3px solid #16a34a; }
.pc-insight-warn { border-left:3px solid #d97706; }
.pc-insight-crit { border-left:3px solid #ef4444; }
.pc-insight-title { font-weight:700; font-size:0.8rem; color:#111827; margin-bottom:3px; }
.pc-insight-body  { font-size:0.74rem; color:#6b7280; line-height:1.5; }

/* ── DNA side panel ──────────────────────────────── */
.dna-panel-sec { color:#111827; font-size:0.65rem; font-weight:700;
  text-transform:uppercase; letter-spacing:0.8px; margin:10px 0 6px; }
.dna-f  { margin-bottom:6px; }
.dna-badge-a  { display:inline-block; padding:2px 8px; border-radius:4px;
  font-size:0.65rem; font-weight:600; color:#16a34a; background:#f0fdf4; }
.dna-badge-s  { display:inline-block; padding:2px 8px; border-radius:4px;
  font-size:0.65rem; font-weight:600; color:#dc2626; background:#fef2f2; }
.dna-badge-ex { display:inline-block; padding:2px 8px; border-radius:4px;
  font-size:0.65rem; font-weight:600; color:#dc2626; background:#fef2f2; }
.dna-badge-xp { display:inline-block; padding:2px 8px; border-radius:4px;
  font-size:0.65rem; font-weight:600; color:#d97706; background:#fffbeb; }
.dna-trow { display:flex; gap:8px; padding:4px 0;
  border-bottom:1px solid #f9fafb; }
.dna-tdate { color:#9ca3af; font-size:0.62rem; min-width:50px; }
.dna-ttxt  { color:#6b7280; font-size:0.72rem; line-height:1.4; }

/* ── Chat Demo — two-panel support window ─────── */
.chat-panel-wrap { display:grid; grid-template-columns:1fr 1fr; gap:0;
  border:1px solid #f0f0f0; border-radius:10px; overflow:hidden;
  min-height:420px; background:#fff; }
.chat-panel-customer { border-right:1px solid #f0f0f0; display:flex;
  flex-direction:column; }
.chat-panel-agent { display:flex; flex-direction:column; }
.chat-panel-hdr { padding:10px 14px; border-bottom:1px solid #f0f0f0;
  font-size:0.72rem; font-weight:700; text-transform:uppercase;
  letter-spacing:0.8px; background:#fafafa; }
.chat-panel-hdr-c { color:#374151; }
.chat-panel-hdr-a { color:#111827; background:#111827; color:#f9fafb; }
.chat-msgs { flex:1; overflow-y:auto; padding:12px 14px;
  display:flex; flex-direction:column; gap:6px; min-height:320px; }
.chat-bubble-c { background:#f3f4f6; border-radius:10px 10px 2px 10px;
  padding:9px 13px; color:#111827; font-size:0.85rem; line-height:1.5;
  max-width:90%; display:inline-block; word-break:break-word; }
.chat-bubble-a { background:#fff; border:1px solid #e5e7eb;
  border-radius:10px 10px 10px 2px; padding:9px 13px;
  color:#374151; font-size:0.85rem; line-height:1.5;
  max-width:90%; word-break:break-word; }
.chat-row-c { display:flex; justify-content:flex-start; }
.chat-row-a { display:flex; justify-content:flex-end; }
.chat-meta { font-size:0.6rem; color:#9ca3af; font-weight:600;
  text-transform:uppercase; letter-spacing:0.7px;
  margin:2px 2px; }
.mem-chunk { background:#fafafa; border:1px solid #f0f0f0;
  border-left:3px solid #111827; border-radius:0 8px 8px 0;
  padding:10px 12px; margin-bottom:6px; font-size:0.76rem;
  color:#374151; line-height:1.5; }
.mem-bank-badge { display:inline-block; padding:2px 7px; border-radius:4px;
  font-size:0.62rem; font-weight:600; background:#f3f4f6;
  color:#374151; margin-right:4px; margin-bottom:3px; }
.mem-off-banner { background:#fef2f2; border:1px solid #fecaca;
  border-radius:8px; padding:10px 14px; margin-bottom:12px;
  color:#dc2626; font-weight:600; font-size:0.82rem; }
.mem-on-banner  { background:#f0fdf4; border:1px solid #bbf7d0;
  border-radius:8px; padding:10px 14px; margin-bottom:12px;
  color:#16a34a; font-weight:600; font-size:0.82rem; }
/* chat hero strip */
.chat-hero { background:#111827; border-radius:10px;
  padding:16px 20px; margin-bottom:16px; }
.chat-hero-title { font-size:1rem; font-weight:800;
  color:#f9fafb; margin-bottom:3px; letter-spacing:-0.3px; }
.chat-hero-sub { font-size:0.78rem; color:#9ca3af; line-height:1.4; }

/* ── Pipeline ────────────────────────────────────── */
.jp-pipeline { display:flex; align-items:center; gap:0; margin:12px 0; flex-wrap:wrap; }
.jp-pipe-box  { background:#fafafa; border:1px solid #f0f0f0; border-radius:6px;
  padding:6px 10px; font-size:0.72rem; color:#6b7280; text-align:center; min-width:72px; }
.jp-pipe-ok   { border-color:#bbf7d0; color:#16a34a; background:#f0fdf4; }
.jp-pipe-arrow { color:#d1d5db; font-size:1rem; padding:0 4px; }
.jp-mem-chunk { background:#fafafa; border:1px solid #f0f0f0;
  border-left:3px solid #6b7280; border-radius:0 8px 8px 0;
  padding:10px 12px; margin-bottom:6px; color:#374151; font-size:0.74rem; line-height:1.5; }

/* ── Customer card ───────────────────────────────── */
.cust-card { background:#fff; border:1px solid #f0f0f0;
  border-radius:8px; padding:14px 16px; margin-bottom:8px; }
.cust-name { color:#111827; font-weight:700; font-size:0.95rem; }
.cust-meta { color:#9ca3af; font-size:0.76rem; margin-top:2px; }

/* ── Mobile ──────────────────────────────────────── */
@media (max-width:640px) {
  .nr-topbar { flex-direction:column; align-items:flex-start; gap:6px; }
  .call-active-bar { flex-direction:column; gap:4px; }
}
</style>""", unsafe_allow_html=True)


# ── States ────────────────────────────────────────────────────────────────────
IDLE     = "idle"
RINGING  = "ringing"
ACTIVE   = "active"
POSTCALL = "postcall"

AREAS = [f"Sector {i}" for i in range(1, 9)]
PLANS = ["50Mbps", "100Mbps", "200Mbps", "500Mbps"]

QUICK_ACTIONS = [
    ("🔴 Escalate",       "escalate",       "Escalated to field team"),
    ("📅 Schedule Visit", "schedule_visit", "Field visit scheduled"),
    ("🔄 OLT Reboot",     "olt_reboot",     "OLT port rebooted remotely"),
    ("📦 Replace ONT",    "replace_ont",    "ONT replacement ordered"),
]

# ── Scripted demo scenarios (auto-played customer lines) ──────────────────────
DEMO_SCENARIOS = [
    {
        "id":       "ont_expiry",
        "title":    "ONT Red LOS + Plan Expiring",
        "customer": "Priya Sharma",
        "phone":    "+91-9876501001",
        "color":    "#f97316",
        "icon":     "📡",
        "tagline":  "3× recurring hardware fault · Plan expires in 8 days",
        "badges":   [("Recurring ×3","#7c2d12","#fb923c"),
                     ("Expiring Soon","#422006","#fbbf24"),
                     ("Frustration 6.4","#450a0a","#fca5a5")],
        "script": [
            {"delay": 0, "text": "Hello, my internet is not working again. All the lights on my router are red."},
            {"delay": 5, "text": "This is the third time this month! I am very frustrated with this situation."},
            {"delay": 6, "text": "I have the TP-Link ONT. I'm on the 100 Mbps plan in Sector 3."},
            {"delay": 7, "text": "Every time you just reboot it and it works for a few days, then same problem again."},
            {"delay": 6, "text": "Can you please fix this permanently? I cannot keep taking time off work for this."},
            {"delay": 5, "text": "Also — nobody told me my plan is expiring soon. I did not get any renewal reminder!"},
        ],
    },
    {
        "id":       "suspended",
        "title":    "Suspended Account — Angry Customer",
        "customer": "Deepika Rao",
        "phone":    "+91-9876501002",
        "color":    "#ef4444",
        "icon":     "⛔",
        "tagline":  "Account suspended 28 days ago · Escalation risk",
        "badges":   [("SUSPENDED","#450a0a","#fca5a5"),
                     ("Escalation Risk","#3b0764","#c084fc"),
                     ("High Anger","#450a0a","#ef4444")],
        "script": [
            {"delay": 0, "text": "My internet is completely dead! I cannot connect at all!"},
            {"delay": 4, "text": "I already paid my bill last month. Why is my connection suspended without any warning?"},
            {"delay": 5, "text": "I have work deadlines and your team just cut my internet without sending any message."},
            {"delay": 6, "text": "I want this fixed right now or I am switching to your competitor. This is completely unacceptable."},
            {"delay": 5, "text": "What do you mean it expired 28 days ago? I never received any renewal notice from you!"},
        ],
    },
    {
        "id":       "slow_speed",
        "title":    "Peak-Hour Slow Speeds + 2-Day Expiry",
        "customer": "Vikram Singh",
        "phone":    "+91-9876501004",
        "color":    "#38bdf8",
        "icon":     "🐢",
        "tagline":  "Evening speed drops · Plan expires in 2 days",
        "badges":   [("Speed Issue","#0c2a4a","#7dd3fc"),
                     ("EXPIRING 2d","#422006","#fbbf24"),
                     ("WFH Impact","#0c1a3a","#93c5fd")],
        "script": [
            {"delay": 0, "text": "Hello, I am getting very slow internet speed every single evening."},
            {"delay": 5, "text": "During the day it is fine, but after 6 PM it becomes almost unusable."},
            {"delay": 6, "text": "I am paying for 100 Mbps plan but I get barely 10 Mbps at peak hours."},
            {"delay": 7, "text": "I work from home and this is affecting my video calls. My clients are complaining."},
            {"delay": 5, "text": "Can you check if there is a problem in my area? Is it my equipment or the network?"},
        ],
    },
]


# ── Session state ─────────────────────────────────────────────────────────────
def _init():
    defaults: dict = {
        "call_state":          IDLE,
        "ringing_id":          None,
        "ringing_phone":       "",
        "active_id":           None,
        "active_call_id":      None,
        "call_start":          None,
        "transcript":          [],
        "copilot_data":        {},
        "call_memories":       {"customer": [], "network": []},
        "post_data":           {},
        "live_notes":          {},
        "last_extraction_at":  0,
        "decision_log":        [],
        "db_obj":              None,
        "re_obj":              None,
        "detector_obj":        None,
        "copilot_obj":         None,
        "groq_ok":             False,
        "hindsight_ok":        False,
        "last_alert":          {},
        "new_customer_mode":   False,
        "incoming_phone":      "",
        # ── Twilio real-time ──────────────────────────────────────────────
        "twilio_call_sid":     None,   # Twilio CallSid for the current live call
        "last_tx_id":          0,      # live_transcripts high-water mark
        "last_signal_id":      0,      # call_signals high-water mark
        # ── Judges Portal ─────────────────────────────────────────────────
        "judge_profile":       {},     # generated + editable profile dict
        "judge_generated":     False,  # True after AI generation
        "judge_seeded":        False,  # True after seed to DB + Hindsight
        "judge_mem_results":   [],     # last Hindsight recall results
        # ── Demo mode ─────────────────────────────────────────────────────
        "memory_off_mode":     False,  # True = bypass all Hindsight recall/retain
        "retain_confirmed":    False,  # True after successful post-call retain
        # ── Live Demo Call (Twilio outbound) ──────────────────────────────
        "live_demo_status":    "idle",   # idle|calling|ringing|connected|ended
        "live_demo_call_sid":  "",
        "live_demo_phone":     "",
        "live_demo_name":      "",
        # ── Scripted auto-play demo ───────────────────────────────────────
        "demo_running":        False,
        "demo_scenario":       {},
        "demo_step_idx":       0,
        "demo_next_ts":        0.0,
        "demo_paused":         False,
        "demo_speed":          1.0,
        # ── Chat Demo (text-based AI interface for judges) ────────────────
        "chat_messages":       [],     # [{role:"user"|"agent", text:str, mem_log:dict}]
        "chat_customer":       {},     # the seeded judge profile
        "chat_seeded":         False,  # True after seeding to DB+Hindsight
        "chat_generated":      False,  # True after AI profile generation
        "agent_obj":           None,   # NetRecallAgent singleton
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ── Client bootstrap ──────────────────────────────────────────────────────────
@st.cache_resource
def _build():
    gk  = os.getenv("GROQ_API_KEY", "")
    hu  = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    hk  = os.getenv("HINDSIGHT_API_KEY", "")
    gcl = hcl = None
    gok = hok = False

    if gk:
        try:
            gcl = Groq(api_key=gk)
            gcl.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=4,
            )
            gok = True
        except Exception:
            pass

    if hk and hu:
        try:
            from hindsight_client import Hindsight
            hcl = Hindsight(base_url=hu, api_key=hk)
            hcl.recall(bank_id="netrecall-customers", query="ping", max_tokens=5)
            hok = True
        except Exception as e:
            err = str(e).lower()
            hok = not any(x in err for x in ["refused", "timeout", "unreachable", "nodename"])
            if hcl is None and hk and hu:
                try:
                    from hindsight_client import Hindsight
                    hcl = Hindsight(base_url=hu, api_key=hk)
                except Exception:
                    pass

    return gcl, hcl, gok, hok


gcl, hcl, gok, hok = _build()

# Init singletons once per session
if st.session_state.re_obj is None:
    db_path = os.path.join(os.path.dirname(__file__), "netrecall.db")
    db = CustomerDB(db_path)
    st.session_state.db_obj       = db
    st.session_state.re_obj       = ResolutionEngine(db, hcl if hok else None)
    st.session_state.detector_obj = PatternDetector(hcl if hok else None)
    st.session_state.copilot_obj  = CoPilot(gcl, hcl if hok else None)
    st.session_state.groq_ok      = gok
    st.session_state.hindsight_ok = hok

if st.session_state.agent_obj is None:
    st.session_state.agent_obj = NetRecallAgent(gcl, hcl if hok else None)

db:       CustomerDB    = st.session_state.db_obj
re_eng:   ResolutionEngine = st.session_state.re_obj
detector: PatternDetector  = st.session_state.detector_obj
copilot:  CoPilot          = st.session_state.copilot_obj


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:10px 4px;">'
        '<div style="color:#111827;font-size:1.1rem;font-weight:900;">📡 NetRecall</div>'
        '<div style="color:#9ca3af;font-size:0.73rem;">ISP Intelligence · Hindsight AI</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    gd = "🟢 Connected" if gok else "🔴 Offline"
    hd = "🟢 Connected" if hok else "🔴 Offline"
    nc = db.get_customer_count()
    st.markdown(
        f'<div style="font-size:0.78rem;line-height:1.9;">'
        f'<div>Groq LLM <span style="float:right;font-weight:700;">{gd}</span></div>'
        f'<div>Hindsight Memory <span style="float:right;font-weight:700;">{hd}</span></div>'
        f'<div>Customers in DB <span style="float:right;font-weight:700;color:#111827;">{nc}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    st.markdown("**📦 Seed Customer Database**")
    st.caption("Load 15 demo ISP customers with full ticket history + Hindsight memory banks.")

    if st.button("🌱 Seed Customer Database", type="primary", use_container_width=True):
        import seed_data as sd
        pb = st.progress(0.0, text="Starting…")
        errors: list[str] = []

        # ── 1. Seed SQLite ────────────────────────────────────────────────
        all_customers = sd.CUSTOMERS
        all_tickets   = [t for c in all_customers for t in c["tickets"]]
        sqlite_total  = len(all_customers) + len(all_tickets)
        done = 0

        for c in all_customers:
            try:
                db.upsert_customer(
                    customer_id=c["id"],
                    name=c["name"],
                    phone=c["phone"],
                    email=c.get("email", ""),
                    area=c.get("area", ""),
                    plan=c.get("plan", ""),
                    equipment=c.get("equipment", ""),
                    account_number=c.get("account_number", ""),
                    address=c.get("address", ""),
                    plan_expiry=c.get("plan_expiry", ""),
                    plan_status=c.get("plan_status", "active"),
                    monthly_rate=c.get("monthly_rate", 0),
                )
            except Exception as e:
                errors.append(f"Customer {c['id']}: {e}")
            done += 1
            pb.progress(done / (sqlite_total * 2), text=f"Customer: {c['name']}")

        for c in all_customers:
            for t in c["tickets"]:
                try:
                    db.upsert_ticket(
                        ticket_id=t["id"],
                        customer_id=c["id"],
                        issue_type=t.get("type", ""),
                        description=t.get("description", ""),
                        resolution=t.get("resolution", ""),
                        status=t.get("status", "resolved"),
                        date_opened=t.get("date", ""),
                    )
                except Exception as e:
                    errors.append(f"Ticket {t['id']}: {e}")
                done += 1
                pb.progress(done / (sqlite_total * 2), text=f"Ticket: {t['id']}")

        # ── 2. Seed Hindsight ─────────────────────────────────────────────
        if hok and hcl:
            def _hprog(p: float, m: str) -> None:
                pb.progress(0.5 + p * 0.5, text=m[:50])
            h_res = sd.seed_all(hcl, progress_callback=_hprog)
            errors.extend(h_res.get("errors", []))
            st.success(
                f"✅ {db.get_customer_count()} customers · "
                f"{h_res['tickets']} tickets in memory · "
                f"{h_res['network_incidents']} area incidents"
            )
        else:
            pb.progress(1.0, text="Done (SQLite only)")
            st.warning("SQLite seeded. Connect Hindsight to enable AI memory features.")

        if errors:
            with st.expander(f"⚠️ {len(errors)} errors"):
                for err in errors[:10]:
                    st.caption(err)

        st.rerun()

    st.markdown("---")
    # ── Demo Memory Toggle ────────────────────────────────────────────────────
    st.markdown("**🧠 Hindsight Memory**")
    mem_off = st.toggle(
        "Disable Memory (demo comparison)",
        value=st.session_state.memory_off_mode,
        help="Turn OFF to show how the agent behaves WITHOUT memory. Turn ON to restore full Hindsight recall/retain.",
        key="mem_off_toggle",
    )
    if mem_off != st.session_state.memory_off_mode:
        st.session_state.memory_off_mode = mem_off
        st.session_state.retain_confirmed = False
        st.rerun()
    if st.session_state.memory_off_mode:
        st.error("Memory OFF — agent is blind")
    else:
        st.success("Memory ON — Hindsight active")
    st.markdown("---")
    st.caption("NetRecall · Hindsight AI Hackathon 2025")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _recall_for_call(customer: dict) -> dict:
    """Recall customer + network memories from Hindsight."""
    if st.session_state.get("memory_off_mode"):
        return {"customer": [], "network": []}
    cust_mems: list = []
    net_mems:  list = []
    if hok and hcl:
        try:
            r1 = hcl.recall(
                bank_id="netrecall-customers",
                query=(f"Full history of {customer['name']} ({customer['id']}): "
                       f"past tickets, equipment issues, resolutions, patterns"),
                tags=[f"customer:{customer['id']}"],
                tags_match="any_strict",
                budget="mid",
                max_tokens=2000,
            )
            cust_mems = r1.results
        except Exception:
            pass
        try:
            r2 = hcl.recall(
                bank_id="netrecall-network",
                query=f"Area incidents and failures in {customer.get('area','')}",
                tags=[f"sector:{customer.get('area','').lower().replace(' ','-')}"],
                tags_match="any_strict",
                budget="low",
                max_tokens=800,
            )
            net_mems = r2.results
        except Exception:
            pass
    return {"customer": cust_mems, "network": net_mems}


def _retain_call(customer: dict, transcript: list, resolution: str, post_data: dict) -> bool:
    """Retain completed call to Hindsight. Returns True if successfully retained."""
    if st.session_state.get("memory_off_mode"):
        return False
    if not (hok and hcl) or not transcript:
        return False
    try:
        content = (
            f"Support call with {customer['name']} ({customer['id']}) "
            f"on {datetime.now().strftime('%Y-%m-%d %H:%M')}:\n"
            + "\n".join(f"{e['speaker'].upper()}: {e['text']}" for e in transcript)
            + f"\nResolution: {resolution or 'Not specified'}"
            + f"\nSummary: {post_data.get('summary', '')}"
        )
        hcl.retain(
            bank_id="netrecall-customers",
            content=content,
            context="completed-call",
            tags=[
                f"customer:{customer['id']}",
                f"sector:{customer.get('area','').lower().replace(' ','-')}",
            ],
            document_id=f"{customer['id']}-call-{datetime.now().isoformat()}",
        )
        return True
    except Exception:
        return False


def _log_action(call_id: str, action: str, note: str):
    """Log a decision to SQLite + session decision log."""
    ts = datetime.now().strftime("%H:%M")
    st.session_state.decision_log.append({
        "action": action, "note": note, "timestamp": ts
    })
    if call_id:
        try:
            db.log_action(call_id, action, note)
        except Exception:
            pass
    # Retain action to Hindsight
    if not st.session_state.get("memory_off_mode") and hok and hcl and st.session_state.active_id:
        cust = db.get_customer_by_id(st.session_state.active_id)
        if cust:
            try:
                hcl.retain(
                    bank_id="netrecall-customers",
                    content=f"Action during call with {cust['name']} ({cust['id']}) at {ts}: {note}",
                    context="call-action",
                    tags=[f"customer:{cust['id']}",
                          f"sector:{cust.get('area','').lower().replace(' ','-')}"],
                    document_id=f"{cust['id']}-action-{datetime.now().isoformat()}",
                )
            except Exception:
                pass


def _run_copilot_and_notes() -> None:
    """
    Run note extraction + co-pilot update against the current transcript.
    Called by both _handle_new_customer_line (typed/voice) and the
    Twilio transcript watcher fragment after bulk-appending new lines.
    """
    cid  = st.session_state.active_id
    if not cid:
        return
    cust = db.get_customer_by_id(cid)
    if not cust:
        return

    tx_len = len(st.session_state.transcript)
    if should_extract(tx_len, st.session_state.last_extraction_at):
        new_notes = extract_notes(
            st.session_state.transcript, cust, gcl, window=8
        )
        st.session_state.live_notes = merge_notes(
            st.session_state.live_notes, new_notes
        )
        st.session_state.last_extraction_at = tx_len

    mems      = st.session_state.call_memories
    fs_now    = re_eng.compute_frustration_score(cust)
    alert_now = detector.check_for_pattern(cust.get("area", ""))
    new_cp    = copilot.generate_live_update(
        customer=cust,
        transcript=st.session_state.transcript,
        customer_mems=mems["customer"],
        network_mems=mems["network"],
        frustration_score=fs_now,
        pattern_alert=alert_now,
    )
    st.session_state.copilot_data = new_cp


def _handle_new_customer_line(text: str) -> None:
    """
    Append a typed/voice customer line and trigger notes + co-pilot update.
    Also used by the Twilio transcript watcher (per-line append path).
    """
    cid = st.session_state.active_id
    if not cid:
        return
    cust = db.get_customer_by_id(cid)
    if not cust:
        return

    st.session_state.transcript.append({
        "speaker": "customer",
        "text":    text,
        "ts":      datetime.now().strftime("%H:%M"),
    })
    _run_copilot_and_notes()


def _fmt_timer(start: float) -> str:
    elapsed = int(time.time() - start)
    return f"{elapsed // 60}:{elapsed % 60:02d}"


def _sentiment_html(sentiment: str) -> str:
    colours = {
        "frustrated": ("#ef4444", "Frustrated"),
        "angry":      ("#dc2626", "Angry"),
        "confused":   ("#d97706", "Confused"),
        "neutral":    ("#6b7280", "Neutral"),
        "satisfied":  ("#16a34a", "Satisfied"),
        "relieved":   ("#16a34a", "Relieved"),
    }
    col, label = colours.get(sentiment, ("#6b7280", "Neutral"))
    return (f'<span class="sentiment-chip" style="background:{col}15;color:{col};'
            f'border:1px solid {col}33;">{label}</span>')


def _days_until_expiry(expiry_str: str) -> int:
    """Returns days until expiry (negative = already expired). 9999 = no expiry set."""
    if not expiry_str:
        return 9999
    try:
        expiry = datetime.strptime(expiry_str.strip(), "%Y-%m-%d")
        return (expiry - datetime.now()).days
    except Exception:
        return 9999


def _emotion_face_html(sentiment: str, confidence: int = 50) -> str:
    """Return an animated emoji face HTML card for the given sentiment."""
    configs = {
        "neutral":    {"anim": "breathe 3s ease-in-out infinite",    "emoji": "😐",  "label": "Neutral",    "bar": "#9ca3af"},
        "curious":    {"anim": "breathe 3s ease-in-out infinite",    "emoji": "🤔",  "label": "Curious",    "bar": "#6b7280"},
        "frustrated": {"anim": "em-pulse 1.5s ease-in-out infinite", "emoji": "😤",  "label": "Frustrated", "bar": "#f97316"},
        "angry":      {"anim": "em-shake 0.65s ease-in-out infinite","emoji": "😠",  "label": "Angry",      "bar": "#ef4444"},
        "satisfied":  {"anim": "breathe 3s ease-in-out infinite",    "emoji": "😊",  "label": "Satisfied",  "bar": "#16a34a"},
        "confused":   {"anim": "em-tilt 2s ease-in-out infinite",    "emoji": "😕",  "label": "Confused",   "bar": "#d97706"},
        "relieved":   {"anim": "breathe 3s ease-in-out infinite",    "emoji": "😌",  "label": "Relieved",   "bar": "#16a34a"},
    }
    cfg = configs.get(sentiment, configs["neutral"])
    bar_col = cfg["bar"]
    return (
        f'<div class="emotion-wrap">'
        f'<span class="emotion-emoji" style="animation:{cfg["anim"]};">{cfg["emoji"]}</span>'
        f'<div class="emotion-lbl">{cfg["label"]}</div>'
        f'<div class="emotion-bar-bg">'
        f'<div style="background:{bar_col};width:{confidence}%;height:4px;border-radius:4px;"></div>'
        f'</div>'
        f'<div class="emotion-conf" style="color:{bar_col};">detection {confidence}%</div>'
        f'</div>'
    )


def _customer_dna_panel(cust: dict, fs: dict, tickets: list) -> str:
    """Return HTML for the Customer DNA side panel (left column on active call)."""
    name     = cust.get("name", "Unknown")
    phone    = cust.get("phone", "—")
    area     = cust.get("area", "—")
    plan     = cust.get("plan", "—")
    equip    = (cust.get("equipment") or "—").split("(")[0].strip()
    addr     = cust.get("address", "—")
    acc      = cust.get("account_number", "—")
    rate     = cust.get("monthly_rate", 0) or 0
    expiry   = cust.get("plan_expiry", "")
    p_status = cust.get("plan_status", "active") or "active"
    calls    = cust.get("total_calls", 0) or 0
    score    = fs.get("score", 1.0)

    days = _days_until_expiry(expiry)

    # Plan status badge
    if p_status == "suspended":
        badge = '<span class="dna-badge-s">⛔ SUSPENDED</span>'
    elif days < 0:
        badge = f'<span class="dna-badge-ex">⚠️ EXPIRED {abs(days)}d ago</span>'
    elif days <= 7:
        badge = f'<span class="dna-badge-xp">⏰ {days}d to expire</span>'
    else:
        badge = '<span class="dna-badge-a">✅ ACTIVE</span>'

    # Frustration bar
    score_col = "#22c55e" if score < 4 else "#f97316" if score < 7 else "#ef4444"
    score_pct = int((score / 10) * 100)

    # Ticket rows
    ticket_rows = ""
    for t in tickets[:6]:
        issue = (t.get("issue_type") or "")[:38]
        date  = (t.get("date_opened") or "")[:10]
        sta   = t.get("status", "")
        s_col = "#22c55e" if sta == "resolved" else "#f97316"
        ticket_rows += (
            f'<div class="dna-trow">'
            f'<span class="dna-tdate">{date}</span>'
            f'<span class="dna-ttxt" style="color:{s_col};">{issue}</span>'
            f'</div>'
        )

    rate_str  = f"₹{int(rate)}/mo" if rate else ""
    exp_str   = expiry if expiry else "—"

    return (
        f'<div class="dna-card">'
        f'<div class="dna-panel-sec" style="margin-top:0;">👤 Caller</div>'
        f'<div class="dna-f"><div class="dna-label">Name</div>'
        f'<div class="dna-value" style="font-size:1rem;font-weight:900;">{name}</div></div>'
        f'<div class="dna-f"><div class="dna-label">Mobile</div>'
        f'<div class="dna-value">{phone}</div></div>'
        f'<div class="dna-f"><div class="dna-label">Address</div>'
        f'<div class="dna-value" style="font-size:0.73rem;">{addr}</div></div>'
        f'<div class="dna-f"><div class="dna-label">Account</div>'
        f'<div class="dna-value" style="font-size:0.72rem;">{acc}</div></div>'
        f'<div style="height:1px;background:#f0f0f0;margin:8px 0 2px;"></div>'
        f'<div class="dna-panel-sec">📦 Plan</div>'
        f'<div class="dna-f"><div class="dna-label">Plan</div>'
        f'<div class="dna-value">{plan} {rate_str}</div></div>'
        f'<div class="dna-f"><div class="dna-label">Expires</div>'
        f'<div class="dna-value">{exp_str}</div></div>'
        f'<div class="dna-f"><div class="dna-label">Status</div>'
        f'{badge}</div>'
        f'<div class="dna-f" style="margin-top:4px;"><div class="dna-label">Equipment</div>'
        f'<div class="dna-value" style="font-size:0.71rem;">{equip}</div></div>'
        f'<div style="height:1px;background:#f0f0f0;margin:8px 0 2px;"></div>'
        f'<div class="dna-panel-sec">📊 Profile</div>'
        f'<div class="dna-f"><div class="dna-label">Area / Calls</div>'
        f'<div class="dna-value">{area} · {calls} calls</div></div>'
        f'<div class="dna-f"><div class="dna-label">Frustration</div>'
        f'<div style="display:flex;align-items:center;gap:7px;margin-top:3px;">'
        f'<div class="cp-conf-bar" style="flex:1;">'
        f'<div style="background:{score_col};width:{score_pct}%;height:5px;border-radius:4px;"></div>'
        f'</div>'
        f'<span style="color:{score_col};font-size:0.73rem;font-weight:700;">{score:.1f}/10</span>'
        f'</div></div>'
        f'</div>'
        f'<div class="dna-card" style="padding:9px 12px;margin-top:0;">'
        f'<div class="dna-panel-sec" style="margin-top:0;">🎫 Ticket History</div>'
        + (ticket_rows or
           '<div style="color:#6b7280;font-size:0.71rem;padding:4px 0;">No tickets on record.</div>')
        + '</div>'
    )


def _generate_judge_profile(name: str, phone: str) -> dict:
    """
    Build a random but realistic customer profile for a judge.
    Deterministic from name+phone so the same person gets the same profile
    on repeated runs. Uses Groq to write natural-language ticket descriptions.
    """
    import random, uuid, json as _json

    seed_val = sum(ord(c) for c in name + phone)
    rng      = random.Random(seed_val)

    area  = AREAS[seed_val % len(AREAS)]
    plans_with_rate = [
        ("50Mbps",  599),
        ("100Mbps", 999),
        ("200Mbps", 1999),
        ("500Mbps", 2999),
    ]
    plan, rate = plans_with_rate[hash(name) % len(plans_with_rate)]

    equip_templates = [
        f"TP-Link XC220-G3v ONT (SN: TL-{uuid.uuid4().hex[:6].upper()})",
        f"Huawei EG8141A5 ONT (SN: HW-{uuid.uuid4().hex[:6].upper()})",
        f"MikroTik hAP ac3 (SN: MT-{uuid.uuid4().hex[:6].upper()})",
    ]
    equip = equip_templates[seed_val % 3]

    # Expiry — weighted toward dramatic scenarios for the demo
    expiry_days = rng.choice([-8, -3, 2, 5, 9, 30, 60, 75])
    expiry = (datetime.now() + __import__("datetime").timedelta(days=expiry_days)).strftime("%Y-%m-%d")
    p_status = "suspended" if expiry_days < 0 else "active"

    frustration = round(1.0 + (seed_val % 72) / 10.0, 1)
    total_calls = rng.randint(1, 9)

    streets = ["MG Road", "Gandhi Nagar", "Nehru Street", "Park Avenue", "Lake View"]
    address = f"No.{rng.randint(1,50)}, {rng.choice(streets)}, {area}"

    cid = f"JDG-{uuid.uuid4().hex[:8].upper()}"
    acc = f"NET-JDG-{cid[-6:]}"

    profile: dict = {
        "id":               cid,
        "name":             name,
        "phone":            phone,
        "email":            f"{name.lower().replace(' ', '.')[:14]}@gmail.com",
        "area":             area,
        "plan":             plan,
        "equipment":        equip,
        "account_number":   acc,
        "address":          address,
        "plan_expiry":      expiry,
        "plan_status":      p_status,
        "monthly_rate":     rate,
        "frustration_score": frustration,
        "total_calls":      total_calls,
        "tickets":          [],
    }

    # ── AI ticket generation (Groq) ───────────────────────────────────────
    if gcl:
        try:
            resp = gcl.chat.completions.create(
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
                messages=[{
                    "role": "user",
                    "content": (
                        f"Generate 3 realistic Indian ISP fiber broadband support tickets for a customer named "
                        f"{name} on a {plan} plan in {area} using {equip.split('(')[0].strip()}. "
                        f"Return JSON: {{\"tickets\": ["
                        f"{{\"issue_type\":\"...\",\"date_opened\":\"2024-MM-DD\","
                        f"\"description\":\"2-sentence customer complaint\","
                        f"\"resolution\":\"1-sentence fix by ISP tech\","
                        f"\"status\":\"resolved\"}}]}}. "
                        f"Use realistic ISP issues: ONT red LOS, slow speeds, disconnections, DNS failures, "
                        f"power outage recovery, WiFi dead zones. Keep it concise."
                    ),
                }],
                max_tokens=500,
                temperature=0.85,
            )
            raw  = resp.choices[0].message.content
            data = _json.loads(raw)
            tix  = data.get("tickets", [])
            for i, t in enumerate(tix[:3]):
                t["id"] = f"{cid}-T{i+1:02d}"
            profile["tickets"] = tix[:3]
        except Exception:
            pass   # fall through to hardcoded fallback

    # ── Fallback tickets ──────────────────────────────────────────────────
    if not profile["tickets"]:
        fallbacks = [
            ("ONT light blinking red",
             f"ONT showing red LOS light, no internet. {equip.split('(')[0].strip()} not syncing.",
             "Remote ONT reboot via OLT portal cleared LOS. Service restored in 4 minutes."),
            ("Slow speed complaint",
             f"Getting well below {plan} speeds during evening hours 7-10 PM.",
             "OLT port oversubscription identified. Migrated to uncongested port."),
            ("Intermittent disconnection",
             "Connection dropping 3-4 times daily, auto-reconnects after 30-60 seconds.",
             "Faulty SFP module on OLT card replaced. Drops stopped after replacement."),
        ]
        for i, (itype, desc, res) in enumerate(fallbacks[:2]):
            mo = rng.randint(1, 11)
            profile["tickets"].append({
                "id":          f"{cid}-T{i+1:02d}",
                "issue_type":  itype,
                "date_opened": f"2024-{mo:02d}-{rng.randint(1,28):02d}",
                "description": desc,
                "resolution":  res,
                "status":      "resolved",
            })

    return profile


def _seed_judge_profile(profile: dict) -> None:
    """Write judge profile to SQLite + Hindsight memory banks."""
    try:
        db.upsert_customer(
            customer_id=profile["id"],
            name=profile["name"],
            phone=profile["phone"],
            email=profile.get("email", ""),
            area=profile.get("area", ""),
            plan=profile.get("plan", ""),
            equipment=profile.get("equipment", ""),
            account_number=profile.get("account_number", ""),
            address=profile.get("address", ""),
            plan_expiry=profile.get("plan_expiry", ""),
            plan_status=profile.get("plan_status", "active"),
            monthly_rate=profile.get("monthly_rate", 0),
        )
        db.update_frustration_score(
            profile["id"], profile.get("frustration_score", 1.0)
        )
        for t in profile.get("tickets", []):
            db.upsert_ticket(
                ticket_id=t["id"],
                customer_id=profile["id"],
                issue_type=t.get("issue_type", ""),
                description=t.get("description", ""),
                resolution=t.get("resolution", ""),
                status=t.get("status", "resolved"),
                date_opened=t.get("date_opened", ""),
            )
    except Exception as e:
        st.error(f"SQLite seed error: {e}")

    if not (hok and hcl):
        return

    cid_tag    = f"customer:{profile['id']}"
    sector_tag = f"sector:{profile.get('area','').lower().replace(' ','-')}"
    rate_str   = f"Rs.{int(profile.get('monthly_rate',0))}/month"

    try:
        hcl.retain(
            bank_id="netrecall-customers",
            content=(
                f"{profile['name']} (ID: {profile['id']}, Account: {profile['account_number']}) "
                f"is a customer in {profile.get('area','')}. "
                f"Plan: {profile.get('plan','')} fiber broadband at {rate_str}. "
                f"Equipment: {profile.get('equipment','')}. "
                f"Phone: {profile['phone']}. Address: {profile.get('address','')}. "
                f"Plan expires: {profile.get('plan_expiry','')}. "
                f"Status: {profile.get('plan_status','active')}. "
                f"Frustration score: {profile.get('frustration_score',1.0)}/10."
            ),
            context="judge-customer-profile",
            tags=[cid_tag, sector_tag, "judge-profile"],
            document_id=f"profile-{profile['id']}",
        )
    except Exception:
        pass

    for t in profile.get("tickets", []):
        try:
            hcl.retain(
                bank_id="netrecall-customers",
                content=(
                    f"Support ticket {t['id']} for {profile['name']} ({profile['id']}) "
                    f"opened {t.get('date_opened','')}:\n"
                    f"Issue: {t.get('issue_type','')}\n"
                    f"Description: {t.get('description','')}\n"
                    f"Resolution: {t.get('resolution','')}\n"
                    f"Status: {t.get('status','resolved')}"
                ),
                context="judge-support-ticket",
                tags=[cid_tag, sector_tag,
                      f"issue:{t.get('issue_type','').lower().replace(' ','-')}"],
                document_id=t["id"],
            )
        except Exception:
            pass


def _twilio_hangup_active_call() -> None:
    """
    Call Twilio REST API to terminate the active call.
    Used by the End Call button. Silently does nothing if Twilio is not
    configured or the call is already ended.
    """
    call_sid     = st.session_state.get("twilio_call_sid")
    account_sid  = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token   = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not (call_sid and account_sid and auth_token):
        return
    try:
        from twilio.rest import Client as TwilioClient  # lazy import
        TwilioClient(account_sid, auth_token).calls(call_sid).update(
            status="completed"
        )
    except Exception:
        pass  # Don't block the UI transition


def _normalize_phone(raw: str) -> str:
    """
    Convert various Indian mobile number formats to E.164.
    Returns empty string if invalid.
    """
    import re
    s = re.sub(r"[\s\-\(\)]", "", raw.strip())
    # Already E.164 with country code
    if s.startswith("+"):
        return s
    # 91XXXXXXXXXX → +91XXXXXXXXXX
    if s.startswith("91") and len(s) == 12:
        return "+" + s
    # 10-digit Indian number starting with 6-9
    if len(s) == 10 and s[0] in "6789":
        return "+91" + s
    return s if s else ""


def _validate_phone(phone: str) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    if not phone:
        return False, "Phone number is required."
    import re
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return False, "Number too short."
    if phone.startswith("+91") and len(digits) == 12:
        if phone[3] not in "6789":
            return False, "Indian mobiles start with 6, 7, 8, or 9."
    return True, ""


# ── Scripted demo runner ───────────────────────────────────────────────────────

@st.fragment(run_every=1)
def _demo_runner() -> None:
    """
    Auto-play scripted demo messages during an ACTIVE call.
    Fires the next customer line from DEMO_SCENARIOS script at the scheduled time.
    """
    if not st.session_state.get("demo_running"):
        return
    if st.session_state.call_state != ACTIVE:
        return
    if st.session_state.get("demo_paused"):
        return

    script   = st.session_state.get("demo_scenario", {}).get("script", [])
    step_idx = st.session_state.get("demo_step_idx", 0)

    if step_idx >= len(script):
        st.session_state.demo_running = False
        return

    if time.time() < st.session_state.get("demo_next_ts", 0):
        return

    # Fire next message
    msg = script[step_idx]["text"]
    st.session_state.demo_step_idx = step_idx + 1

    # Schedule next
    if step_idx + 1 < len(script):
        speed = st.session_state.get("demo_speed", 1.0)
        nxt   = script[step_idx + 1].get("delay", 5)
        st.session_state.demo_next_ts = time.time() + nxt / speed
    else:
        st.session_state.demo_running = False

    _handle_new_customer_line(msg)
    st.rerun()


# ── Twilio real-time fragment watchers ────────────────────────────────────────
# Each runs independently every 2 s. They write to session_state and call
# st.rerun() only when something actually changed.

@st.fragment(run_every=2)
def _twilio_ringing_watcher() -> None:
    """
    Poll incoming_calls for a new Twilio call while the app is IDLE.
    Sets RINGING state and populates ringing_id / incoming_phone.
    """
    if st.session_state.call_state != IDLE:
        return
    _db: CustomerDB = st.session_state.db_obj
    if _db is None:
        return

    pending = _db.get_pending_incoming_call()
    if pending is None:
        return

    call_sid   = pending["call_sid"]
    from_phone = pending["from_phone"]
    st.session_state.twilio_call_sid = call_sid

    # Try E.164 (+919876501001) then hyphenated (+91-9876501001) format
    customer = _db.get_customer_by_phone(from_phone)
    if customer is None and from_phone.startswith("+91") and len(from_phone) == 13:
        customer = _db.get_customer_by_phone(f"+91-{from_phone[3:]}")

    if customer:
        st.session_state.ringing_id    = customer["id"]
        st.session_state.call_state    = RINGING
        st.session_state.incoming_phone = from_phone
    else:
        # Unknown caller → new customer registration form
        st.session_state.new_customer_mode = True
        st.session_state.incoming_phone    = from_phone
        st.session_state.call_state        = RINGING
    st.rerun()


@st.fragment(run_every=2)
def _twilio_transcript_watcher() -> None:
    """
    Poll live_transcripts for new Twilio STT lines during an active call.
    Appends each new line to the transcript and triggers co-pilot update.
    """
    if st.session_state.call_state != ACTIVE:
        return
    call_sid = st.session_state.get("twilio_call_sid")
    if not call_sid:
        return

    _db: CustomerDB = st.session_state.db_obj
    new_rows = _db.get_new_transcripts(call_sid, after_id=st.session_state.last_tx_id)
    if not new_rows:
        return

    for row in new_rows:
        st.session_state.transcript.append({
            "speaker":    "customer",
            "text":       row["text"],
            "ts":         datetime.now().strftime("%H:%M"),
            "confidence": round(row.get("confidence", 0.0), 2),
        })
        st.session_state.last_tx_id = row["id"]

    _run_copilot_and_notes()
    st.rerun()


@st.fragment(run_every=2)
def _twilio_hangup_watcher() -> None:
    """
    Poll call_signals for terminal events (completed/failed/etc).
    Transitions ACTIVE → POSTCALL or RINGING → IDLE on caller hangup.
    """
    if st.session_state.call_state not in (ACTIVE, RINGING):
        return
    call_sid = st.session_state.get("twilio_call_sid")
    if not call_sid:
        return

    _db: CustomerDB = st.session_state.db_obj
    terminal = {"completed", "failed", "busy", "no-answer", "canceled"}
    signals  = _db.get_new_signals(call_sid, after_id=st.session_state.last_signal_id)

    for sig in signals:
        st.session_state.last_signal_id = sig["id"]
        if sig["signal"] in terminal:
            if st.session_state.call_state == RINGING:
                st.session_state.call_state     = IDLE
                st.session_state.ringing_id     = None
                st.session_state.incoming_phone = ""
                st.session_state.twilio_call_sid = None
            else:
                st.session_state.call_state = POSTCALL
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TWILIO WATCHERS + DEMO RUNNER — register all auto-running fragments
# ═══════════════════════════════════════════════════════════════════════════════
_twilio_ringing_watcher()
_twilio_transcript_watcher()
_twilio_hangup_watcher()
_demo_runner()   # scripted demo auto-player (runs every 1 s)


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE INPUT — poll at very top of every render cycle
# ═══════════════════════════════════════════════════════════════════════════════
_voice_text = poll_voice_input()
if _voice_text and st.session_state.call_state == ACTIVE:
    _handle_new_customer_line(_voice_text)
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TOP BAR
# ═══════════════════════════════════════════════════════════════════════════════
state = st.session_state.call_state
tb_logo, tb_right = st.columns([5, 2])

with tb_logo:
    if state == ACTIVE:
        cid  = st.session_state.active_id
        cust = db.get_customer_by_id(cid) or {}
        fs   = re_eng.compute_frustration_score(cust)
        timer_str = _fmt_timer(st.session_state.call_start) if st.session_state.call_start else "0:00"
        mem_count = (len(st.session_state.call_memories.get("customer", [])) +
                     len(st.session_state.call_memories.get("network", [])))
        st.markdown(
            f'<div class="call-active-bar">'
            f'<div><span class="call-cname">📞 {cust.get("name","")}</span>'
            f' <span class="call-meta"> · {cust.get("area","")} · {cust.get("plan","")}'
            f' · {(cust.get("equipment","") or "").split("(")[0].strip()}'
            f' &nbsp;|&nbsp; {fs["badge"]} {fs["score"]}/10 risk</span></div>'
            f'<div class="call-timer">🟢 LIVE · {timer_str}'
            f'{"  ·  🧠 " + str(mem_count) + " memories" if mem_count else ""}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        gd = "🟢" if gok else "🔴"
        hd = "🟢" if hok else "🔴"
        nc = db.get_customer_count()
        st.markdown(
            f'<div class="nr-topbar">'
            f'<div><span class="nr-logo">NetRecall</span>'
            f'<span class="nr-sub">ISP Support Intelligence</span></div>'
            f'<div class="nr-status">{gd} Groq &nbsp;·&nbsp; {hd} Hindsight &nbsp;·&nbsp; '
            f'{nc} customer{"s" if nc != 1 else ""}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

with tb_right:
    st.markdown("<br>", unsafe_allow_html=True)
    if state == ACTIVE:
        if st.button("📵 End Call", type="primary", use_container_width=True):
            _twilio_hangup_active_call()   # hang up the real call if active
            st.session_state.call_state = POSTCALL
            st.rerun()
    elif state == RINGING:
        rcid = st.session_state.ringing_id
        if rcid:
            rcust = db.get_customer_by_id(rcid) or {}
            if st.button("📞 Answer", type="primary", use_container_width=True):
                with st.spinner(f"Loading {rcust.get('name','customer')} history..."):
                    mems  = _recall_for_call(rcust)
                    fs    = re_eng.compute_frustration_score(rcust)
                    alert = detector.check_for_pattern(rcust.get("area", ""))
                    cpdata = copilot.generate_initial_briefing(
                        customer=rcust,
                        customer_mems=mems["customer"],
                        network_mems=mems["network"],
                        frustration_score=fs,
                        pattern_alert=alert,
                    )
                    call_id = db.start_call(rcid)
                    re_eng.record_live_call(rcid)

                # Link real Twilio call and snapshot high-water marks so the
                # transcript watcher only reads lines spoken AFTER answering.
                call_sid = st.session_state.get("twilio_call_sid")
                if call_sid:
                    db.mark_incoming_call_answered(call_sid, rcid)
                    tx_snap  = db.get_new_transcripts(call_sid, after_id=0)
                    sig_snap = db.get_new_signals(call_sid, after_id=0)
                    st.session_state.last_tx_id     = tx_snap[-1]["id"]  if tx_snap  else 0
                    st.session_state.last_signal_id = sig_snap[-1]["id"] if sig_snap else 0
                else:
                    st.session_state.last_tx_id     = 0
                    st.session_state.last_signal_id = 0

                st.session_state.last_alert[rcid]   = alert
                st.session_state.call_memories      = mems
                st.session_state.copilot_data       = cpdata
                st.session_state.active_id          = rcid
                st.session_state.active_call_id     = call_id
                st.session_state.ringing_id         = None
                st.session_state.call_state         = ACTIVE
                st.session_state.call_start         = time.time()
                st.session_state.transcript         = []
                st.session_state.live_notes         = {}
                st.session_state.last_extraction_at = 0
                st.session_state.decision_log       = []
                st.session_state.retain_confirmed   = False  # reset for new call
                # ── Scripted demo: arm the first message ─────────────────
                if st.session_state.get("demo_running"):
                    speed = st.session_state.get("demo_speed", 1.0)
                    first_delay = st.session_state.get("demo_scenario", {}).get(
                        "script", [{}])[0].get("delay", 0)
                    st.session_state.demo_next_ts = time.time() + max(first_delay, 3) / speed
                # ── Live demo: mark connected ─────────────────────────────
                if st.session_state.get("live_demo_status") in ("calling", "ringing"):
                    st.session_state.live_demo_status = "connected"
                st.rerun()
        if st.button("Decline", use_container_width=True):
            _twilio_hangup_active_call()
            st.session_state.ringing_id     = None
            st.session_state.incoming_phone = ""
            st.session_state.twilio_call_sid = None
            st.session_state.call_state     = IDLE
            st.rerun()
    else:
        # IDLE / POSTCALL — quick simulate from top-right
        phone_input = st.text_input(
            "Simulate by phone",
            value=st.session_state.incoming_phone,
            placeholder="+91XXXXXXXXXX",
            label_visibility="visible",
            key="phone_sim_input",
        )
        if st.button("▶ Simulate Call", type="secondary",
                     use_container_width=True, key="sim_btn"):
            num = phone_input.strip()
            if num:
                detector.record_ticket("incoming", "caller", "unknown", "incoming call")
                existing = db.get_customer_by_phone(num)
                if existing:
                    st.session_state.ringing_id    = existing["id"]
                    st.session_state.call_state    = RINGING
                    st.session_state.incoming_phone = ""
                else:
                    st.session_state.new_customer_mode = True
                    st.session_state.incoming_phone    = num
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE: RINGING
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.call_state == RINGING:
    rid   = st.session_state.ringing_id
    rcust = db.get_customer_by_id(rid) if rid else {}
    if not rcust:
        st.session_state.call_state = IDLE
        st.rerun()

    fs = re_eng.compute_frustration_score(rcust)

    # ── Ring banner ──────────────────────────────────────────────────────────
    r_tickets = db.get_tickets_for_customer(rid)
    r_days    = _days_until_expiry(rcust.get("plan_expiry", ""))
    r_status  = rcust.get("plan_status", "active") or "active"

    st.markdown(
        f"""<div class="ring-banner">
<div class="ring-title">📳 INCOMING CALL — {rcust.get('phone','')}</div>
<div class="ring-sub">Customer identified: <b>{rcust.get('name','')}</b>
 · {rcust.get('account_number','')}</div>
<div class="ring-preview">
  📍 {rcust.get('area','')} &nbsp;·&nbsp;
  📶 {rcust.get('plan','')} &nbsp;·&nbsp;
  🖥️ {(rcust.get('equipment','') or '').split('(')[0].strip()} &nbsp;·&nbsp;
  {fs['badge']} Risk {fs['score']}/10
</div>
</div>""",
        unsafe_allow_html=True,
    )

    # ── Pre-call AI Insights ─────────────────────────────────────────────────
    if st.session_state.get("memory_off_mode"):
        st.markdown(
            '<div style="background:#fff5f5;border:2px solid #f87171;border-radius:12px;'
            'padding:16px 20px;margin-bottom:12px;">'
            '<div style="color:#dc2626;font-size:1rem;font-weight:800;margin-bottom:6px;">'
            '🔴 MEMORY OFF — Agent Is Blind</div>'
            '<div style="color:#6b7280;font-size:0.82rem;">Hindsight memory is disabled. '
            'The agent has no recall of this customer\'s history, tickets, frustration score, '
            'or plan details. The caller will have to repeat everything.<br><br>'
            '<b style="color:#d97706;">Toggle Memory ON in the sidebar to see the difference.</b>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div style="font-size:0.9rem;font-weight:700;color:#111827;margin-bottom:8px;">🧠 Pre-Call Intelligence — Know Before You Pick Up</div>', unsafe_allow_html=True)
    ri_col1, ri_col2 = st.columns(2)

    with ri_col1:
        # Plan status insight
        if r_status == "suspended":
            st.markdown(
                '<div class="pc-insight pc-insight-crit">'
                '<div class="pc-insight-title">⛔ Plan SUSPENDED</div>'
                '<div class="pc-insight-body">Account is currently suspended. '
                'Customer likely calling to reactivate. Have billing team on standby.</div>'
                '</div>', unsafe_allow_html=True)
        elif r_days < 0:
            st.markdown(
                f'<div class="pc-insight pc-insight-crit">'
                f'<div class="pc-insight-title">⚠️ Plan EXPIRED {abs(r_days)} days ago</div>'
                f'<div class="pc-insight-body">Subscription ended on {rcust.get("plan_expiry","")}. '
                f'Issue may be related to expired service. Offer renewal immediately.</div>'
                f'</div>', unsafe_allow_html=True)
        elif r_days <= 7:
            st.markdown(
                f'<div class="pc-insight pc-insight-warn">'
                f'<div class="pc-insight-title">⏰ Plan Expires in {r_days} Days</div>'
                f'<div class="pc-insight-body">Renewal due {rcust.get("plan_expiry","")}. '
                f'Proactively offer renewal — customer may not be aware.</div>'
                f'</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="pc-insight pc-insight-ok">'
                f'<div class="pc-insight-title">✅ Plan Active · {rcust.get("plan","")} · '
                f'₹{int(rcust.get("monthly_rate",0) or 0)}/mo</div>'
                f'<div class="pc-insight-body">Expires {rcust.get("plan_expiry","N/A")}. '
                f'No billing issues detected.</div>'
                f'</div>', unsafe_allow_html=True)

        # Frustration insight
        fscore = fs.get("score", 1.0)
        if fscore >= 7:
            st.markdown(
                f'<div class="pc-insight pc-insight-crit">'
                f'<div class="pc-insight-title">🔥 HIGH Frustration: {fscore}/10</div>'
                f'<div class="pc-insight-body">{fs.get("reason","Repeated unresolved issues.")} '
                f'Be extra patient — this customer has a history of difficult calls.</div>'
                f'</div>', unsafe_allow_html=True)
        elif fscore >= 4:
            st.markdown(
                f'<div class="pc-insight pc-insight-warn">'
                f'<div class="pc-insight-title">⚠️ Moderate Frustration: {fscore}/10</div>'
                f'<div class="pc-insight-body">{fs.get("reason","Past issues not fully resolved.")} '
                f'Acknowledge delay before jumping to diagnosis.</div>'
                f'</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="pc-insight pc-insight-ok">'
                f'<div class="pc-insight-title">😊 Low Frustration: {fscore}/10</div>'
                f'<div class="pc-insight-body">Customer has had smooth interactions so far. '
                f'Standard approach should work well.</div>'
                f'</div>', unsafe_allow_html=True)

    with ri_col2:
        # Recurring issue insight
        if r_tickets:
            issue_counts: dict = {}
            for t in r_tickets:
                it = t.get("issue_type", "")
                if it:
                    issue_counts[it] = issue_counts.get(it, 0) + 1
            top_issue, top_count = max(issue_counts.items(), key=lambda x: x[1])
            if top_count >= 3:
                st.markdown(
                    f'<div class="pc-insight pc-insight-crit">'
                    f'<div class="pc-insight-title">🔁 Recurring Issue ×{top_count}</div>'
                    f'<div class="pc-insight-body">"{top_issue}" reported {top_count} times. '
                    f'Root cause may not have been fully resolved. Consider escalation this time.</div>'
                    f'</div>', unsafe_allow_html=True)
            elif top_count == 2:
                st.markdown(
                    f'<div class="pc-insight pc-insight-warn">'
                    f'<div class="pc-insight-title">🔄 Pattern Detected ×2</div>'
                    f'<div class="pc-insight-body">"{top_issue}" seen twice before. '
                    f'Watch for the same pattern — check if prior fix was complete.</div>'
                    f'</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="pc-insight pc-insight-ok">'
                    f'<div class="pc-insight-title">📋 {len(r_tickets)} Tickets on Record</div>'
                    f'<div class="pc-insight-body">All past issues appear resolved with no '
                    f'recurring pattern. Latest: "{r_tickets[0].get("issue_type","")}"</div>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="pc-insight pc-insight-ok">'
                '<div class="pc-insight-title">🆕 First-Time Caller</div>'
                '<div class="pc-insight-body">No prior tickets. This is their first support contact. '
                'Start fresh — collect issue details carefully.</div>'
                '</div>', unsafe_allow_html=True)

        # Total calls insight
        total_calls = rcust.get("total_calls", 0) or 0
        if total_calls >= 5:
            st.markdown(
                f'<div class="pc-insight pc-insight-warn">'
                f'<div class="pc-insight-title">📞 Frequent Caller: {total_calls} calls</div>'
                f'<div class="pc-insight-body">Customer has called {total_calls} times. '
                f'May indicate an ongoing structural problem. Consider a field visit.</div>'
                f'</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="pc-insight pc-insight-ok">'
                f'<div class="pc-insight-title">📞 {total_calls} Previous Calls</div>'
                f'<div class="pc-insight-body">Low call frequency. Standard engagement expected.</div>'
                f'</div>', unsafe_allow_html=True)

    st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# STATE: NEW CUSTOMER REGISTRATION (unknown caller)
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.new_customer_mode:
    phone = st.session_state.incoming_phone
    st.markdown(
        f"""<div class="ring-banner">
<div class="ring-title">📳 UNKNOWN CALLER — {phone}</div>
<div class="ring-sub">No customer found for this number. Register now (10 seconds).</div>
</div>""",
        unsafe_allow_html=True,
    )
    with st.form("new_customer_form"):
        nc1, nc2 = st.columns(2)
        name  = nc1.text_input("Full Name *", placeholder="e.g. Priya Sharma")
        area  = nc2.selectbox("Area *", AREAS)
        plan  = nc1.selectbox("Plan *", PLANS)
        equip = nc2.text_input("Equipment", placeholder="e.g. TP-Link ONT")
        email = nc1.text_input("Email (optional)")
        addr  = nc2.text_input("Address (optional)")
        submitted = st.form_submit_button("✅ Register & Answer Call",
                                          type="primary", use_container_width=True)
    if submitted and name.strip():
        try:
            new_id = db.add_customer(
                name=name.strip(), phone=phone,
                email=email.strip(), area=area,
                plan=plan, equipment=equip.strip(), address=addr.strip()
            )
            st.session_state.new_customer_mode = False
            st.session_state.incoming_phone    = ""
            st.session_state.ringing_id        = new_id
            st.session_state.call_state        = RINGING
            # Immediately also seed this new customer into Hindsight
            if hok and hcl:
                try:
                    hcl.retain(
                        bank_id="netrecall-customers",
                        content=(f"{name} is a customer with phone {phone}, "
                                 f"area {area}, plan {plan}, equipment {equip}"),
                        context="customer-profile",
                        tags=[f"customer:{new_id}",
                              f"sector:{area.lower().replace(' ','-')}"],
                        document_id=f"profile-{new_id}",
                    )
                except Exception:
                    pass
            st.rerun()
        except Exception as e:
            st.error(f"Error creating customer: {e}")
    if st.button("← Cancel", use_container_width=True):
        st.session_state.new_customer_mode = False
        st.session_state.incoming_phone    = ""
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE: ACTIVE CALL
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.call_state == ACTIVE:
    cid     = st.session_state.active_id
    cust    = db.get_customer_by_id(cid) or {}
    fs      = re_eng.compute_frustration_score(cust)
    cp      = st.session_state.copilot_data
    alert   = st.session_state.last_alert.get(cid)
    call_id = st.session_state.active_call_id
    tickets = db.get_tickets_for_customer(cid)

    col_dna, col_ai, col_tx = st.columns([1.7, 2.8, 1.5], gap="medium")

    # ── LEFT: Customer DNA Panel ──────────────────────────────────────────────
    with col_dna:
        st.markdown(
            _customer_dna_panel(cust, fs, tickets),
            unsafe_allow_html=True,
        )

    # ── CENTER: Emotion Face + AI Co-Pilot + Live Intelligence ───────────────
    with col_ai:
        # ── Emotion face (animated, updates with sentiment) ──────────────
        sentiment  = cp.get("sentiment", "neutral") if cp else "neutral"
        conf_score = cp.get("confidence", 0) if cp else 0
        st.markdown(
            _emotion_face_html(sentiment, conf_score),
            unsafe_allow_html=True,
        )

        # ── Co-Pilot ─────────────────────────────────────────────────────
        st.markdown('<div style="font-size:1rem;font-weight:700;color:#111827;margin-bottom:6px;">🤖 AI Co-Pilot</div>', unsafe_allow_html=True)

        if not cp:
            st.info("Co-pilot loading… speak a few words to activate.")
        else:
            # SAY THIS NOW
            wts = cp.get("what_to_say_now", "")
            st.markdown(
                f'<div class="cp-what-to-say">'
                f'<div class="cp-wts-label">🗣️ Say This Now</div>'
                f'<div class="cp-wts-text">"{wts}"</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Escalation / Handle card
            if cp.get("escalate"):
                reason = cp.get("escalation_reason", "Recurring issue pattern detected.")
                st.markdown(
                    f'<div class="cp-esc-yes">'
                    f'<div class="cp-sec-title">🚨 ESCALATE THIS CALL</div>'
                    f'<div style="color:#6b7280;font-size:0.77rem;">{reason}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                res_hint = cp.get("suggested_resolution", "Continue standard resolution")
                st.markdown(
                    f'<div class="cp-esc-no">'
                    f'<div class="cp-sec-title">✅ Handle Normally</div>'
                    f'<div style="color:#6b7280;font-size:0.76rem;">{res_hint[:120]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # DO / DON'T
            do_html   = "".join(f'<div class="cp-do">✓ {x}</div>' for x in cp.get("do_say", []))
            dont_html = "".join(f'<div class="cp-dont">✗ {x}</div>' for x in cp.get("dont_say", []))
            if do_html or dont_html:
                st.markdown(
                    f'<div class="cp-section">'
                    f'<div class="cp-sec-title">Do / Don\'t</div>'
                    f'{do_html}{dont_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Diagnosis + confidence
            issue    = cp.get("likely_issue", "Analyzing…")
            conf     = cp.get("confidence", 0)
            conf_col = "#16a34a" if conf >= 80 else "#d97706" if conf >= 55 else "#9ca3af"
            st.markdown(
                f'<div class="cp-section">'
                f'<div class="cp-sec-title">Diagnosis</div>'
                f'<div style="color:#374151;font-size:0.81rem;margin-bottom:5px;">{issue}</div>'
                f'<div class="cp-conf-bar">'
                f'<div style="background:{conf_col};width:{conf}%;height:5px;border-radius:4px;"></div>'
                f'</div>'
                f'<div style="color:{conf_col};font-size:0.72rem;font-weight:700;">{conf}% confidence</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Key points
            tp_list = cp.get("talking_points", [])
            if tp_list:
                st.markdown(
                    '<div class="cp-section">'
                    '<div class="cp-sec-title">Key Points</div>'
                    + "".join(f'<div class="cp-tp">• {x}</div>' for x in tp_list)
                    + '</div>',
                    unsafe_allow_html=True,
                )

        # ── Live Intelligence (below co-pilot) ────────────────────────────
        # Area alert
        if alert:
            st.markdown(
                f'<div class="alert-band">'
                f'<div class="alert-band-title">⚠️ {alert["sector"]} — AREA ALERT</div>'
                f'<div class="alert-band-body">{alert["ticket_count"]} customers · '
                f'{alert["window_minutes"]} min window</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Auto-Notes
        notes_html = notes_to_html(st.session_state.live_notes)
        if notes_html:
            st.markdown(
                f'<div class="intel-card">'
                f'<div class="intel-head">📝 Auto-Notes (AI extracted)</div>'
                f'{notes_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Quick action buttons
        st.markdown(
            '<div class="intel-card">'
            '<div class="intel-head">⚡ Quick Actions</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        action_c1, action_c2 = st.columns(2)
        for i, (label, action_key, note) in enumerate(QUICK_ACTIONS):
            col = action_c1 if i % 2 == 0 else action_c2
            if col.button(label, key=f"act_{action_key}", use_container_width=True):
                _log_action(call_id, action_key, note)
                st.rerun()

        # Decision log
        dlog = st.session_state.decision_log
        if dlog:
            entries_html = "".join(
                f'<div class="action-log-entry">'
                f'<span class="action-log-time">{e["timestamp"]}</span>'
                f'<span class="action-log-text">{e["note"]}</span>'
                f'</div>'
                for e in reversed(dlog[-5:])
            )
            st.markdown(
                f'<div class="intel-card">'
                f'<div class="intel-head">📌 Decision Log</div>'
                f'{entries_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── RIGHT: Transcript + Input ─────────────────────────────────────────────
    with col_tx:
        st.markdown('<div style="font-size:1rem;font-weight:700;color:#111827;margin-bottom:6px;">💬 Transcript</div>', unsafe_allow_html=True)

        # Last 5 transcript lines (compact)
        tx = st.session_state.transcript
        tx_container = st.container(height=240)
        with tx_container:
            if not tx:
                st.markdown(
                    "<div style='color:#94a3b8;text-align:center;margin-top:40px;font-size:0.78rem;'>"
                    "Waiting…<br>Tap mic or type below.</div>",
                    unsafe_allow_html=True,
                )
            for entry in tx[-8:]:
                if entry["speaker"] == "customer":
                    st.markdown(
                        f"<div class='tx-label'>Customer · {entry['ts']}</div>"
                        f"<div class='tx-c'>{entry['text']}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div class='tx-label'>Agent · {entry['ts']}</div>"
                        f"<div class='tx-a'>{entry['text']}</div>",
                        unsafe_allow_html=True,
                    )

        # Full transcript expander
        if len(tx) > 8:
            with st.expander(f"Show all {len(tx)} lines"):
                for entry in tx:
                    label = "Customer" if entry["speaker"] == "customer" else "Agent"
                    st.markdown(f"**{label} ({entry['ts']}):** {entry['text']}")

        # Voice input
        st.markdown("---")
        render_voice_input(height=85)

        # Text input form
        with st.form("tx_form", clear_on_submit=True):
            user_line = st.text_input(
                "Or type:",
                placeholder="What the customer is saying…",
                label_visibility="collapsed",
            )
            sub_col1, sub_col2 = st.columns([3, 1])
            submit = sub_col1.form_submit_button("Log Customer", use_container_width=True)
            log_agent = sub_col2.form_submit_button("Say ✓", type="primary",
                                                     use_container_width=True)

        if submit and user_line.strip():
            _handle_new_customer_line(user_line.strip())
            st.rerun()

        # Log co-pilot suggestion as spoken
        if log_agent and cp.get("what_to_say_now"):
            st.session_state.transcript.append({
                "speaker": "agent",
                "text":    cp["what_to_say_now"],
                "ts":      datetime.now().strftime("%H:%M"),
            })
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE: POST-CALL
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.call_state == POSTCALL:
    cid     = st.session_state.active_id
    cust    = db.get_customer_by_id(cid) or {}
    tx      = st.session_state.transcript
    mems    = st.session_state.call_memories
    fs      = re_eng.compute_frustration_score(cust)
    call_id = st.session_state.active_call_id

    st.markdown('<div style="font-size:1.1rem;font-weight:800;color:#111827;margin-bottom:12px;">📋 Call Ended — Summary & Memory</div>', unsafe_allow_html=True)

    col_sum, col_stats = st.columns([3, 2], gap="large")

    with col_sum:
        resolution = st.text_area(
            "What was the resolution / action taken?",
            placeholder="e.g. Scheduled field visit for ONT replacement. OLT port J2 flagged.",
            height=80,
        )

        if st.button("💾 Generate Summary & Save to Memory",
                     type="primary", use_container_width=True):
            with st.spinner("Generating summary and saving to Hindsight…"):
                post = copilot.generate_post_call_summary(
                    customer=cust, transcript=tx,
                    resolution=resolution, frustration_before=fs,
                )
                retained = _retain_call(cust, tx, resolution, post)
                st.session_state.retain_confirmed = retained

                # Save to SQLite
                if call_id:
                    try:
                        db.end_call(
                            call_id=call_id,
                            transcript=tx,
                            resolution_text=resolution,
                            actions=st.session_state.decision_log,
                            extracted_notes=st.session_state.live_notes,
                            post_call_summary=post,
                            memories_recalled=(len(mems.get("customer", [])) +
                                               len(mems.get("network", []))),
                        )
                    except Exception:
                        pass

                # Update customer frustration score
                if post.get("risk_change") == "worsened":
                    new_score = min(10.0, fs["score"] + 0.5)
                elif post.get("risk_change") == "improved":
                    new_score = max(1.0, fs["score"] - 0.3)
                else:
                    new_score = fs["score"]
                db.update_frustration_score(cid, new_score)

                # Create ticket record
                if resolution:
                    notes = st.session_state.live_notes
                    issue = notes.get("issue_summary") or detect_issue_type(
                        " ".join(e["text"] for e in tx if e["speaker"] == "customer")
                    ) or "General support"
                    db.add_ticket(
                        customer_id=cid,
                        issue_type=issue[:80],
                        description=notes.get("issue_summary", ""),
                        resolution=resolution,
                        status="resolved",
                    )

                st.session_state.post_data = post
            st.rerun()

        pd = st.session_state.post_data
        if pd:
            # Hindsight retain confirmation banner
            if st.session_state.retain_confirmed:
                st.markdown(
                    '<div style="background:#fafafa;border:1px solid #f0f0f0;border-left:3px solid #111827;'
                    'border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:12px;'
                    'display:flex;align-items:center;gap:10px;">'
                    '<span style="font-size:1.3rem;">✅</span>'
                    '<div><div style="color:#111827;font-weight:800;font-size:0.85rem;">'
                    'RETAINED TO HINDSIGHT MEMORY</div>'
                    '<div style="color:#6b7280;font-size:0.75rem;">'
                    'This call is now part of the agent\'s persistent memory. '
                    'The next agent will know everything that happened here.</div></div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif st.session_state.get("memory_off_mode"):
                st.markdown(
                    '<div style="background:#fafafa;border:1px solid #f0f0f0;border-left:3px solid #d97706;'
                    'border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:12px;">'
                    '<span style="color:#111827;font-weight:800;">Memory OFF — Call NOT retained.</span>'
                    '<span style="color:#6b7280;font-size:0.8rem;"> Toggle Memory ON to persist this call to Hindsight.</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div class="pc-card">'
                f'<div class="pc-head">📝 Call Summary</div>'
                f'<div class="pc-body">{pd.get("summary","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="pc-card">'
                f'<div class="pc-head">🔧 Resolution</div>'
                f'<div class="pc-body">{pd.get("resolution_applied","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if pd.get("follow_up_needed"):
                st.markdown(
                    f'<div class="pc-card" style="border-left:3px solid #d97706;">'
                    f'<div class="pc-head">📌 Follow-Up Required</div>'
                    f'<div class="pc-body">{pd.get("follow_up_action","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div class="pc-card" style="border-left:3px solid #111827;">'
                f'<div class="pc-head">🧠 Retained in Memory</div>'
                f'<div class="pc-body">{pd.get("knowledge_gained","")}<br><br>'
                f'<i>Next agent: {pd.get("next_agent_note","")}</i></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            with st.expander("📜 Full Call Transcript"):
                for entry in tx:
                    label = "Customer" if entry["speaker"] == "customer" else "Agent"
                    st.markdown(f"**{label} ({entry['ts']}):** {entry['text']}")

            if st.session_state.decision_log:
                with st.expander("📌 Decision Log"):
                    for d in st.session_state.decision_log:
                        st.markdown(f"`{d['timestamp']}` — **{d['note']}**")

    with col_stats:
        st.markdown('<div style="font-size:0.95rem;font-weight:700;color:#111827;margin-bottom:6px;">📊 Call Stats</div>', unsafe_allow_html=True)
        if st.session_state.call_start:
            elapsed = int(time.time() - st.session_state.call_start)
            st.metric("Call Duration", f"{elapsed//60}m {elapsed%60:02d}s")
        st.metric("Transcript Lines", len(tx))
        st.metric("Memories Recalled", len(mems.get("customer",[])) + len(mems.get("network",[])))
        st.metric("Decisions Logged",  len(st.session_state.decision_log))
        st.metric("Customer Risk",     f"{fs['score']}/10")

        if st.session_state.post_data:
            sentiment_end = st.session_state.post_data.get("customer_sentiment_end", "neutral")
            risk_change   = st.session_state.post_data.get("risk_change", "unchanged")
            rc_col = "#22c55e" if risk_change == "improved" else "#ef4444" if risk_change == "worsened" else "#6b7280"
            st.markdown(
                f'<div class="dna-card" style="margin-top:10px;">'
                f'<div class="dna-label">Customer Sentiment at End</div>'
                f'<div style="margin:5px 0;">{_sentiment_html(sentiment_end)}</div>'
                f'<div class="dna-label" style="margin-top:8px;">Risk Change</div>'
                f'<div style="color:{rc_col};font-weight:700;font-size:0.84rem;'
                f'text-transform:capitalize;">{risk_change}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")
        if st.button("↩ Return to Command Center",
                     use_container_width=True, type="primary"):
            st.session_state.call_state         = IDLE
            st.session_state.active_id          = None
            st.session_state.active_call_id     = None
            st.session_state.call_start         = None
            st.session_state.transcript         = []
            st.session_state.copilot_data       = {}
            st.session_state.post_data          = {}
            st.session_state.live_notes         = {}
            st.session_state.decision_log       = []
            st.session_state.last_extraction_at = 0
            st.session_state.twilio_call_sid    = None
            st.session_state.last_tx_id         = 0
            st.session_state.last_signal_id     = 0
            # ── Reset demo state ─────────────────────────────────────────
            st.session_state.demo_running       = False
            st.session_state.demo_scenario      = {}
            st.session_state.demo_step_idx      = 0
            st.session_state.demo_next_ts       = 0.0
            st.session_state.demo_paused        = False
            if st.session_state.get("live_demo_status") == "connected":
                st.session_state.live_demo_status = "ended"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE: IDLE — Command Center
# ═══════════════════════════════════════════════════════════════════════════════
else:
    tab_queue, tab_chat, tab_customers, tab_dash = st.tabs([
        "📞 Voice Call", "💬 Chat Support", "👥 Customers", "🌐 Network",
    ])

    with tab_queue:
        # ── DEMO: Call Me — judge enters name+phone, AI creates profile + calls them ──
        st.markdown(
            '<div style="background:#111827;border-radius:10px;padding:18px 22px;'
            'margin-bottom:18px;">'
            '<div style="color:#f9fafb !important;font-size:1rem;font-weight:800;margin-bottom:6px;">'
            '📲 Demo — Enter Your Name &amp; Mobile to Get Called</div>'
            '<div style="color:#d1d5db !important;font-size:0.82rem;line-height:1.6;">'
            '1. Enter name + mobile below &nbsp;'
            '2. Click <b style="color:#f9fafb;">Call Me</b> — AI creates your ISP profile &amp; dials your phone &nbsp;'
            '3. Answer → portal shows your pre-call intelligence live<br>'
            '<span style="color:#9ca3af;font-size:0.75rem;">'
            'Can\'t receive calls? Use <b>Simulate</b> instead — same demo, no phone needed.</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        cm1, cm2, cm3, cm4 = st.columns([2, 2, 1, 1], gap="small")
        callme_name  = cm1.text_input("Your Name", placeholder="e.g. Ravi Kumar",
                                       key="callme_name_input")
        callme_phone = cm2.text_input("Your Mobile (+91XXXXXXXXXX)", placeholder="+919876500000",
                                       key="callme_phone_input")
        cm3.markdown("<br>", unsafe_allow_html=True)
        callme_btn = cm3.button("📞 Call Me", type="primary",
                                use_container_width=True, key="callme_btn")
        cm4.markdown("<br>", unsafe_allow_html=True)
        simulate_me_btn = cm4.button("▶ Simulate", use_container_width=True,
                                     key="simulate_me_btn")

        if callme_btn:
            _cm_name  = (callme_name or "").strip()
            _cm_phone = (callme_phone or "").strip()
            if not _cm_name:
                st.warning("Enter your name.")
            elif not _cm_phone:
                st.warning("Enter your mobile number in +91XXXXXXXXXX format.")
            else:
                import re as _re
                _digits    = _re.sub(r"[^\d+]", "", _cm_phone)
                _phone_e164 = _digits if _digits.startswith("+") else "+" + _digits

                twilio_sid    = os.getenv("TWILIO_ACCOUNT_SID", "")
                twilio_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
                twilio_number = os.getenv("TWILIO_PHONE_NUMBER", "")
                webhook_base  = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

                if not all([twilio_sid, twilio_token, twilio_number, webhook_base]):
                    st.error("Twilio credentials not set in .env — check TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, WEBHOOK_BASE_URL")
                else:
                    with st.spinner(f"Creating profile for {_cm_name} and calling {_phone_e164}…"):
                        try:
                            # 1. Generate + seed customer profile to Hindsight
                            _prof = _generate_judge_profile(_cm_name, _phone_e164)
                            _seed_judge_profile(_prof)

                            # 2. Dial via Twilio
                            from twilio.rest import Client as TwilioClient
                            _tcl  = TwilioClient(twilio_sid, twilio_token)
                            _call = _tcl.calls.create(
                                to=_phone_e164,
                                from_=twilio_number,
                                url=f"{webhook_base}/demo-incoming?customer_phone={_phone_e164}",
                                status_callback=f"{webhook_base}/call-status",
                                status_callback_method="POST",
                            )
                            # 3. Pre-register so portal reacts immediately
                            try:
                                db.register_incoming_call(
                                    call_sid=_call.sid,
                                    from_phone=_phone_e164,
                                    to_phone=twilio_number,
                                )
                                db.write_call_signal(
                                    call_sid=_call.sid,
                                    signal="ringing",
                                    payload={"from": _phone_e164, "demo_call": True,
                                             "pre_registered": True},
                                )
                            except Exception:
                                pass

                            st.session_state.live_demo_status   = "calling"
                            st.session_state.live_demo_call_sid = _call.sid
                            st.session_state.live_demo_phone    = _phone_e164
                            st.success(
                                f"✅ Calling {_phone_e164}  |  Profile seeded to Hindsight\n\n"
                                "**Answer your phone.** This portal will switch to RINGING state "
                                "automatically and load your full pre-call intelligence."
                            )
                            st.rerun()
                        except Exception as _cme:
                            _err_str = str(_cme)
                            if "unverified" in _err_str.lower() or "verified" in _err_str.lower():
                                st.warning(
                                    "**Twilio trial account:** Can only call verified numbers.\n\n"
                                    "Your profile was created and seeded to Hindsight ✅  \n"
                                    "To demo the call flow, click **▶ Simulate** — same experience, no phone needed."
                                )
                            else:
                                st.error(f"Call error: {_cme}")

        # Simulate Me — create profile + trigger simulate (no real phone needed)
        if simulate_me_btn:
            _sm_name  = (callme_name or "").strip()
            _sm_phone = (callme_phone or "").strip()
            if not _sm_name:
                st.warning("Enter your name first.")
            else:
                _sm_phone = _sm_phone or f"+91{abs(hash(_sm_name))%10000000000:010d}"
                import re as _re2
                _sm_digits = _re2.sub(r"[^\d+]", "", _sm_phone)
                _sm_e164   = _sm_digits if _sm_digits.startswith("+") else "+" + _sm_digits
                with st.spinner(f"Creating profile for {_sm_name}…"):
                    try:
                        _sm_prof = _generate_judge_profile(_sm_name, _sm_e164)
                        _seed_judge_profile(_sm_prof)
                        st.session_state.ringing_id    = _sm_prof["id"]
                        st.session_state.call_state    = RINGING
                        st.success(f"✅ Profile for {_sm_name} created! Starting demo call…")
                        st.rerun()
                    except Exception as _sme:
                        st.error(f"Error: {_sme}")

        # Show live call status banner
        _ls = st.session_state.get("live_demo_status", "idle")
        if _ls in ("calling", "ringing", "connected"):
            st.markdown(
                f'<div style="border:1px solid #f0f0f0;border-left:3px solid #111827;'
                f'border-radius:0 8px 8px 0;padding:10px 14px;background:#fafafa;">'
                f'<b style="color:#111827;">📞 Outbound call active</b> — '
                f'<span style="color:#6b7280;font-size:0.85rem;">'
                f'{st.session_state.get("live_demo_phone","")} · status: {_ls}'
                f'</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Active area alerts
        for cid_a, alert in st.session_state.last_alert.items():
            if alert:
                affected = ", ".join(alert["affected_customers"])
                st.markdown(
                    f'<div class="alert-band">'
                    f'<div class="alert-band-title">⚠️ AREA ALERT: '
                    f'{alert["sector"]} — {alert["ticket_count"]} tickets in '
                    f'{alert["window_minutes"]} min</div>'
                    f'<div class="alert-band-body">Customers: {affected}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        col_high, col_all = st.columns([2, 3], gap="large")

        with col_high:
            st.markdown('<div style="font-size:1rem;font-weight:700;color:#111827;margin-bottom:4px;">🔴 High-Risk Customers</div>', unsafe_allow_html=True)
            st.caption("Proactively reach out before they call you.")

            try:
                high_risk = db.get_high_frustration_customers(threshold=5.5)
            except Exception:
                high_risk = []

            if not high_risk:
                st.markdown(
                    '<div style="color:#374151;font-size:0.82rem;margin-top:20px;text-align:center;">'
                    'No high-risk customers yet.<br>Risk scores build through call history.</div>',
                    unsafe_allow_html=True,
                )
            for c in high_risk[:6]:
                fs = re_eng.compute_frustration_score(c)
                ca, cb = st.columns([4, 1])
                ca.markdown(
                    f'<div class="queue-card">'
                    f'<div class="queue-name">{fs["badge"]} {c["name"]} — {fs["score"]}/10</div>'
                    f'<div class="queue-meta">{c.get("area","")} · {c.get("plan","")}'
                    f' · {(c.get("equipment","") or "").split("(")[0].strip()}</div>'
                    f'<div class="queue-meta" style="margin-top:2px;">'
                    f'{" · ".join(fs["drivers"][:2])}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if cb.button("📞", key=f"proact_{c['id']}",
                             help=f"Simulate proactive call to {c['name']}"):
                    detector.record_ticket(c["id"], c["name"],
                                           c.get("area", ""), "proactive outreach")
                    st.session_state.ringing_id    = c["id"]
                    st.session_state.call_state    = RINGING
                    st.rerun()

        with col_all:
            st.markdown('<div style="font-size:1rem;font-weight:700;color:#111827;margin-bottom:4px;">📋 All Customers</div>', unsafe_allow_html=True)
            st.caption("Click 📞 to simulate an incoming call.")

            customers = db.get_all_customers()

            if not customers:
                st.markdown(
                    '<div style="background:#f8fafc;border:1px dashed #cbd5e1;'
                    'border-radius:12px;padding:30px;text-align:center;">'
                    '<div style="color:#6b7280;font-size:0.88rem;">No customers yet.</div>'
                    '<div style="color:#94a3b8;font-size:0.78rem;margin-top:8px;">'
                    'Use the "Simulate Incoming" box above to register a new caller,<br>'
                    'or load demo data below.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("---")
                if st.button("🎭 Load Demo Data (2 customers, Sector 4 scenario)",
                             type="primary", use_container_width=True):
                    import demo_seeder
                    pb = st.progress(0, text="Loading demo data…")
                    try:
                        res = demo_seeder.seed_demo(
                            db, hcl if hok else None,
                            progress_callback=lambda p, m: pb.progress(
                                min(p, 1.0), text=m[:50]
                            ),
                        )
                        st.success(
                            f"Loaded {res['customers']} customers, "
                            f"{res['tickets']} tickets, "
                            f"{res['incidents']} incidents",
                            icon="✅"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading demo data: {e}")
            else:
                for c in customers:
                    fs = re_eng.compute_frustration_score(c)
                    ca, cb = st.columns([5, 1])
                    ca.markdown(
                        f'<div class="queue-card">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<span class="queue-name">{fs["badge"]} {c["name"]}</span>'
                        f'<span style="color:#6b7280;font-size:0.73rem;">{c.get("area","")}</span>'
                        f'</div>'
                        f'<div class="queue-meta">'
                        f'{c.get("plan","")} · {(c.get("equipment","") or "").split("(")[0].strip()}'
                        f' · {c.get("phone","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if cb.button("📞", key=f"call_{c['id']}",
                                 help=f"Simulate call from {c['name']}"):
                        detector.record_ticket(
                            c["id"], c["name"],
                            c.get("area", ""), "incoming call"
                        )
                        st.session_state.ringing_id = c["id"]
                        st.session_state.call_state = RINGING
                        st.rerun()

                st.markdown("---")
                if st.button("🎭 Load Demo Data",
                             use_container_width=True, key="load_demo_bottom"):
                    import demo_seeder
                    pb = st.progress(0, text="Loading…")
                    try:
                        res = demo_seeder.seed_demo(
                            db, hcl if hok else None,
                            progress_callback=lambda p, m: pb.progress(
                                min(p, 1.0), text=m[:50]
                            ),
                        )
                        st.success(f"Loaded {res['customers']} customers", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab_queue:
        st.markdown("---")
        st.markdown('<div style="font-size:1rem;font-weight:700;color:#111827;margin-bottom:4px;">📱 Make a Real Phone Call (to any number)</div>', unsafe_allow_html=True)
        st.caption(
            "Dial a real number via Twilio. When they answer, this portal transitions "
            "to RINGING automatically and the pre-call intelligence panel loads."
        )
        rc_col1, rc_col2 = st.columns([3, 1], gap="small")
        with rc_col1:
            real_phone_input = st.text_input(
                "Phone number to call",
                placeholder="+91-XXXXXXXXXX  or  +1-XXXXXXXXXX",
                label_visibility="collapsed",
                key="real_phone_input",
            )
        with rc_col2:
            make_call_btn = st.button("📞 Call Now", type="primary",
                                      use_container_width=True, key="make_real_call_btn")

        if make_call_btn:
            raw_phone = (real_phone_input or "").strip()
            if not raw_phone:
                st.warning("Enter a phone number first.")
            else:
                # Normalise to E.164
                import re as _re
                digits = _re.sub(r"[^\d+]", "", raw_phone)
                phone_e164 = digits if digits.startswith("+") else "+" + digits

                twilio_sid    = os.getenv("TWILIO_ACCOUNT_SID", "")
                twilio_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
                twilio_number = os.getenv("TWILIO_PHONE_NUMBER", "")
                webhook_base  = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

                if not all([twilio_sid, twilio_token, twilio_number, webhook_base]):
                    st.error("Twilio credentials or WEBHOOK_BASE_URL not set in .env")
                else:
                    try:
                        from twilio.rest import Client as TwilioClient
                        tcl = TwilioClient(twilio_sid, twilio_token)
                        call = tcl.calls.create(
                            to=phone_e164,
                            from_=twilio_number,
                            url=f"{webhook_base}/demo-incoming?customer_phone={phone_e164}",
                            status_callback=f"{webhook_base}/call-status",
                            status_callback_method="POST",
                        )
                        # Pre-register immediately so portal reacts without waiting for webhook
                        try:
                            db.register_incoming_call(
                                call_sid=call.sid,
                                from_phone=phone_e164,
                                to_phone=twilio_number,
                            )
                            db.write_call_signal(
                                call_sid=call.sid,
                                signal="ringing",
                                payload={"from": phone_e164, "demo_call": True,
                                         "pre_registered": True},
                            )
                        except Exception:
                            pass
                        st.session_state.live_demo_status  = "calling"
                        st.session_state.live_demo_call_sid = call.sid
                        st.session_state.live_demo_phone   = phone_e164
                        st.success(
                            f"✅ Calling {phone_e164}…  SID: {call.sid[:16]}…\n\n"
                            "When they answer, this portal will automatically switch to "
                            "RINGING state. The pre-call intelligence panel will load instantly."
                        )
                        st.rerun()
                    except Exception as _ce:
                        st.error(f"Twilio error: {_ce}")

        # Show live status if a call is in progress
        live_status = st.session_state.get("live_demo_status", "idle")
        if live_status in ("calling", "ringing", "connected"):
            st.markdown(
                f'<div style="background:#fafafa;border:1px solid #f0f0f0;'
                f'border-left:3px solid #111827;border-radius:0 8px 8px 0;'
                f'padding:10px 14px;margin-top:8px;">'
                f'<div style="font-weight:700;color:#111827;font-size:0.85rem;">'
                f'📞 Live call {live_status} — {st.session_state.get("live_demo_phone","")}</div>'
                f'<div style="color:#6b7280;font-size:0.75rem;margin-top:3px;">'
                f'Portal will auto-transition to RINGING when answered.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAT SUPPORT TAB — two-panel realtime customer ↔ agent window
    # ═══════════════════════════════════════════════════════════════════════
    with tab_chat:
        st.markdown(
            '<div class="chat-hero">'
            '<div class="chat-hero-title">Chat Support — Real-Time Customer Conversation</div>'
            '<div class="chat-hero-sub">'
            'Left panel: you type as the customer. Right panel: NetRecall AI agent responds '
            'using Hindsight memory. Toggle Memory OFF/ON to see the difference instantly.'
            '</div></div>',
            unsafe_allow_html=True,
        )

        chat_agent: NetRecallAgent = st.session_state.agent_obj

        # ── Step 1: Setup ────────────────────────────────────────────────
        with st.expander(
            "⚙️  Step 1 — Generate your customer profile" +
            (" ✅" if st.session_state.chat_seeded else " (required)"),
            expanded=not st.session_state.chat_seeded,
        ):
            cd1, cd2 = st.columns([1, 1], gap="large")
            with cd1:
                with st.form("chat_setup_form"):
                    cd_name  = st.text_input("Your Name", placeholder="e.g. Ravi Kumar",
                                             value=st.session_state.chat_customer.get("name",""))
                    cd_phone = st.text_input("Mobile (optional)",
                                             placeholder="+91-9876500000  or  leave blank",
                                             value=st.session_state.chat_customer.get("phone",""))
                    cd_gen = st.form_submit_button("⚡ Generate Profile + Seed to Hindsight",
                                                   type="primary", use_container_width=True)
                if cd_gen:
                    if not cd_name.strip():
                        st.warning("Enter your name to continue.")
                    else:
                        phone_val = cd_phone.strip() or f"+91-000{abs(hash(cd_name))%10000000:07d}"
                        with st.spinner("Generating profile and seeding Hindsight memory banks…"):
                            try:
                                prof = _generate_judge_profile(cd_name.strip(), phone_val)
                                _seed_judge_profile(prof)
                                st.session_state.chat_customer  = prof
                                st.session_state.chat_generated = True
                                st.session_state.chat_seeded    = True
                                st.session_state.chat_messages  = []
                                st.success(f"✅ Profile for {cd_name.strip()} created and seeded to Hindsight!")
                                st.rerun()
                            except Exception as _ge:
                                st.error(f"Setup error: {_ge}")
            with cd2:
                if st.session_state.chat_generated:
                    prof_prev = st.session_state.chat_customer
                    fs_prev   = re_eng.compute_frustration_score(prof_prev)
                    tix_prev  = prof_prev.get("tickets", [])
                    st.markdown(_customer_dna_panel(prof_prev, fs_prev, tix_prev),
                                unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div style="text-align:center;padding:24px;color:#9ca3af;'
                        'border:1px dashed #e5e7eb;border-radius:8px;">'
                        '<div style="font-size:2rem;margin-bottom:8px;">🧑‍💻</div>'
                        'Enter your name on the left — AI will generate<br>'
                        'a full ISP customer profile and seed Hindsight.</div>',
                        unsafe_allow_html=True,
                    )

        if not st.session_state.chat_seeded:
            st.markdown(
                '<div style="padding:20px;text-align:center;color:#9ca3af;'
                'border:1px dashed #e5e7eb;border-radius:8px;">'
                'Complete Step 1 above to open the chat window.</div>',
                unsafe_allow_html=True,
            )
        else:
            chat_cust = st.session_state.chat_customer
            chat_mem_on = not st.session_state.memory_off_mode

            # ── Memory toggle bar ─────────────────────────────────────────
            mtog1, mtog2, mtog3 = st.columns([1, 2, 1])
            with mtog2:
                if chat_mem_on:
                    st.markdown(
                        '<div class="mem-on-banner" style="text-align:center;margin:0 0 8px;">'
                        '🧠 Hindsight Memory ON — Agent recalls your full history</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="mem-off-banner" style="text-align:center;margin:0 0 8px;">'
                        '🚫 Memory OFF — Agent responds generically</div>',
                        unsafe_allow_html=True,
                    )
            btog1, btog2, btog3 = st.columns([2, 1, 2])
            with btog2:
                if st.button(
                    "Turn Memory OFF" if chat_mem_on else "Turn Memory ON",
                    use_container_width=True,
                    type="secondary" if chat_mem_on else "primary",
                    key="chat_mem_toggle",
                ):
                    st.session_state.memory_off_mode = chat_mem_on
                    st.rerun()

            # ── Two-panel chat window ─────────────────────────────────────
            msgs = st.session_state.chat_messages

            # Build HTML for left (customer) and right (agent) panels
            left_bubbles  = ""
            right_bubbles = ""
            for m in msgs:
                if m["role"] == "user":
                    left_bubbles += (
                        f'<div class="chat-row-c">'
                        f'<div class="chat-bubble-c">{m["text"]}</div>'
                        f'</div>'
                    )
                    right_bubbles += '<div style="padding:4px 0;min-height:20px;"></div>'
                else:
                    mem_log  = m.get("mem_log", {})
                    recalled = mem_log.get("recalled", [])
                    nbadge   = (
                        f'<span class="mem-bank-badge">🧠 {len(recalled)} memories</span>'
                        if recalled else
                        '<span class="mem-bank-badge" style="opacity:0.5;">no recall</span>'
                    )
                    right_bubbles += (
                        f'<div class="chat-row-a">'
                        f'<div>'
                        f'<div class="chat-bubble-a">{m["text"]}</div>'
                        f'<div style="text-align:right;margin-top:3px;">{nbadge}</div>'
                        f'</div></div>'
                    )
                    left_bubbles += '<div style="padding:4px 0;min-height:20px;"></div>'

            if not msgs:
                placeholder_left  = '<div style="color:#9ca3af;font-size:0.8rem;padding:20px 0;">Type your message below...</div>'
                placeholder_right = '<div style="color:#9ca3af;font-size:0.8rem;padding:20px 0;">AI response will appear here...</div>'
            else:
                placeholder_left = placeholder_right = ""

            st.markdown(
                f'<div class="chat-panel-wrap">'
                # LEFT — customer
                f'<div class="chat-panel-customer">'
                f'<div class="chat-panel-hdr chat-panel-hdr-c">📱 Customer</div>'
                f'<div class="chat-msgs" id="chat-left">{left_bubbles}{placeholder_left}</div>'
                f'</div>'
                # RIGHT — agent
                f'<div class="chat-panel-agent">'
                f'<div class="chat-panel-hdr chat-panel-hdr-a">🤖 NetRecall AI Agent</div>'
                f'<div class="chat-msgs" id="chat-right">{right_bubbles}{placeholder_right}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Input row ────────────────────────────────────────────────
            with st.form("chat_input_form", clear_on_submit=True):
                ci1, ci2, ci3 = st.columns([5, 1, 1])
                chat_text = ci1.text_input(
                    "Customer message",
                    placeholder="Type as the customer — e.g. 'My internet is down again'",
                    label_visibility="collapsed",
                )
                chat_submit = ci2.form_submit_button("Send →", type="primary",
                                                     use_container_width=True)
                chat_clear  = ci3.form_submit_button("Clear", use_container_width=True)

            if chat_clear:
                st.session_state.chat_messages = []
                st.rerun()

            if chat_submit and chat_text.strip():
                st.session_state.chat_messages.append(
                    {"role": "user", "text": chat_text.strip(), "mem_log": {}}
                )
                with st.spinner("Agent thinking…"):
                    try:
                        fs_chat    = re_eng.compute_frustration_score(chat_cust)
                        resp, mlog = chat_agent.handle_message(
                            customer=chat_cust,
                            message=chat_text.strip(),
                            memory_on=chat_mem_on,
                            frustration_score=fs_chat,
                        )
                        st.session_state.chat_messages.append(
                            {"role": "agent", "text": resp, "mem_log": mlog.to_dict()}
                        )
                    except Exception as _ce:
                        st.session_state.chat_messages.append(
                            {"role": "agent", "text": f"(Error: {_ce})", "mem_log": {}}
                        )
                st.rerun()

            # ── Quick prompts ────────────────────────────────────────────
            st.markdown(
                '<div style="font-size:0.72rem;color:#9ca3af;font-weight:700;'
                'text-transform:uppercase;letter-spacing:0.8px;margin:10px 0 6px;">'
                'Quick prompts</div>',
                unsafe_allow_html=True,
            )
            qp1, qp2, qp3, qp4 = st.columns(4)
            _quick_prompts = [
                (qp1, "qp_conn",   "🔴 No internet",       "My internet is completely down. All lights are red on my router."),
                (qp2, "qp_speed",  "🐢 Slow speeds",        "My internet speed is very slow, especially in the evenings."),
                (qp3, "qp_expiry", "📅 Plan renewal",        "My plan is about to expire. What are my renewal options?"),
                (qp4, "qp_repeat", "🔁 Same issue again",   "This same problem keeps happening every week! I am very frustrated."),
            ]
            for col, key, label, text in _quick_prompts:
                if col.button(label, use_container_width=True, key=key):
                    st.session_state.chat_messages.append(
                        {"role": "user", "text": text, "mem_log": {}}
                    )
                    with st.spinner("Agent thinking…"):
                        try:
                            fs_chat    = re_eng.compute_frustration_score(chat_cust)
                            resp2, ml2 = chat_agent.handle_message(
                                customer=chat_cust,
                                message=text,
                                memory_on=chat_mem_on,
                                frustration_score=fs_chat,
                            )
                            st.session_state.chat_messages.append(
                                {"role": "agent", "text": resp2, "mem_log": ml2.to_dict()}
                            )
                        except Exception as _qe:
                            st.session_state.chat_messages.append(
                                {"role": "agent", "text": f"(Error: {_qe})", "mem_log": {}}
                            )
                    st.rerun()

            # ── Hindsight memory evidence ─────────────────────────────────
            last_agent = next(
                (m for m in reversed(st.session_state.chat_messages) if m["role"] == "agent"),
                None,
            )
            if last_agent:
                recalled = last_agent.get("mem_log", {}).get("recalled", [])
                if recalled:
                    st.markdown("---")
                    st.markdown(
                        '<div style="font-size:0.72rem;font-weight:800;color:#111827;'
                        'text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">'
                        '🧠 Hindsight recalled for last response</div>',
                        unsafe_allow_html=True,
                    )
                    bank_labels = {
                        "netrecall-customers":   "👤 Customer Bank",
                        "netrecall-network":     "🌐 Network Bank",
                        "netrecall-resolutions": "✅ Resolution Bank",
                    }
                    r_cols = st.columns(min(len(recalled[:3]), 3))
                    for i, chunk in enumerate(recalled[:3]):
                        blabel  = bank_labels.get(chunk.get("source",""), chunk.get("source",""))
                        preview = (chunk.get("text") or "")[:180]
                        r_cols[i].markdown(
                            f'<div class="mem-chunk">'
                            f'<span class="mem-bank-badge">{blabel}</span>'
                            f'<div style="margin-top:5px;font-size:0.74rem;color:#374151;">'
                            f'{preview}{"…" if len(chunk.get("text",""))>180 else ""}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                    st.caption(
                        f"Agent queried {len(recalled)} memory chunk(s) across "
                        f"{len({c.get('source','') for c in recalled})} bank(s) "
                        "to personalise this response."
                    )
                elif chat_mem_on and last_agent.get("text"):
                    st.info("No matching memories yet — send more messages to build context.")


    # ═══════════════════════════════════════════════════════════════════════
    # CUSTOMERS TAB — full CRM with expandable customer DNA
    # ═══════════════════════════════════════════════════════════════════════
    with tab_customers:
        all_custs = db.get_all_customers()

        total   = len(all_custs)
        active  = sum(1 for c in all_custs if (c.get("plan_status") or "active") == "active")
        susp    = sum(1 for c in all_custs if (c.get("plan_status") or "") == "suspended")
        high_fs = sum(1 for c in all_custs if (c.get("frustration_score") or 0) >= 7)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Customers", total)
        m2.metric("Active Plans", active)
        m3.metric("Suspended", susp)
        m4.metric("High Risk", high_fs)

        st.markdown("---")

        fc1, fc2 = st.columns([4, 3])
        search_q  = fc1.text_input("🔍 Search name or phone", placeholder="Priya / +91…", key="cp_search")
        status_f  = fc2.selectbox("Filter", ["All", "active", "suspended", "expired"], key="cp_status")

        def _plan_days(c: dict) -> int:
            return _days_until_expiry(c.get("plan_expiry",""))

        filtered = all_custs
        if search_q.strip():
            q = search_q.strip().lower()
            filtered = [c for c in filtered if q in c.get("name","").lower() or q in (c.get("phone","") or "")]
        if status_f != "All":
            if status_f == "expired":
                filtered = [c for c in filtered if _plan_days(c) < 0]
            else:
                filtered = [c for c in filtered if (c.get("plan_status") or "active") == status_f]

        if not filtered:
            st.info("No customers match the filter.")
        else:
            st.caption(f"{len(filtered)} of {total} customers")
            for cust_row in filtered:
                cid_r   = cust_row["id"]
                cname   = cust_row.get("name","—")
                cphone  = cust_row.get("phone","—")
                carea   = cust_row.get("area","—")
                cplan   = cust_row.get("plan","—")
                cequip  = (cust_row.get("equipment","") or "—").split("(")[0].strip()
                cfs     = float(cust_row.get("frustration_score") or 1.0)
                ccalls  = int(cust_row.get("total_calls") or 0)
                clast   = (cust_row.get("last_call_at") or "Never")[:10]
                crate   = int(cust_row.get("monthly_rate") or 0)
                cstatus = cust_row.get("plan_status") or "active"
                cexpiry = cust_row.get("plan_expiry") or ""
                cdays   = _plan_days(cust_row)
                cemail  = cust_row.get("email","")
                caddr   = cust_row.get("address","")
                cacc    = cust_row.get("account_number","")
                ctix    = db.get_tickets_for_customer(cid_r)

                fs_col  = "#ef4444" if cfs >= 7 else "#f97316" if cfs >= 4 else "#16a34a"
                if cstatus == "suspended":
                    sbg, scol, slbl = "#fee2e2","#dc2626","SUSPENDED"
                elif cdays < 0:
                    sbg, scol, slbl = "#fff7ed","#ea580c",f"EXPIRED {abs(cdays)}d"
                elif cdays <= 7:
                    sbg, scol, slbl = "#fffbeb","#d97706",f"EXPIRING {cdays}d"
                else:
                    sbg, scol, slbl = "#dcfce7","#16a34a","ACTIVE"

                with st.expander(
                    f"{cname}  ·  {cplan}  ·  {carea}",
                    expanded=False,
                ):
                    # ── Header row ────────────────────────────────────────
                    hdr_c1, hdr_c2, hdr_c3 = st.columns([4, 2, 1])
                    hdr_c1.markdown(
                        f'<div class="cust-name">{cname}</div>'
                        f'<div class="cust-meta">{cphone} · {cemail}</div>'
                        f'<div class="cust-meta">{caddr}</div>',
                        unsafe_allow_html=True,
                    )
                    hdr_c2.markdown(
                        f'<span style="background:{sbg};color:{scol};padding:3px 10px;'
                        f'border-radius:6px;font-size:0.72rem;font-weight:700;">{slbl}</span>'
                        f'<div style="color:#6b7280;font-size:0.74rem;margin-top:6px;">'
                        f'Account: {cacc}</div>'
                        f'<div style="color:{fs_col};font-size:0.76rem;font-weight:700;margin-top:3px;">'
                        f'Frustration {cfs:.1f}/10</div>',
                        unsafe_allow_html=True,
                    )
                    if hdr_c3.button("📞 Call", key=f"cp_call_{cid_r}", use_container_width=True):
                        detector.record_ticket(cid_r, cname, carea, "simulated-from-portal")
                        st.session_state.ringing_id     = cid_r
                        st.session_state.call_state     = RINGING
                        st.session_state.incoming_phone = ""
                        st.rerun()

                    st.markdown("---")

                    # ── Detail columns ────────────────────────────────────
                    det_left, det_right = st.columns([1, 1], gap="medium")
                    with det_left:
                        st.markdown(
                            f'<div class="cust-card">'
                            f'<div style="font-size:0.7rem;font-weight:800;color:#111827;'
                            f'text-transform:uppercase;margin-bottom:8px;">📦 Plan Details</div>'
                            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;font-weight:700;text-transform:uppercase;">Plan</div>'
                            f'<div style="color:#111827;font-size:0.85rem;font-weight:600;">{cplan}</div></div>'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;font-weight:700;text-transform:uppercase;">Rate</div>'
                            f'<div style="color:#111827;font-size:0.85rem;font-weight:600;">{"₹"+str(crate)+"/mo" if crate else "—"}</div></div>'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;font-weight:700;text-transform:uppercase;">Expiry</div>'
                            f'<div style="color:#111827;font-size:0.85rem;font-weight:600;">{cexpiry or "—"}</div></div>'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;font-weight:700;text-transform:uppercase;">Area</div>'
                            f'<div style="color:#111827;font-size:0.85rem;font-weight:600;">{carea}</div></div>'
                            f'<div style="grid-column:span 2;">'
                            f'<div style="color:#94a3b8;font-size:0.65rem;font-weight:700;text-transform:uppercase;">Equipment</div>'
                            f'<div style="color:#111827;font-size:0.82rem;">{cequip}</div></div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                        # Call stats
                        st.markdown(
                            f'<div class="cust-card" style="margin-top:8px;">'
                            f'<div style="font-size:0.7rem;font-weight:800;color:#111827;'
                            f'text-transform:uppercase;margin-bottom:8px;">📊 Call Stats</div>'
                            f'<div style="display:flex;gap:20px;">'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;">Total Calls</div>'
                            f'<div style="color:#111827;font-size:1.2rem;font-weight:900;">{ccalls}</div></div>'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;">Last Call</div>'
                            f'<div style="color:#111827;font-size:0.85rem;font-weight:600;">{clast}</div></div>'
                            f'<div><div style="color:#94a3b8;font-size:0.65rem;">Tickets</div>'
                            f'<div style="color:#111827;font-size:1.2rem;font-weight:900;">{len(ctix)}</div></div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

                    with det_right:
                        st.markdown(
                            '<div style="font-size:0.7rem;font-weight:800;color:#111827;'
                            'text-transform:uppercase;margin-bottom:8px;">🎫 Ticket History</div>',
                            unsafe_allow_html=True,
                        )
                        if ctix:
                            for t in ctix[:8]:
                                t_status = t.get("status","")
                                t_col = "#16a34a" if t_status == "resolved" else "#d97706"
                                t_border = "#16a34a" if t_status == "resolved" else "#d97706"
                                st.markdown(
                                    f'<div class="cust-card" style="margin-bottom:6px;padding:10px 12px;border-left:3px solid {t_border};">'
                                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                    f'<span style="font-size:0.76rem;font-weight:700;color:#111827;">'
                                    f'{(t.get("issue_type") or "Issue")[:42]}</span>'
                                    f'<span style="font-size:0.65rem;font-weight:700;color:{t_col};">{t_status.upper()}</span>'
                                    f'</div>'
                                    f'<div style="font-size:0.72rem;color:#9ca3af;margin-top:3px;">'
                                    f'{(t.get("date_opened") or "")[:10]}'
                                    f'</div>'
                                    f'<div style="font-size:0.73rem;color:#6b7280;margin-top:4px;line-height:1.4;">'
                                    f'{(t.get("description") or "")[:120]}{"…" if len(t.get("description",""))>120 else ""}'
                                    f'</div>'
                                    + (
                                        f'<div style="font-size:0.7rem;color:#6b7280;margin-top:3px;">'
                                        f'✓ {(t.get("resolution") or "")[:100]}</div>'
                                        if t.get("resolution") else ""
                                    )
                                    + '</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown(
                                '<div style="color:#94a3b8;font-size:0.8rem;padding:12px 0;">'
                                'No tickets on record.</div>',
                                unsafe_allow_html=True,
                            )

                        # Hindsight memory peek
                        if hok and hcl:
                            if st.button(f"🧠 View Hindsight Memory", key=f"mem_peek_{cid_r}",
                                         use_container_width=True):
                                with st.spinner("Recalling from Hindsight…"):
                                    try:
                                        mr = hcl.recall(
                                            bank_id="netrecall-customers",
                                            query=f"History of {cname} ({cid_r})",
                                            tags=[f"customer:{cid_r}"],
                                            tags_match="any_strict",
                                            budget="mid",
                                            max_tokens=1200,
                                        )
                                        for chunk in mr.results[:4]:
                                            txt = (chunk.text or "")[:300]
                                            st.markdown(
                                                f'<div class="mem-chunk">'
                                                f'<span class="mem-bank-badge">👤 Customer Bank</span>'
                                                f'<div style="margin-top:6px;">{txt}…</div></div>',
                                                unsafe_allow_html=True,
                                            )
                                        if not mr.results:
                                            st.caption("No memory chunks found yet.")
                                    except Exception as _me:
                                        st.caption(f"Memory recall error: {_me}")

    with tab_dash:
        dash_module.render_dashboard(
            db=db,
            resolution_engine=re_eng,
            pattern_detector=detector,
            active_customers=set(),
            last_alerts=st.session_state.last_alert,
        )

