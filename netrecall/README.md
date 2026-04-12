# NetRecall — ISP Support AI That Remembers Everything

> An AI co-pilot for ISP support agents that knows every customer's full history before they even pick up the phone. Powered by [Hindsight](https://hindsight.vectorize.io/) persistent agent memory and [Groq](https://console.groq.com/) LLM. Integrates with real phone calls via Twilio.

---

## The Problem

Every support call at a small ISP starts the same way:

1. "Can I get your account number?" — 90 seconds wasted
2. "Have you tried restarting the router?" — customer sighs
3. "Has this happened before?" — agent flips through disconnected notes
4. "Let me check for outages in your area..." — hold music plays

NetRecall eliminates all of this. The moment a customer calls, the agent already knows who they are, what their issue history is, how frustrated they've been, and what fixes have worked before. The agent **remembers**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Real Phone Call                      │
│            Customer → Twilio → FastAPI Webhook           │
│                     (port 5050)                          │
└──────────────────┬───────────────────────────────────────┘
                   │ Speech-to-text + call events
                   ▼
┌──────────────────────────────────────────────────────────┐
│              SQLite WAL (Shared State Bus)                │
│  customers · tickets · calls · live_transcripts          │
└──────────────────┬───────────────────────────────────────┘
                   │ Polls every 2s via st.fragment
                   ▼
┌──────────────────────────────────────────────────────────┐
│             Streamlit UI (port 8504)                     │
│   IDLE → RINGING → ACTIVE CALL → POSTCALL               │
│                                                          │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────┐  │
│  │ Customer    │  │  AI Co-Pilot     │  │ Live       │  │
│  │ DNA Panel   │  │  + Emotion Face  │  │ Transcript │  │
│  │ (from HS)   │  │  + Auto-Notes    │  │ (Twilio)   │  │
│  └─────────────┘  └──────────────────┘  └────────────┘  │
└──────────────────┬───────────────────────────────────────┘
                   │ recall() / retain()
                   ▼
┌──────────────────────────────────────────────────────────┐
│            Hindsight Memory (3 Banks)                    │
│  netrecall-customers  ← full history per customer        │
│  netrecall-network    ← area-wide incident patterns      │
│  netrecall-resolutions← what fixed which issue           │
└──────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **Customer DNA Panel** | Plan status, expiry badge, equipment, ticket history — recalled from Hindsight before call answers |
| **Pre-Call Intelligence** | Plan expiry alerts, frustration score, recurring issue patterns — visible the instant the phone rings |
| **Animated Emotion Face** | Live sentiment tracking (neutral/frustrated/angry/satisfied) with CSS animations |
| **AI Co-Pilot** | Real-time guidance: what to say, what NOT to say, likely issue, escalation recommendation |
| **Auto Note Extraction** | Extracts equipment, area, issue summary, and action items from live transcript |
| **Pattern Detection** | 2+ tickets from the same area in 60 min → automatic area-wide outage alert |
| **Resolution Memory** | What fixed a given issue before is recalled across all customers |
| **Post-Call Retain** | Full call summary + resolution + frustration delta → stored in Hindsight for next agent |
| **Real Phone Calls** | Twilio integration: actual mobile calls with live STT transcript |
| **Memory ON/OFF Toggle** | Side-by-side contrast: generic chatbot vs memory-aware agent |
| **Judges Portal** | Self-service demo: generates a realistic customer profile, seeds it, lets judges call and verify their own memory recall |

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit ≥1.38.0 |
| LLM | Groq `llama-3.3-70b-versatile` |
| Persistent Memory | Hindsight Cloud (Vectorize) — 3 semantic banks |
| Real-time State | SQLite WAL mode (FastAPI → Streamlit shared bus) |
| Phone | Twilio Voice + `<Gather input="speech">` for STT |
| Backend | FastAPI + uvicorn (Twilio webhook receiver) |
| Language | Python 3.11+ |

---

## Project Structure

```
netrecall/
├── app.py                  # Streamlit UI — state machine IDLE/RINGING/ACTIVE/POSTCALL
├── agent.py                # NetRecallAgent — Groq + Hindsight recall/retain
├── copilot.py              # AI Co-Pilot — live operator guidance
├── database.py             # SQLite WAL CustomerDB + call logging
├── webhook_server.py       # FastAPI — Twilio webhook receiver (port 5050)
├── network_patterns.py     # PatternDetector — area-wide outage detection
├── resolution_engine.py    # ResolutionEngine — frustration scoring
├── note_engine.py          # Auto-extracts notes from live transcript
├── voice_component.py      # Browser SpeechRecognition bridge
├── dashboard.py            # Network health dashboard
├── demo_seeder.py          # Quick 2-customer seed for demos
├── seed_data.py            # Full 15-customer dataset with tickets
├── start_demo.bat          # One-click Windows launcher
├── DEMO_GUIDE.md           # Live demo script for judges
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Clone and install

```bash
pip install -r requirements.txt
```

### 2. Get API credentials

**Groq:** https://console.groq.com → API Keys

**Hindsight Cloud:** https://ui.hindsight.vectorize.io → Connect to Hindsight
- Copy your **API Key** and **API Endpoint**
- Use promo code `MEMHACK409` for $50 free credits

### 3. Configure environment

```bash
cp .env.example .env
# Fill in GROQ_API_KEY, HINDSIGHT_API_KEY, HINDSIGHT_BASE_URL
```

### 4. Run (browser demo — no phone needed)

```bash
streamlit run app.py
```

Open sidebar → click **"🌱 Seed Customer Database"** to populate 15 customers with full ticket history into SQLite + Hindsight.

Use the **Judges Portal** tab → enter any name and phone → click Generate → Seed → Simulate Call.

### 5. Run with real phone calls (optional)

```bash
# Terminal 1: Twilio webhook
python webhook_server.py

# Terminal 2: App
streamlit run app.py

# Terminal 3: Public tunnel
ngrok http 5050
```

Set your Twilio phone number's Voice webhook URL to:
```
https://<your-ngrok-id>.ngrok.io/voice
```

Then add Twilio credentials to `.env`:
```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
WEBHOOK_BASE_URL=https://<your-ngrok-id>.ngrok.io
```

---

## How Hindsight Memory Works

### Memory Banks

| Bank ID | What's Stored | Tags Used |
|---|---|---|
| `netrecall-customers` | Customer profile, all ticket history, live call interactions | `customer:CUST001`, `sector:sector-4` |
| `netrecall-network` | Area-wide outage incidents, pattern history | `sector:sector-4`, `historical-incident` |
| `netrecall-resolutions` | Cross-customer fix patterns: what resolved which issue type | `issue:ont-red-light` |

### On each incoming call (RINGING state)

```python
# Pre-call recall — fires before agent picks up
r1 = hindsight.recall(bank_id="netrecall-customers",
                      query=f"Full history of {customer['name']}",
                      tags=[f"customer:{customer['id']}"],
                      budget="mid")

r2 = hindsight.recall(bank_id="netrecall-network",
                      query=f"Area incidents in {customer['area']}",
                      tags=[f"sector:{area}"],
                      budget="low")
```

### On each transcript turn (ACTIVE call)

```python
# Resolution recall
r3 = hindsight.recall(bank_id="netrecall-resolutions",
                      query=f"Proven fix for: {customer_message}",
                      budget="low")

# Co-pilot generates guidance from all 3 recall results
guidance = copilot.generate_live_update(customer, transcript, r1, r2, fs, alert)

# Retain the interaction
hindsight.retain(bank_id="netrecall-customers",
                 content=f"{customer['name']}: {message}\nAgent: {response}",
                 tags=[f"customer:{customer['id']}", f"sector:{area}"],
                 document_id=f"{customer_id}-{timestamp}")
```

### Post-call retain

After the call ends, the full transcript + AI summary + resolution + frustration delta are retained to `netrecall-customers`. The next agent who handles this customer will instantly know what happened.

---

## Memory OFF / ON Demo

Open the **sidebar** → toggle **"Disable Hindsight Memory"** to see the difference:

| Mode | Pre-Call | Co-Pilot | Post-Call |
|---|---|---|---|
| **Memory ON** | Full history, plan expiry, frustration score, recurring patterns | Personalised guidance citing specific past tickets, equipment, area incidents | Retained to Hindsight — next agent knows everything |
| **Memory OFF** | "Agent is blind" — no history | Generic "restart your router" advice | Not retained — history is lost |

---

## Before / After Memory Contrast

**Without memory (Memory OFF):**
```
Customer: My internet keeps dropping every evening.
Agent:    Please try restarting your router and modem. 
          Wait 2 minutes and reconnect. If the issue persists, 
          check your cables and contact us again.
```

**With memory (Memory ON) — same customer, same issue:**
```
Customer: My internet keeps dropping every evening.
Agent:    Priya, I can see this is the third time in the last 
          six weeks — ONT red light and evening drops. The last 
          two restarts only held for a few days. This time I'm 
          escalating directly to a field visit to check OLT port J2. 
          I'm also seeing two other customers in Sector 4 with the 
          same issue this week — this looks area-wide.
```

---

## Demo Script

See [DEMO_GUIDE.md](DEMO_GUIDE.md) for the full live demo walkthrough.

Quick path:
1. Open app → seed database
2. Sidebar → toggle Memory OFF → simulate call from Priya Sharma → answer → type "internet is down again"
3. Observe generic response
4. Toggle Memory ON → repeat
5. Observe: name, equipment, history, recurring pattern all cited
6. End call → see "✅ Retained to Hindsight" confirmation

---

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (`gsk_...`) |
| `HINDSIGHT_BASE_URL` | Hindsight Cloud endpoint |
| `HINDSIGHT_API_KEY` | Hindsight API key (`hsk_...`) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID (optional — for real calls) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (optional) |
| `TWILIO_PHONE_NUMBER` | Your Twilio number in E.164 format (optional) |
| `WEBHOOK_BASE_URL` | Public ngrok URL for Twilio callback (optional) |

---

## Hackathon

Built for the **Hindsight AI Agents Hackathon** by [Vectorize](https://vectorize.io/).
Memory bank: Hindsight Cloud · Promo code: `MEMHACK409`
