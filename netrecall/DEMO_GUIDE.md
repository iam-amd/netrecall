# NetRecall — Live Demo Guide
## Real Phone Call Setup for Judges

---

## Prerequisites (one-time, do before the event)

| What | Where to get |
|---|---|
| Twilio account | twilio.com — free trial has $15 credit (~200 calls) |
| Twilio phone number | Twilio Console → Phone Numbers → Buy a number |
| ngrok | ngrok.com → free account → `ngrok.exe` on your PATH |
| Groq API key | console.groq.com → API Keys |
| Hindsight API key | vectorize.io → Settings → API Keys |

---

## One-Time Twilio Configuration

After you run ngrok (Step 3 below), you need to point your Twilio number at your local server.

1. Go to **Twilio Console** → **Phone Numbers** → click your number
2. Under **"A Call Comes In"** → set to **Webhook** → paste:
   ```
   https://YOUR-NGROK-URL.ngrok-free.app/incoming
   ```
   Method: **HTTP POST**
3. Under **"Call Status Changes"** → paste:
   ```
   https://YOUR-NGROK-URL.ngrok-free.app/call-status
   ```
   Method: **HTTP POST**
4. Click **Save**

> **Note:** Free ngrok URLs change every restart. If you restart ngrok, update both Twilio webhook URLs and `.env` again.

---

## Before the Demo — Start Everything

### Step 1 · Fill in your .env

Copy `.env.example` → `.env` and fill in:
```
GROQ_API_KEY=gsk_xxxx
HINDSIGHT_API_KEY=hsk_xxxx
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=xxxx
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
WEBHOOK_BASE_URL=https://xxxx.ngrok-free.app   ← fill after Step 3
```

### Step 2 · Launch both servers (double-click)
```
start_demo.bat
```
Or manually in two terminals:
```bash
# Terminal 1 — Webhook server
python -m uvicorn webhook_server:app --host 0.0.0.0 --port 5050

# Terminal 2 — Streamlit UI
python -m streamlit run app.py --server.port 8504
```

Verify both are up:
- UI: `http://localhost:8504` — should show Command Center
- Webhook: `http://localhost:5050/health` — should return `{"status":"ok","customers":15}`

### Step 3 · Start ngrok (separate terminal)
```bash
ngrok http 5050
```
You'll see output like:
```
Forwarding  https://a1b2c3d4.ngrok-free.app -> http://localhost:5050
```
Copy the `https://xxxx.ngrok-free.app` URL (no trailing slash).

### Step 4 · Update .env and Twilio

1. Paste the ngrok URL into `.env` as `WEBHOOK_BASE_URL`
2. Update the two Twilio webhook URLs (see One-Time Configuration above)
3. Restart the webhook server so it picks up the new URL:
   ```bash
   Ctrl+C  →  python -m uvicorn webhook_server:app --host 0.0.0.0 --port 5050
   ```

### Step 5 · Seed demo data

In the Streamlit UI:
1. Open the **sidebar** (expand ← on the left)
2. Click **"🌱 Seed Customer Database"**
3. Wait for green confirmation — 15 customers loaded

---

## Live Demo Script (for judges)

### What the judge sees before calling

Show the **Command Center (IDLE state)** — 15 customers in the queue, network dashboard.

Point out the demo customers:
- **Priya Sharma** — 100Mbps plan, expires in 8 days, recurring ONT red LOS ×3
- **Deepika Rao** — 50Mbps plan, **SUSPENDED** (expired 28 days ago)
- **Vikram Singh** — 100Mbps plan, **expires in 2 days** — urgent
- **Amit Kumar** — 50Mbps plan, **SUSPENDED** account

---

### The Demo Call Flow

**Judge dials the Twilio number from their phone.**

Twilio phone number: write it on the whiteboard beforehand.

```
+1 (XXX) XXX-XXXX   ← your Twilio number
```

#### What happens (real-time, ~2 seconds per step):

| Seconds | What the judge hears | What the UI shows |
|---------|---------------------|-------------------|
| 0s | Call connects, hear: *"Thank you for calling NetRecall support. Please hold..."* | RINGING banner appears with caller ID |
| 1-2s | Holding | **Pre-Call Intelligence panel** shows: plan status, frustration score, recurring issues |
| — | Agent clicks **Answer** | ACTIVE call state loads with DNA panel + emotion face |
| Judge speaks | Natural speech | Transcript appears in real-time; emotion face animates |
| After ~3 lines | — | Co-pilot generates "Say This Now" suggestion, diagnosis, Do/Don't |
| More speech | Customer says "my internet keeps disconnecting" | Emotion face shifts to 😤 Frustrated; co-pilot updates |
| Agent clicks **End Call** | Call disconnects | POST-CALL summary screen |
| Agent clicks **Generate Summary** | — | AI summary + memory saved to Hindsight |

---

### Talking Points During the Demo

**On RINGING screen:**
> "Before I even pick up, the system already knows: this customer's plan expires in 8 days, they've had the same ONT issue 3 times, and their frustration score is 6.4 out of 10. I didn't look up anything — it's all pre-computed."

**On ACTIVE call / DNA panel:**
> "Left column is the full customer DNA — name, address, plan, expiry, account status. Everything visible in one panel. No switching screens, no asking 'can I get your account number'."

**On emotion face:**
> "This face updates live as the customer speaks. When they say 'this is the third time I'm calling', you'll see it shift to frustrated. The agent knows to slow down and empathize before jumping to diagnosis."

**On Co-pilot:**
> "The AI is listening and saying 'Say This Now' — not after the call, not in training — live, as the customer speaks. It knows from Hindsight memory that this exact issue was fixed before with an OLT port reboot."

**On Post-Call:**
> "End the call, click Generate Summary — every detail is auto-written, saved to Hindsight memory, and becomes part of this customer's permanent DNA for the next agent who picks up."

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Phone rings but UI doesn't react | Check ngrok is running; check `.env WEBHOOK_BASE_URL` is the current ngrok URL; restart webhook server |
| "Speech not transcribed" | Twilio trial accounts may need phone number verification. Verify your number at twilio.com/console/verified-caller-ids |
| Twilio says "Application Error" | Webhook server is not running or ngrok is down. Check `http://localhost:5050/health` |
| Customer number not found | Their phone number format differs. The ringing watcher tries E.164 and hyphenated formats. For demo, use "Simulate Incoming" with a seeded number instead |
| Co-pilot doesn't update | GROQ_API_KEY not set or invalid. Check sidebar shows "🟢 Groq Connected" |

---

## Quick Demo Alternative (no phone needed)

If Twilio/ngrok has issues during the live demo, use the **built-in simulator**:

1. In the top-right of the UI, type a customer phone number:
   ```
   +91-9876501001    ← Priya Sharma (recurring ONT issue, expiry in 8 days)
   +91-9876501002    ← Deepika Rao (SUSPENDED account)
   +91-9876501004    ← Vikram Singh (expires in 2 days)
   ```
2. Click **"📞 Simulate Incoming"**
3. The full RINGING → ACTIVE → POSTCALL flow works exactly the same
4. In the transcript box, type what the "customer" is saying to drive the co-pilot

This is 100% functional — Hindsight memory, co-pilot, emotion face, DNA panel all work.

---

---

## Judge as Customer — Full Mobile Call Flow

> **For judges who want to experience the system as a real customer.**
> This is the most impressive demo path: enter your own data, call from your mobile, and watch the system recognise you automatically.

### Prerequisites
- Twilio is configured and ngrok is running (see setup above)
- Both servers are running (`webhook_server.py` + `app.py`)
- Your **real mobile number** — the one you will call FROM

---

### Step 1 — Enter Your Profile (Judges Portal)

1. In the Streamlit UI, click the **"🧑‍⚖️ Judges Portal"** tab
2. In **Step 1 — Generate Profile**:
   - Enter your **Full Name** (e.g. "Rajesh Kumar")
   - Enter your **Mobile Number in E.164 format**: `+91XXXXXXXXXX`
     - Indian number: `+91` + 10 digits (e.g. `+919876543210`)
     - UK number: `+44` + 10 digits (e.g. `+447911123456`)
     - US number: `+1` + 10 digits (e.g. `+12025551234`)
   - Click **"Generate My Customer Profile"**

   > The AI (Groq) will create a realistic ISP customer profile for you — with a plan, equipment, address, and 2–3 plausible ticket history entries. It takes ~5 seconds.

### Step 2 — Review and Edit Your Profile

The generated profile appears in **Step 2 — Edit Profile**.

Things to check / optionally edit:
- **Phone number** — must match EXACTLY what your mobile will show as caller ID when you call
  - If Twilio shows your number without country code, add `+91` prefix
  - If you're using a SIM that shows `+44...` format, ensure that's what's stored
- **Plan Expiry** — set to a date 2–5 days in future for the most dramatic pre-call alert
- **Plan Status** — leave as "active" unless you want to demo the SUSPENDED scenario
- **Frustration Score** — slide to 7+ if you want the high-frustration demo experience

### Step 3 — Seed to Database and Hindsight Memory

1. Click **"💾 Seed to DB + Memory"**
2. Wait for the green confirmation: `✅ Profile seeded to SQLite and Hindsight`
3. Click **"🔍 Verify Hindsight Memory Recall"**

   > This fires a real `hindsight.recall()` call and shows you the memory chunks that were just stored. You should see your name, plan details, and ticket summaries returned as semantic search results. **This is the memory pipeline proving it works.**

### Step 4 — Call from Your Mobile

Pick up your phone and dial the Twilio number:

```
Your Twilio number: ________________________________
                   (write it here before the demo)
```

**What happens in the next 10 seconds:**

| Your phone | The screen |
|---|---|
| Rings → connects | Nothing yet |
| You hear: *"Thank you for calling NetRecall support. Please hold..."* | 📳 RINGING banner appears with YOUR phone number |
| — | **Pre-Call Intelligence** loads: YOUR plan status, YOUR frustration score, YOUR ticket history |
| Presenter clicks **📞 Answer** | ACTIVE call state — YOUR Customer DNA panel on the left |
| You speak: *"Hi, my internet is dropping every evening"* | Transcript appears live; emotion face animates |
| You say: *"This has happened three times already"* | Co-pilot updates: cites YOUR ticket history; emotion shifts to 😤 Frustrated |
| Presenter clicks **📵 End Call** | Post-call summary screen |
| Presenter clicks **Generate Summary & Save** | YOUR call is retained to Hindsight — forever |

### Step 5 — See Your Call History

After the call ends and summary is saved:

1. Switch back to **Judges Portal** tab (it auto-reloads)
2. Scroll to **Step 4 — Your Call History**
3. You'll see YOUR call logged: timestamp, duration, AI summary
4. Also visible in **👥 Customers** tab — search your name or phone number

---

### Exact Phone Number Format Guide

Twilio passes the caller's number in E.164 format. The stored number must match exactly.

| Your SIM / Country | Format to enter in Step 1 |
|---|---|
| India (+91) | `+91XXXXXXXXXX` — 13 chars total |
| UK (+44) | `+44XXXXXXXXXX` — 13 chars total |
| US/Canada (+1) | `+1XXXXXXXXXX` — 12 chars total |
| Australia (+61) | `+61XXXXXXXXX` — 12 chars total |

**If the RINGING screen shows "Unknown Caller" instead of your name:**  
→ The phone number format didn't match. Go back to Judges Portal → Step 2 → edit the phone field to match exactly what appeared in the RINGING banner → Re-seed → Call again.

---

### What to Say When Calling (for best demo effect)

The Twilio STT works best with clear, natural speech. Suggested script:

1. **First sentence:** *"Hi, my internet connection keeps dropping every evening."*
   - This will trigger the co-pilot to recall your ticket history
   
2. **Second sentence:** *"This has happened at least three times in the past month."*
   - If you have 3+ tickets seeded, the co-pilot will flag it as a recurring issue

3. **Third sentence:** *"I have the TP-Link ONT router and I'm on the 100Mbps plan."*
   - The co-pilot will confirm it matches your seeded equipment (from memory)

4. **Wait 5–10 seconds** between sentences — Twilio STT needs a brief pause to commit each phrase.

---

## Architecture for the 30-second pitch

```
Judge's phone
     │
     ▼
Twilio  ──────────────────────────────────────
(STT, call routing)        │
                           ▼
                    ngrok tunnel
                           │
                           ▼
              webhook_server.py  (FastAPI :5050)
              ┌────────────────────────────┐
              │  POST /incoming            │
              │  POST /transcription       │  writes to
              │  POST /call-status         │──────────────►  netrecall.db
              └────────────────────────────┘                 (SQLite WAL)
                                                                   │
                                                             polls every 2s
                                                                   │
                                                                   ▼
                                                          app.py  (Streamlit :8504)
                                                          ┌───────────────────────┐
                                                          │  IDLE → RINGING       │
                                                          │  Pre-call insights    │
                                                          │  ACTIVE call          │
                                                          │  ├─ DNA panel         │──► Hindsight
                                                          │  ├─ Emotion face      │    Memory
                                                          │  └─ AI Co-pilot       │    Banks
                                                          │  POST-CALL summary    │
                                                          └───────────────────────┘
```
