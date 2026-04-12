"""
network_patterns.py — Real-time area-wide failure pattern detection.

Tracks tickets received during the current session in memory.
When 2+ tickets arrive from the same Sector within 60 minutes it fires an
ALERT and queries Hindsight for historical incidents in that sector so the
operator knows what happened last time and how it was resolved.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional


NETWORK_BANK = "netrecall-network"
ALERT_THRESHOLD = 2          # tickets in same sector within the window
WINDOW_MINUTES = 60


class PatternDetector:
    def __init__(self, hindsight_client=None):
        self._hindsight = hindsight_client
        # list of dicts: {customer_id, customer_name, sector, issue, timestamp}
        self._recent: list[dict] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def record_ticket(
        self,
        customer_id: str,
        customer_name: str,
        sector: str,
        issue: str,
    ) -> None:
        """Call this every time a new support interaction starts."""
        self._recent.append(
            {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "sector": sector,
                "issue": issue,
                "timestamp": datetime.now(),
            }
        )
        self._prune()

    def check_for_pattern(self, sector: str) -> Optional[dict]:
        """
        Returns an alert dict if the sector has hit the threshold, else None.

        Alert dict keys:
          sector, ticket_count, affected_customers, issues,
          historical_match (str | None), window_minutes
        """
        self._prune()
        cutoff = datetime.now() - timedelta(minutes=WINDOW_MINUTES)
        in_window = [
            t for t in self._recent
            if t["sector"] == sector and t["timestamp"] >= cutoff
        ]

        if len(in_window) < ALERT_THRESHOLD:
            return None

        historical = self._recall_historical(sector, in_window)
        return {
            "sector": sector,
            "ticket_count": len(in_window),
            "affected_customers": [t["customer_name"] for t in in_window],
            "issues": [t["issue"] for t in in_window],
            "historical_match": historical,
            "window_minutes": WINDOW_MINUTES,
        }

    def get_sector_summary(self, sector: str) -> dict:
        """How many tickets have come in for this sector in the last hour."""
        self._prune()
        cutoff = datetime.now() - timedelta(minutes=WINDOW_MINUTES)
        count = sum(
            1 for t in self._recent
            if t["sector"] == sector and t["timestamp"] >= cutoff
        )
        return {"sector": sector, "recent_count": count, "window_minutes": WINDOW_MINUTES}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _prune(self) -> None:
        """Drop entries older than the detection window."""
        cutoff = datetime.now() - timedelta(minutes=WINDOW_MINUTES)
        self._recent = [t for t in self._recent if t["timestamp"] >= cutoff]

    def _recall_historical(self, sector: str, current_tickets: list[dict]) -> Optional[str]:
        """Query Hindsight for past area-wide incidents in this sector."""
        if not self._hindsight:
            return None

        # Build a query that references current issue types for better matching
        issue_summary = "; ".join(set(t["issue"] for t in current_tickets))
        query = (
            f"What area-wide outages or incidents happened in {sector}? "
            f"Current symptoms: {issue_summary}. "
            f"What was the root cause and how was it resolved?"
        )

        try:
            sector_tag = f"sector:{sector.lower().replace(' ', '-')}"
            response = self._hindsight.recall(
                bank_id=NETWORK_BANK,
                query=query,
                tags=[sector_tag],
                tags_match="any_strict",
                budget="mid",
                max_tokens=1200,
            )
            if not response.results:
                return None

            snippets = []
            for r in response.results[:3]:
                snippets.append(r.text)
            return " | ".join(snippets)

        except Exception:
            return None
