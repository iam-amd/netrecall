"""
webhook_server.py — FastAPI server bridging Twilio → NetRecall SQLite → Streamlit.

Endpoints:
  POST /incoming           — Twilio fires this when a real incoming call arrives
  POST /demo-incoming      — Twilio fires this when an OUTBOUND demo call is answered
  POST /transcription      — Twilio fires this after each STT Gather result
  POST /call-status        — Twilio fires this on every call status change
  GET  /health             — Sanity check

Run alongside the Streamlit app:
  uvicorn webhook_server:app --host 0.0.0.0 --port 5050

Expose to Twilio (dev):
  ngrok http 5050
  → copy the https://xxx.ngrok.io URL into WEBHOOK_BASE_URL in .env
  → set Twilio number webhook to https://xxx.ngrok.io/incoming
  → set Twilio number status callback to https://xxx.ngrok.io/call-status
"""

from __future__ import annotations
import json
import logging
import os

from fastapi import FastAPI, Form, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv

from database import CustomerDB

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [webhook] %(levelname)s %(message)s",
)
logger = logging.getLogger("webhook_server")

# ── Shared DB — same file as Streamlit; WAL mode allows concurrent access ─────
_DB_PATH = os.path.join(os.path.dirname(__file__), "netrecall.db")
db = CustomerDB(_DB_PATH)

app = FastAPI(title="NetRecall Twilio Webhooks", version="1.0.0")

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
if not WEBHOOK_BASE_URL:
    logger.warning(
        "WEBHOOK_BASE_URL is not set. TwiML action URLs will be relative "
        "(e.g. action='/transcription'). Twilio requires ABSOLUTE URLs. "
        "Set WEBHOOK_BASE_URL to your ngrok https URL in .env before making real calls."
    )

# ── TwiML helpers ─────────────────────────────────────────────────────────────

_XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>'


def _twiml(body: str) -> Response:
    """Wrap TwiML body in <Response> and return with correct Content-Type."""
    return Response(
        content=f"{_XML_HEADER}\n<Response>\n{body}\n</Response>",
        media_type="application/xml",
    )


def _gather_block(
    action_url: str,
    say_text: str | None = None,
    speech_timeout: str = "auto",
    timeout: int = 15,
    language: str = "en-IN",
    base_url: str = "",
) -> str:
    """
    Build a <Gather input="speech"> TwiML block.

    speech_timeout="auto" lets Twilio detect natural end-of-speech
    rather than cutting off after a fixed number of seconds — better
    for ISP support customers reading error codes or descriptions.

    Falls through to <Redirect>/incoming</Redirect> if the caller is
    completely silent for `timeout` seconds.
    """
    redirect_base = base_url or WEBHOOK_BASE_URL
    inner = f"<Say language='{language}'>{say_text}</Say>" if say_text else ""
    return (
        f'<Gather input="speech" '
        f'action="{action_url}" '
        f'method="POST" '
        f'speechTimeout="{speech_timeout}" '
        f'timeout="{timeout}" '
        f'language="{language}">'
        f"{inner}"
        f"</Gather>"
        f'<Redirect method="POST">{redirect_base}/incoming</Redirect>'
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

def _base_url(request: Request) -> str:
    """Return the absolute base URL for TwiML action URLs.

    Priority:
    1. WEBHOOK_BASE_URL env var (set when using ngrok / production domain)
    2. Fall back to the incoming request's base URL (works for local dev / ngrok if env not set)
    """
    if WEBHOOK_BASE_URL:
        return WEBHOOK_BASE_URL
    # Build from request: scheme + host (strips trailing slash)
    return f"{request.url.scheme}://{request.url.netloc}"


@app.post("/incoming")
async def incoming_call(
    request:     Request,
    CallSid:     str = Form(...),
    From:        str = Form(...),
    To:          str = Form(""),
    CallStatus:  str = Form("ringing"),
) -> Response:
    """
    Twilio fires this the instant a call arrives.
    1. Register the call in incoming_calls (idempotent — handles Twilio retries).
    2. Write an initial 'ringing' signal so the Streamlit watcher can fire.
    3. Return TwiML: greet the caller, then start the Gather STT loop.
    """
    logger.info("Incoming call  CallSid=%s  From=%s  To=%s", CallSid, From, To)

    base = _base_url(request)

    db.register_incoming_call(call_sid=CallSid, from_phone=From, to_phone=To)
    db.write_call_signal(
        call_sid=CallSid,
        signal="ringing",
        payload={"from": From, "to": To},
    )

    body = _gather_block(
        action_url=f"{base}/transcription",
        say_text=(
            "Thank you for calling NetRecall support. "
            "Please hold for a moment while we connect you."
        ),
        speech_timeout="auto",
        timeout=20,
        base_url=base,
    )
    return _twiml(body)


@app.post("/demo-incoming")
async def demo_incoming(
    request:         Request,
    CallSid:         str = Form(...),
    From:            str = Form(""),
    To:              str = Form(""),
    CallStatus:      str = Form("ringing"),
    customer_phone:  str = Query(default=""),
) -> Response:
    """
    Twilio fires this when an OUTBOUND demo call is answered by the judge/customer.

    For outbound calls, `From` is the Twilio number and `To` is the judge's phone.
    We register the call using `customer_phone` (from query string) as from_phone
    so the Streamlit ringing-watcher can look up the customer by their own number.
    """
    effective_phone = customer_phone or To or From
    logger.info(
        "Demo-incoming  CallSid=%s  customer_phone=%s  From=%s  To=%s",
        CallSid, effective_phone, From, To,
    )

    base = _base_url(request)

    db.register_incoming_call(
        call_sid=CallSid,
        from_phone=effective_phone,
        to_phone=os.getenv("TWILIO_PHONE_NUMBER", ""),
    )
    db.write_call_signal(
        call_sid=CallSid,
        signal="ringing",
        payload={"from": effective_phone, "demo_call": True},
    )

    body = _gather_block(
        action_url=f"{base}/transcription",
        say_text=(
            "Thank you for calling NetRecall support. "
            "Please hold for a moment while we connect you."
        ),
        speech_timeout="auto",
        timeout=20,
        base_url=base,
    )
    return _twiml(body)


@app.post("/transcription")
async def transcription(
    request:      Request,
    CallSid:      str   = Form(...),
    SpeechResult: str   = Form(""),
    Confidence:   float = Form(0.0),
    CallStatus:   str   = Form("in-progress"),
) -> Response:
    """
    Twilio fires this after every Gather STT result — including empty results
    (caller was silent / speechTimeout fired with no speech).

    1. Save non-empty text to live_transcripts.
    2. Return a new <Gather> to keep the listen loop going.
    """
    text = (SpeechResult or "").strip()
    logger.info(
        "Transcription  CallSid=%s  Confidence=%.2f  Text=%r",
        CallSid, Confidence, text[:80] if text else "",
    )

    if text:
        db.add_live_transcript(
            call_sid=CallSid,
            text=text,
            confidence=float(Confidence),
            speaker="customer",
        )
        db.write_call_signal(
            call_sid=CallSid,
            signal="in-progress",
            payload={"speech_received": True, "confidence": round(float(Confidence), 2)},
        )

    # Continue the loop — no <Say> so it silently keeps listening
    base = _base_url(request)
    body = _gather_block(
        action_url=f"{base}/transcription",
        say_text=None,
        speech_timeout="auto",
        timeout=30,
        base_url=base,
    )
    return _twiml(body)


@app.post("/call-status")
async def call_status(
    CallSid:    str = Form(...),
    CallStatus: str = Form(""),
    From:       str = Form(""),
    To:         str = Form(""),
) -> PlainTextResponse:
    """
    Twilio fires this on every status change for the call.
    The critical events are 'completed', 'failed', 'busy', 'no-answer'.

    MUST return 200 OK even on errors — Twilio retries non-200 responses,
    which would produce duplicate signal rows.
    """
    logger.info("Call status  CallSid=%s  Status=%s", CallSid, CallStatus)

    terminal = {"completed", "failed", "busy", "no-answer", "canceled"}

    twilio_own_number = os.getenv("TWILIO_PHONE_NUMBER", "")

    try:
        db.write_call_signal(
            call_sid=CallSid,
            signal=CallStatus,
            payload={"from": From, "to": To},
        )

        # Fallback registration for outbound demo calls: if the TwiML URL
        # (/demo-incoming) fired late or was missed (e.g. Twilio trial account
        # screening), register the call here when it becomes in-progress so the
        # Streamlit ringing-watcher can still detect it.
        if CallStatus == "in-progress" and From == twilio_own_number and To:
            existing = db._conn.execute(
                "SELECT 1 FROM incoming_calls WHERE call_sid = ?", (CallSid,)
            ).fetchone()
            if not existing:
                logger.info(
                    "call_status: registering outbound call %s via fallback (To=%s)",
                    CallSid, To,
                )
                db.register_incoming_call(
                    call_sid=CallSid,
                    from_phone=To,   # the judge's phone becomes "from" in our model
                    to_phone=twilio_own_number,
                )
                db.write_call_signal(
                    call_sid=CallSid,
                    signal="ringing",
                    payload={"from": To, "demo_call": True, "fallback": True},
                )

        if CallStatus in terminal:
            db._conn.execute(
                "UPDATE incoming_calls SET status = ? WHERE call_sid = ?",
                (CallStatus, CallSid),
            )
            db._conn.commit()
    except Exception as exc:
        logger.error("call_status DB error: %s", exc)
        # Swallow — still return 200 to stop Twilio retrying

    return PlainTextResponse("OK", status_code=200)


@app.get("/health")
async def health() -> dict:
    """Health check — confirms DB is reachable."""
    try:
        return {"status": "ok", "customers": db.get_customer_count()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "webhook_server:app",
        host="0.0.0.0",
        port=5050,
        reload=False,
        log_level="info",
    )
