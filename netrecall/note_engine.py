"""
note_engine.py — Real-time AI note extraction from live call transcript.

Called every 3 transcript lines during an ACTIVE call.
Extracts structured facts the operator shouldn't have to write down manually:
  - Equipment mentioned
  - Symptoms described
  - What was already tried
  - How long the issue has been occurring
  - Key facts and urgency signals

Notes are ACCUMULATED across multiple extractions — new facts extend existing
lists, new strings only replace null values (never overwrite known facts).
"""

from __future__ import annotations
import json
import re
from typing import Optional


EMPTY_NOTES: dict = {
    "equipment_mentioned": None,
    "symptoms":            [],
    "what_was_tried":      [],
    "duration":            None,
    "key_facts":           [],
    "sentiment":           "neutral",
    "urgency_signals":     [],
    "issue_summary":       "",
}

EXTRACTION_TRIGGER_EVERY = 3   # extract after every N new transcript lines


def should_extract(transcript_length: int, last_extraction_at: int) -> bool:
    """Returns True when it's time to run note extraction again."""
    return (transcript_length - last_extraction_at) >= EXTRACTION_TRIGGER_EVERY


def extract_notes(
    transcript: list[dict],
    customer: dict,
    groq_client,
    window: int = 8,
) -> dict:
    """
    Extract structured notes from the most recent `window` transcript lines.

    Args:
        transcript:   list of {speaker, text, ts}
        customer:     customer dict with name, equipment, plan
        groq_client:  Groq client instance
        window:       how many recent lines to analyze

    Returns:
        dict matching EMPTY_NOTES structure (null for unknown fields)
    """
    if not transcript:
        return EMPTY_NOTES.copy()

    recent = transcript[-window:]
    transcript_text = "\n".join(
        f"{e['speaker'].upper()}: {e['text']}"
        for e in recent
        if e["speaker"] == "customer"   # only customer lines matter for notes
    )

    if not transcript_text.strip():
        return EMPTY_NOTES.copy()

    prompt = f"""You are extracting structured notes from a live ISP support call.
Only extract facts that are explicitly stated or strongly implied by the customer.
Do NOT hallucinate. Use null for any field not mentioned.

Customer: {customer.get('name', 'Unknown')}
Equipment on file: {customer.get('equipment', 'Unknown')}
Plan: {customer.get('plan', 'Unknown')}

Recent customer statements:
{transcript_text}

Return ONLY valid JSON (no explanation, no markdown):
{{
  "equipment_mentioned": "exact equipment the customer mentioned, or null",
  "symptoms": ["symptom 1", "symptom 2"],
  "what_was_tried": ["already tried action 1", "already tried action 2"],
  "duration": "how long the issue has been occurring, or null",
  "key_facts": ["important detail 1", "important detail 2"],
  "sentiment": "frustrated|neutral|angry|satisfied|confused",
  "urgency_signals": ["work from home", "exam tonight"],
  "issue_summary": "one sentence: what is this call about"
}}"""

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.1,
        )
        text = resp.choices[0].message.content
        return _parse_json(text)
    except Exception:
        return EMPTY_NOTES.copy()


def merge_notes(existing: dict, new: dict) -> dict:
    """
    Merge new extraction into existing notes.
    Lists are extended (deduplicated). Strings only replace null/empty values.
    Existing non-null values are never overwritten.
    """
    if not existing:
        existing = EMPTY_NOTES.copy()
    if not new:
        return existing

    merged = existing.copy()

    # String fields: only replace if currently null/empty
    for field in ("equipment_mentioned", "duration", "issue_summary"):
        if not merged.get(field) and new.get(field):
            merged[field] = new[field]

    # Sentiment: always take the more extreme reading (frustrated > neutral)
    _SEVERITY = {"angry": 4, "frustrated": 3, "confused": 2, "neutral": 1, "satisfied": 0}
    existing_s = merged.get("sentiment", "neutral")
    new_s      = new.get("sentiment", "neutral")
    merged["sentiment"] = (
        new_s if _SEVERITY.get(new_s, 0) > _SEVERITY.get(existing_s, 0) else existing_s
    )

    # List fields: extend + deduplicate (case-insensitive)
    for field in ("symptoms", "what_was_tried", "key_facts", "urgency_signals"):
        existing_items = [x.lower() for x in (merged.get(field) or [])]
        for item in (new.get(field) or []):
            if item and item.lower() not in existing_items:
                merged.setdefault(field, []).append(item)
                existing_items.append(item.lower())

    return merged


def notes_to_html(notes: dict) -> str:
    """
    Convert notes dict to styled HTML for the Live Intelligence panel.
    Returns empty string if notes are empty.
    """
    if not notes or not any([
        notes.get("equipment_mentioned"),
        notes.get("symptoms"),
        notes.get("what_was_tried"),
        notes.get("duration"),
        notes.get("key_facts"),
        notes.get("urgency_signals"),
        notes.get("issue_summary"),
    ]):
        return ""

    parts = []

    if notes.get("issue_summary"):
        parts.append(
            f'<div style="color:#e2e8f0;font-size:0.82rem;font-weight:600;'
            f'margin-bottom:8px;font-style:italic;">"{notes["issue_summary"]}"</div>'
        )

    def _row(label: str, value: str, color: str = "#94a3b8") -> str:
        return (
            f'<div style="display:flex;gap:6px;margin:3px 0;align-items:flex-start;">'
            f'<span style="color:#475569;font-size:0.68rem;font-weight:700;'
            f'text-transform:uppercase;min-width:80px;padding-top:1px;">{label}</span>'
            f'<span style="color:{color};font-size:0.78rem;">{value}</span>'
            f'</div>'
        )

    def _list_rows(label: str, items: list, color: str = "#94a3b8") -> str:
        if not items:
            return ""
        html = ""
        for i, item in enumerate(items[:4]):  # cap at 4 items
            prefix = label if i == 0 else ""
            html += _row(prefix, f"• {item}", color)
        return html

    if notes.get("equipment_mentioned"):
        parts.append(_row("Equipment", notes["equipment_mentioned"], "#38bdf8"))

    if notes.get("duration"):
        parts.append(_row("Duration", notes["duration"], "#fbbf24"))

    if notes.get("symptoms"):
        parts.append(_list_rows("Symptoms", notes["symptoms"], "#fca5a5"))

    if notes.get("what_was_tried"):
        parts.append(_list_rows("Tried", notes["what_was_tried"], "#86efac"))

    if notes.get("key_facts"):
        parts.append(_list_rows("Key Facts", notes["key_facts"], "#c4b5fd"))

    if notes.get("urgency_signals"):
        parts.append(
            f'<div style="background:#2d1a00;border:1px solid #f97316;border-radius:6px;'
            f'padding:5px 8px;margin-top:5px;">'
            + "".join(
                f'<div style="color:#fbbf24;font-size:0.75rem;">⚡ {u}</div>'
                for u in notes["urgency_signals"][:3]
            )
            + '</div>'
        )

    return "".join(parts)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    """Robustly extract the JSON object from LLM output."""
    for pattern in [r'\{[\s\S]*\}', r'\{[^{}]*\}']:
        m = re.search(pattern, text)
        if m:
            try:
                data = json.loads(m.group())
                # Validate expected keys exist
                result = EMPTY_NOTES.copy()
                result.update({k: v for k, v in data.items() if k in EMPTY_NOTES})
                return result
            except json.JSONDecodeError:
                pass
    try:
        data = json.loads(text.strip())
        result = EMPTY_NOTES.copy()
        result.update({k: v for k, v in data.items() if k in EMPTY_NOTES})
        return result
    except Exception:
        return EMPTY_NOTES.copy()
