"""
resolution_engine.py — Resolution confidence scoring + Customer frustration scoring.

Data source: CustomerDB (SQLite) — live tickets and call history.
No more hardcoded seed_data. Confidence and frustration scores reflect
actual accumulated data from real calls.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from database import CustomerDB

RESOLUTION_BANK = "netrecall-resolutions"

# ── Issue keyword matcher ─────────────────────────────────────────────────────
ISSUE_KEYWORDS: dict[str, list[str]] = {
    "Slow speed complaint":            ["slow", "speed", "mbps", "bandwidth", "throttl", "fast", "quick"],
    "Intermittent disconnection":      ["drop", "disconnect", "cut", "intermittent", "unstable", "keeps going", "keeps dropping", "reconnect"],
    "ONT light blinking red":          ["red", "blink", "los", "ont light", "fiber light", "signal light", "orange light"],
    "No internet after power outage":  ["power", "outage", "electricity", "after power", "shutdown", "back online", "light went"],
    "WiFi not reaching certain rooms": ["wifi", "wi-fi", "range", "reach", "room", "signal", "weak", "dead zone", "coverage"],
    "IP conflict issues":              ["ip", "conflict", "169.", "apipa", "address", "duplicate", "same ip"],
    "DNS resolution failures":         ["dns", "website", "domain", "resolve", "browser", "open", "teams", "office", "can't open"],
}


def detect_issue_type(message: str) -> Optional[str]:
    """Best-guess issue type from a free-form operator or customer message."""
    msg = message.lower()
    scores: dict[str, int] = {}
    for issue, keywords in ISSUE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in msg)
        if hits:
            scores[issue] = hits
    return max(scores, key=lambda k: scores[k]) if scores else None


# ── ResolutionEngine ──────────────────────────────────────────────────────────

class ResolutionEngine:
    """
    Computes resolution confidence and frustration scores from live DB data.
    Stats are re-computed from SQLite on demand so they always reflect
    the current state of knowledge.
    """

    def __init__(self, db: "CustomerDB", hindsight_client=None):
        self._db = db
        self._hindsight = hindsight_client
        self._live_call_counts: dict[str, int] = {}

    # ── Resolution Confidence ─────────────────────────────────────────────────

    def compute_confidence(
        self,
        issue_type: Optional[str],
        equipment: str = "",
        area: str = "",
    ) -> dict:
        """
        Return confidence dict based on ticket history in the live DB.
        confidence    int 0-100
        total_cases   int
        primary_fix   str
        fallback_fix  str | None
        equipment_specific bool
        """
        if not issue_type:
            return self._empty_conf()

        stats = self._build_live_stats()
        issue_stats = stats.get(issue_type)
        if not issue_stats:
            return self._empty_conf()

        total = issue_stats["count"]
        resolutions = issue_stats["resolutions"]

        # Confidence scales asymptotically with case count (caps at 97%)
        confidence = min(97, 50 + (total * 7))

        # Equipment-specific boost
        eq_key = equipment.split("(")[0].strip() if equipment else ""
        eq_count = issue_stats["equipment_map"].get(eq_key, 0)
        equipment_specific = eq_count > 0
        if equipment_specific:
            confidence = min(98, confidence + (eq_count * 2))

        primary  = resolutions[0] if resolutions else "Standard troubleshooting"
        fallback = None
        for r in resolutions[1:]:
            if r and r[:80] != primary[:80]:
                fallback = r
                break

        return {
            "confidence":         confidence,
            "total_cases":        total,
            "primary_fix":        primary[:160],
            "fallback_fix":       (fallback[:160] if fallback else None),
            "equipment_specific": equipment_specific,
            "eq_count":           eq_count,
            "eq_key":             eq_key,
        }

    def _empty_conf(self) -> dict:
        return {
            "confidence": 0, "total_cases": 0,
            "primary_fix": "No historical data yet — first time we are seeing this issue.",
            "fallback_fix": None, "equipment_specific": False,
            "eq_count": 0, "eq_key": "",
        }

    # ── Frustration Score ─────────────────────────────────────────────────────

    def record_live_call(self, customer_id: str) -> None:
        """Track each live call this session (in addition to stored history)."""
        self._live_call_counts[customer_id] = (
            self._live_call_counts.get(customer_id, 0) + 1
        )

    def compute_frustration_score(self, customer: dict) -> dict:
        """
        Return 1-10 frustration score, risk level, colour, badge, and drivers.
        Reads ticket history from SQLite if db is available.
        Falls back to customer["tickets"] list if passed in directly.
        """
        # Support both DB-driven and dict-driven modes
        if self._db is not None:
            try:
                tickets = self._db.get_tickets_for_customer(customer["id"])
            except Exception:
                tickets = customer.get("tickets", [])
        else:
            tickets = customer.get("tickets", [])

        live_calls  = self._live_call_counts.get(customer["id"], 0)
        total_calls = len(tickets) + live_calls

        # Recurring same-issue pattern
        recurring: dict[str, int] = {}
        for t in tickets:
            issue = t.get("issue_type") or t.get("type", "")
            if issue:
                recurring[issue] = recurring.get(issue, 0) + 1
        max_recurring = max(recurring.values()) if recurring else 0
        top_issue = max(recurring, key=lambda k: recurring[k]) if recurring else None

        # Temp fix count
        temp_kw = ["reboot", "restart", "again", "temporary", "remote reboot", "workaround"]
        temp_count = sum(
            1 for t in tickets
            if any(kw in (t.get("resolution", "") or "").lower() for kw in temp_kw)
        )

        # Score (1.0 → 10.0)
        score = 1.5
        score += min(2.5, total_calls * 0.55)
        score += min(2.5, max(0, max_recurring - 1) * 1.3)
        score += min(1.5, temp_count * 0.65)
        score += min(0.8, live_calls * 0.4)
        if "200" in customer.get("plan", ""):
            score += 0.4

        score = round(min(10.0, max(1.0, score)), 1)

        if score >= 8.0:
            risk, color, badge = "critical", "#dc2626", "🔴"
        elif score >= 6.0:
            risk, color, badge = "high",     "#ea580c", "🟠"
        elif score >= 4.0:
            risk, color, badge = "medium",   "#ca8a04", "🟡"
        else:
            risk, color, badge = "low",      "#16a34a", "🟢"

        drivers = []
        if max_recurring >= 3:
            drivers.append(f"Same issue {max_recurring}× ({top_issue})")
        elif max_recurring == 2:
            drivers.append(f"Recurring: {top_issue}")
        if temp_count >= 2:
            drivers.append(f"{temp_count} temp fixes applied")
        if live_calls > 0:
            drivers.append(f"{live_calls} call(s) this session")
        if total_calls >= 4:
            drivers.append(f"{total_calls} total support calls")
        if not drivers:
            drivers.append("New customer — no history yet" if total_calls == 0 else "Minimal history")

        return {
            "score":        score,
            "risk":         risk,
            "color":        color,
            "badge":        badge,
            "drivers":      drivers,
            "total_calls":  total_calls,
            "max_recurring":max_recurring,
            "temp_fixes":   temp_count,
        }

    # ── Knowledge Base Summary ────────────────────────────────────────────────

    def get_knowledge_stats(self) -> dict:
        stats = self._build_live_stats()
        db_stats = {}
        if self._db:
            try:
                db_stats = self._db.get_stats()
            except Exception:
                pass

        total = sum(s["count"] for s in stats.values())
        top = sorted(
            [(k, v["count"]) for k, v in stats.items()],
            key=lambda x: -x[1],
        )
        return {
            "total_issue_types":   len(stats),
            "total_resolutions":   total,
            "customers_in_system": db_stats.get("total_customers", 0),
            "historical_incidents":db_stats.get("total_incidents", 0),
            "top_issues":          top[:7],
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    def _build_live_stats(self) -> dict:
        """
        Build issue-type statistics from the live SQLite ticket database.
        Called on demand so dashboard always reflects current data.
        """
        stats: dict[str, dict] = {}
        if self._db is None:
            return stats

        try:
            # Pull all tickets from DB
            all_customers = self._db.get_all_customers()
            for customer in all_customers:
                eq = (customer.get("equipment") or "").split("(")[0].strip()
                tickets = self._db.get_tickets_for_customer(customer["id"])
                for t in tickets:
                    issue = t.get("issue_type", "")
                    if not issue:
                        continue
                    if issue not in stats:
                        stats[issue] = {
                            "count": 0, "resolutions": [],
                            "equipment_map": {}, "area_map": {},
                        }
                    stats[issue]["count"] += 1
                    res = t.get("resolution", "")
                    if res:
                        stats[issue]["resolutions"].append(res)
                    if eq:
                        stats[issue]["equipment_map"][eq] = (
                            stats[issue]["equipment_map"].get(eq, 0) + 1
                        )
                    area = customer.get("area", "")
                    if area:
                        stats[issue]["area_map"][area] = (
                            stats[issue]["area_map"].get(area, 0) + 1
                        )
        except Exception:
            pass

        return stats
