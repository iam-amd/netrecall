"""
copilot.py — Real-time AI Co-Pilot for ISP support operators.

The co-pilot runs silently alongside the operator during every call.
It reads the customer's full DNA from memory and the live conversation,
then tells the operator:

  • Exactly what to say right now  (large, readable script)
  • What to DO in this call        (green talking points)
  • What NOT to do / say           (red warnings)
  • What the issue likely is       (diagnosis + confidence)
  • Whether to escalate            (and why)
  • How the customer is feeling    (sentiment)
  • Any area-wide context          (network alert)

All output is structured so the UI can render each section clearly.
The operator reads it while talking — they never have to think from scratch.
"""

from __future__ import annotations
import json
import re
from typing import Optional


FALLBACK_BRIEFING = {
    "opening_line":        "Thank you for calling. I can see your account and history right here.",
    "what_to_say_now":     "Let me pull up your account. I can see your service history — no need to repeat anything you've told us before.",
    "do_say":              ["Acknowledge their history", "Be specific about their equipment", "Give a clear next step"],
    "dont_say":            ["Don't ask them to repeat account details", "Don't suggest generic reboot without context"],
    "likely_issue":        "Checking history...",
    "confidence":          0,
    "suggested_resolution":"Reviewing historical resolutions...",
    "escalate":            False,
    "escalation_reason":   "",
    "sentiment":           "neutral",
    "area_alert":          "",
    "talking_points":      ["Customer history loaded", "Equipment details available", "Area status checked"],
}


class CoPilot:
    """Generates live operator guidance during a support call."""

    MODEL = "llama-3.3-70b-versatile"

    def __init__(self, groq_client, hindsight_client=None):
        self.groq      = groq_client
        self.hindsight = hindsight_client

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_initial_briefing(
        self,
        customer:        dict,
        customer_mems:   list,
        network_mems:    list,
        frustration_score: dict,
        pattern_alert:   Optional[dict],
    ) -> dict:
        """
        Called the moment the operator answers the call.
        Returns full structured briefing in ~2 seconds.
        """
        mem_ctx = "\n".join(f"- {m.text}" for m in customer_mems[:8]) or "No prior history found."
        net_ctx = "\n".join(f"- {m.text}" for m in network_mems[:4]) or "No area incidents found."
        fs      = frustration_score
        alert_ctx = (
            f"AREA ALERT: {pattern_alert['ticket_count']} customers from "
            f"{pattern_alert['sector']} called in the last {pattern_alert['window_minutes']} min. "
            f"Issues: {'; '.join(set(pattern_alert['issues']))}."
            if pattern_alert else "No area-wide alerts."
        )

        system = f"""You are NetRecall Co-Pilot — an AI that briefs ISP support operators the moment they answer a call.

CUSTOMER CALLING:
Name:      {customer['name']}
Area:      {customer['area']}
Plan:      {customer['plan']}
Equipment: {customer['equipment']}
Risk Score:{fs['score']}/10 ({fs['risk']} — {'; '.join(fs['drivers'][:2])})

RECALLED CUSTOMER HISTORY:
{mem_ctx}

AREA NETWORK CONTEXT:
{net_ctx}

AREA ALERT:
{alert_ctx}

Generate a JSON briefing for the operator. They are currently on the phone and need to read this while talking.
Make "what_to_say_now" a natural, human-sounding sentence the operator can actually say out loud.
Be specific: reference the customer's actual equipment, actual ticket history, actual area.
If risk is high or critical, recommend escalation.

Return ONLY valid JSON in this exact structure:
{{
  "opening_line": "The first thing to say when the customer starts talking",
  "what_to_say_now": "The full sentence the operator should say right now — specific, human, informed",
  "do_say": ["Point 1", "Point 2", "Point 3"],
  "dont_say": ["Warning 1", "Warning 2"],
  "likely_issue": "One-line diagnosis based on history",
  "confidence": 85,
  "suggested_resolution": "Specific fix to apply (not generic)",
  "escalate": false,
  "escalation_reason": "Why to escalate (empty string if not escalating)",
  "sentiment": "frustrated|neutral|angry|confused|satisfied",
  "area_alert": "One-line area alert if applicable, else empty string",
  "talking_points": ["Specific point 1", "Specific point 2", "Specific point 3"]
}}"""

        return self._call_groq(system, f"Generate briefing for call from {customer['name']}.")

    def generate_live_update(
        self,
        customer:      dict,
        transcript:    list[dict],
        customer_mems: list,
        network_mems:  list,
        frustration_score: dict,
        pattern_alert: Optional[dict],
    ) -> dict:
        """
        Called after each new line in the conversation transcript.
        Updates the co-pilot suggestions based on what the customer just said.
        """
        if not transcript:
            return FALLBACK_BRIEFING.copy()

        transcript_text = "\n".join(
            f"{e['speaker'].upper()}: {e['text']}"
            for e in transcript[-6:]   # last 6 turns
        )
        mem_ctx = "\n".join(f"- {m.text}" for m in customer_mems[:6]) or "No prior history."
        net_ctx = "\n".join(f"- {m.text}" for m in network_mems[:3]) or "No area incidents."
        alert_ctx = (
            f"AREA ALERT: {pattern_alert['ticket_count']} customers from "
            f"{pattern_alert['sector']} in last {pattern_alert['window_minutes']} min."
            if pattern_alert else ""
        )
        fs = frustration_score

        system = f"""You are NetRecall Co-Pilot. The operator is on a live call. Update their guidance based on the conversation so far.

CUSTOMER: {customer['name']} | {customer['area']} | {customer['plan']} | {customer['equipment']}
RISK: {fs['score']}/10 — {'; '.join(fs['drivers'][:2])}

CONVERSATION SO FAR:
{transcript_text}

CUSTOMER HISTORY:
{mem_ctx}

AREA CONTEXT:
{net_ctx}
{alert_ctx}

The operator needs to know what to say NEXT based on what the customer just said.
Be specific. Reference actual history. If customer mentioned a specific symptom, connect it to their past tickets.
If this sounds like a recurring issue, say so and recommend escalation.

Return ONLY valid JSON:
{{
  "opening_line": "",
  "what_to_say_now": "The EXACT next sentence the operator should say — human, informed, specific",
  "do_say": ["Specific action 1", "Specific action 2", "Specific action 3"],
  "dont_say": ["Warning 1", "Warning 2"],
  "likely_issue": "Updated diagnosis based on what customer just said",
  "confidence": 80,
  "suggested_resolution": "Most likely fix based on history + current symptoms",
  "escalate": false,
  "escalation_reason": "",
  "sentiment": "frustrated|neutral|angry|confused|satisfied",
  "area_alert": "",
  "talking_points": ["Key point 1", "Key point 2", "Key point 3"]
}}"""

        return self._call_groq(system, f"Update co-pilot for {customer['name']} based on latest conversation.")

    def generate_post_call_summary(
        self,
        customer:      dict,
        transcript:    list[dict],
        resolution:    str,
        frustration_before: dict,
    ) -> dict:
        """
        Called when the operator ends the call.
        Returns a structured summary for retention and follow-up.
        """
        if not transcript:
            transcript_text = "(No conversation recorded)"
        else:
            transcript_text = "\n".join(
                f"{e['speaker'].upper()}: {e['text']}" for e in transcript
            )

        system = f"""You are NetRecall Co-Pilot. A support call just ended. Generate a post-call summary.

CUSTOMER: {customer['name']} ({customer['area']}, {customer['plan']}, {customer['equipment']})
PRE-CALL RISK SCORE: {frustration_before['score']}/10 ({frustration_before['risk']})

CONVERSATION:
{transcript_text}

RESOLUTION APPLIED: {resolution or 'Not specified'}

Return ONLY valid JSON:
{{
  "summary": "2-3 sentence summary of what happened on this call",
  "issue_identified": "The specific issue that was identified",
  "resolution_applied": "What was done or scheduled",
  "follow_up_needed": true,
  "follow_up_action": "What needs to happen next (field visit, monitoring, etc.)",
  "knowledge_gained": "What new fact was learned that should be remembered",
  "customer_sentiment_end": "how customer felt at END of call: relieved|still frustrated|satisfied|angry|neutral",
  "risk_change": "improved|worsened|unchanged",
  "next_agent_note": "What the next agent should know if this customer calls again"
}}"""

        return self._call_groq(system, "Generate post-call summary.")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call_groq(self, system: str, user: str) -> dict:
        try:
            resp = self.groq.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=700,
                temperature=0.25,
            )
            text = resp.choices[0].message.content
            return self._parse_json(text)
        except Exception as e:
            fb = FALLBACK_BRIEFING.copy()
            fb["what_to_say_now"] = f"[Co-pilot error: {e}] — Review customer history manually."
            return fb

    def _parse_json(self, text: str) -> dict:
        """Robustly extract JSON from LLM output."""
        # Try to find a JSON block
        for pattern in [r'\{[\s\S]*\}', r'\{[^{}]*\}']:
            m = re.search(pattern, text)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        # Try raw parse
        try:
            return json.loads(text.strip())
        except Exception:
            pass
        # Fallback
        fb = FALLBACK_BRIEFING.copy()
        fb["what_to_say_now"] = text[:300] if text else fb["what_to_say_now"]
        return fb
