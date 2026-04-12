"""
agent.py — NetRecall core agent.

Wraps Groq (LLM) and Hindsight (memory) to produce two response modes:

  Memory ON  → recalls full customer history + area patterns, gives a
               personalised, diagnostically-aware answer.

  Memory OFF → no recall, no retain; generic chatbot response that shows
               how support calls go *without* memory.

Each handle_message() call returns (response_text, MemoryLog).
The MemoryLog carries recalled facts, retained confirmations, errors,
and the detected issue type (used by the UI for confidence scoring).
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from resolution_engine import detect_issue_type

CUSTOMER_BANK   = "netrecall-customers"
NETWORK_BANK    = "netrecall-network"
RESOLUTION_BANK = "netrecall-resolutions"


class MemoryLog:
    """Container for what was recalled / retained in one agent turn."""

    def __init__(self):
        self.recalled:            list[dict] = []   # {source, text, type}
        self.retained:            list[str]  = []   # human-readable confirmations
        self.errors:              list[str]  = []
        self.detected_issue_type: Optional[str] = None

    def add_recalled(self, source: str, results: list) -> None:
        for r in results:
            self.recalled.append({
                "source": source,
                "text":   r.text,
                "type":   r.type,
            })

    def add_retained(self, description: str) -> None:
        self.retained.append(description)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def to_dict(self) -> dict:
        return {
            "recalled":            self.recalled,
            "retained":            self.retained,
            "errors":              self.errors,
            "detected_issue_type": self.detected_issue_type,
        }


class NetRecallAgent:

    MODEL = "llama-3.3-70b-versatile"

    def __init__(self, groq_client, hindsight_client=None):
        self.groq      = groq_client
        self.hindsight = hindsight_client

    # ── Public entry point ────────────────────────────────────────────────────

    def handle_message(
        self,
        customer:   dict,
        message:    str,
        memory_on:  bool,
        frustration_score: Optional[dict] = None,
    ) -> tuple[str, MemoryLog]:
        """
        Process one operator message.

        Returns (response_text, memory_log).

        frustration_score — pre-computed dict from ResolutionEngine.
        Used to colour the agent's escalation language appropriately.
        """
        log = MemoryLog()
        log.detected_issue_type = detect_issue_type(message)

        if not memory_on or not self.hindsight:
            return self._generic_response(message), log

        # ── Memory ON path ────────────────────────────────────────────────────
        customer_mems   = self._recall_customer(customer, message, log)
        network_mems    = self._recall_network(customer, message, log)
        resolution_mems = self._recall_resolutions(message, log)

        response = self._memory_response(
            customer, message,
            customer_mems, network_mems, resolution_mems,
            frustration_score,
        )

        self._retain_interaction(customer, message, response, log)
        return response, log

    # ── Recall helpers ────────────────────────────────────────────────────────

    def _recall_customer(self, customer: dict, query: str, log: MemoryLog) -> list:
        try:
            resp = self.hindsight.recall(
                bank_id=CUSTOMER_BANK,
                query=(
                    f"What do we know about {customer['name']} ({customer['id']})? "
                    f"Past tickets, equipment, recurring issues, resolutions. "
                    f"Current issue: {query}"
                ),
                tags=[f"customer:{customer['id']}"],
                tags_match="any_strict",
                budget="mid",
                max_tokens=2000,
            )
            log.add_recalled("Customer History", resp.results)
            return resp.results
        except Exception as e:
            log.add_error(f"Customer recall: {e}")
            return []

    def _recall_network(self, customer: dict, query: str, log: MemoryLog) -> list:
        try:
            sector_tag = f"sector:{customer['area'].lower().replace(' ', '-')}"
            resp = self.hindsight.recall(
                bank_id=NETWORK_BANK,
                query=(
                    f"Area-wide network incidents or patterns in {customer['area']}. "
                    f"Related symptoms: {query}"
                ),
                tags=[sector_tag],
                tags_match="any_strict",
                budget="low",
                max_tokens=1000,
            )
            log.add_recalled("Network Patterns", resp.results)
            return resp.results
        except Exception as e:
            log.add_error(f"Network recall: {e}")
            return []

    def _recall_resolutions(self, query: str, log: MemoryLog) -> list:
        try:
            resp = self.hindsight.recall(
                bank_id=RESOLUTION_BANK,
                query=f"What is the proven fix for: {query}",
                budget="low",
                max_tokens=800,
            )
            log.add_recalled("Resolution Knowledge", resp.results)
            return resp.results
        except Exception as e:
            log.add_error(f"Resolution recall: {e}")
            return []

    # ── Retain ────────────────────────────────────────────────────────────────

    def _retain_interaction(
        self,
        customer: dict,
        message:  str,
        response: str,
        log:      MemoryLog,
    ) -> None:
        try:
            now          = datetime.now()
            customer_tag = f"customer:{customer['id']}"
            sector_tag   = f"sector:{customer['area'].lower().replace(' ', '-')}"

            content = (
                f"Support interaction with {customer['name']} ({customer['id']}) "
                f"on {now.strftime('%Y-%m-%d %H:%M')}:\n"
                f"Issue reported: {message}\n"
                f"Agent action/response: {response}"
            )
            self.hindsight.retain(
                bank_id=CUSTOMER_BANK,
                content=content,
                context="live-support-interaction",
                tags=[customer_tag, sector_tag],
                document_id=f"{customer['id']}-{now.isoformat()}",
                timestamp=now.isoformat(),
            )
            log.add_retained(
                f"Saved interaction for {customer['name']} "
                f"({customer['area']}) at {now.strftime('%H:%M')}"
            )
        except Exception as e:
            log.add_error(f"Retain: {e}")

    # ── Response generators ───────────────────────────────────────────────────

    def _memory_response(
        self,
        customer:        dict,
        message:         str,
        customer_mems:   list,
        network_mems:    list,
        resolution_mems: list,
        frustration_score: Optional[dict],
    ) -> str:

        cx = (
            "\n".join(f"  • {m.text}" for m in customer_mems)
            if customer_mems else "  (no prior history found in memory)"
        )
        nx = (
            "\n".join(f"  • {m.text}" for m in network_mems)
            if network_mems else "  (no area incidents found)"
        )
        rx = (
            "\n".join(f"  • {m.text}" for m in resolution_mems)
            if resolution_mems else "  (no resolution data found)"
        )

        # Frustration-aware escalation guidance
        escalation_note = ""
        if frustration_score:
            risk = frustration_score.get("risk", "low")
            score = frustration_score.get("score", 0)
            temp_fixes = frustration_score.get("temp_fixes", 0)
            if risk == "critical":
                escalation_note = (
                    f"\nFRUSTRATION ALERT: This customer has a frustration score of {score}/10 "
                    f"with {temp_fixes} previous temp fixes applied. "
                    "Do NOT offer another temporary fix. Escalate to field visit or hardware replacement. "
                    "Acknowledge their frustration explicitly."
                )
            elif risk == "high":
                escalation_note = (
                    f"\nHIGH RISK: Frustration score {score}/10. "
                    "Offer a concrete next step beyond rebooting. Consider scheduling a field check."
                )

        system_prompt = f"""You are NetRecall, an intelligent ISP support AI with full persistent memory.

━━ CUSTOMER ON THE LINE ━━
Name      : {customer['name']}
Account   : {customer['account_number']}
Area      : {customer['area']}
Plan      : {customer['plan']} fiber broadband
Equipment : {customer['equipment']}

━━ RECALLED: CUSTOMER HISTORY ━━
{cx}

━━ RECALLED: AREA NETWORK PATTERNS ({customer['area']}) ━━
{nx}

━━ RECALLED: RESOLUTION KNOWLEDGE BASE ━━
{rx}
{escalation_note}

━━ RESPONSE RULES ━━
1. Address customer by FIRST NAME only.
2. Reference their exact equipment model and plan tier.
3. Connect this issue to their ticket history — is this a pattern or a new issue?
4. Recommend the specific fix that WORKED before (from resolution knowledge), not a generic one.
5. If this is the 2nd or 3rd time the same issue has occurred: say so explicitly and escalate
   (schedule field visit / OLT port reassignment / hardware swap) instead of another temp fix.
6. If the area-wide pattern shows other customers with the same issue, tell them it's not isolated.
7. Be specific and human. No "Please hold while I check your account." You already know.
8. Keep response to 3-5 sentences. No bullet points. Conversational, confident, knowledgeable."""

        resp = self.groq.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Customer issue: {message}"},
            ],
            max_tokens=420,
            temperature=0.35,
        )
        return resp.choices[0].message.content

    def _generic_response(self, message: str) -> str:
        system_prompt = (
            "You are a basic ISP helpdesk bot with NO customer history, NO memory, and NO data. "
            "You do not know who you're speaking to. You have no past ticket history, no equipment details, "
            "no idea if this has happened before, and no area information. "
            "Respond generically with standard first-line troubleshooting. "
            "Typical responses: please restart your router/ONT, check cables, wait 5 minutes, "
            "clear DNS cache, power cycle equipment. "
            "Do NOT personalise. Do NOT reference any history. 2-3 sentences max."
        )
        resp = self.groq.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Customer issue: {message}"},
            ],
            max_tokens=180,
            temperature=0.3,
        )
        return resp.choices[0].message.content
