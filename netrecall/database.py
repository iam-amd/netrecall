"""
database.py — NetRecall SQLite CRM layer.

Stores structured customer data, tickets, call logs, and incidents.
This is the GROUND TRUTH store — fast lookups by phone, structured queries.

Hindsight Cloud is the SEMANTIC MEMORY layer — AI-searchable context, patterns.

Both are always written together. SQLite = who/what/when. Hindsight = why/how/insight.
"""

from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional


DB_PATH_DEFAULT = "netrecall.db"


class CustomerDB:
    """
    SQLite wrapper for NetRecall CRM.

    Thread-safe: uses check_same_thread=False so Streamlit's thread pool
    can share the connection safely (all writes are atomic SQL statements).
    """

    def __init__(self, db_path: str = DB_PATH_DEFAULT):
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row   # rows behave like dicts
        self._conn.execute("PRAGMA journal_mode=WAL")  # concurrent reads
        self._init_tables()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            phone             TEXT UNIQUE NOT NULL,
            email             TEXT DEFAULT '',
            area              TEXT DEFAULT '',
            plan              TEXT DEFAULT '',
            equipment         TEXT DEFAULT '',
            account_number    TEXT UNIQUE,
            address           TEXT DEFAULT '',
            created_at        TEXT DEFAULT (datetime('now')),
            last_call_at      TEXT,
            total_calls       INTEGER DEFAULT 0,
            frustration_score REAL DEFAULT 1.0
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id          TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES customers(id),
            issue_type  TEXT DEFAULT '',
            date_opened TEXT DEFAULT (date('now')),
            description TEXT DEFAULT '',
            resolution  TEXT DEFAULT '',
            status      TEXT DEFAULT 'open',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS calls (
            id                TEXT PRIMARY KEY,
            customer_id       TEXT NOT NULL REFERENCES customers(id),
            started_at        TEXT DEFAULT (datetime('now')),
            ended_at          TEXT,
            duration_seconds  INTEGER DEFAULT 0,
            transcript        TEXT DEFAULT '[]',
            resolution_text   TEXT DEFAULT '',
            actions           TEXT DEFAULT '[]',
            extracted_notes   TEXT DEFAULT '{}',
            post_call_summary TEXT DEFAULT '{}',
            memories_recalled INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id           TEXT PRIMARY KEY,
            sector       TEXT NOT NULL,
            reported_at  TEXT DEFAULT (datetime('now')),
            pattern      TEXT DEFAULT '',
            root_cause   TEXT DEFAULT '',
            resolution   TEXT DEFAULT '',
            status       TEXT DEFAULT 'open',
            affected_ids TEXT DEFAULT '[]'
        );
        """)
        self._conn.commit()

        # ── Twilio real-time tables (added separately so existing DBs migrate) ──
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS incoming_calls (
            id           TEXT PRIMARY KEY,
            call_sid     TEXT UNIQUE NOT NULL,
            from_phone   TEXT NOT NULL,
            to_phone     TEXT NOT NULL DEFAULT '',
            status       TEXT DEFAULT 'ringing',
            received_at  TEXT DEFAULT (datetime('now')),
            answered_at  TEXT,
            customer_id  TEXT
        );

        CREATE TABLE IF NOT EXISTS live_transcripts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sid    TEXT NOT NULL,
            speaker     TEXT DEFAULT 'customer',
            text        TEXT NOT NULL,
            confidence  REAL DEFAULT 0.0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_live_tx_call_sid
            ON live_transcripts(call_sid);

        CREATE TABLE IF NOT EXISTS call_signals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sid   TEXT NOT NULL,
            signal     TEXT NOT NULL,
            payload    TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_call_signals_sid
            ON call_signals(call_sid);
        """)
        self._conn.commit()

        # ── Plan field migration (added post-v1, safe to re-run) ──────────────
        for _col, _def in [
            ("plan_expiry",  "TEXT DEFAULT ''"),
            ("plan_status",  "TEXT DEFAULT 'active'"),
            ("monthly_rate", "REAL DEFAULT 0"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE customers ADD COLUMN {_col} {_def}"
                )
                self._conn.commit()
            except Exception:
                pass  # column already exists on subsequent runs

    def _row_to_dict(self, row) -> dict:
        """Convert a sqlite3.Row to a plain dict."""
        return dict(row) if row else None

    def _new_id(self, prefix: str = "C") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    # ── Customer CRUD ─────────────────────────────────────────────────────────

    def add_customer(
        self,
        name: str,
        phone: str,
        email: str = "",
        area: str = "",
        plan: str = "",
        equipment: str = "",
        account_number: str = "",
        address: str = "",
    ) -> str:
        """
        Create a new customer record.
        Returns the auto-generated customer ID like 'C-ab12cd34'.
        Raises sqlite3.IntegrityError if phone already exists.
        """
        cid = self._new_id("C")
        acc = account_number or f"NET-{datetime.now().strftime('%Y-%m')}-{cid}"
        self._conn.execute(
            """INSERT INTO customers
               (id, name, phone, email, area, plan, equipment, account_number, address)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (cid, name, phone, email, area, plan, equipment, acc, address),
        )
        self._conn.commit()
        return cid

    def get_customer_by_id(self, customer_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_customer_by_phone(self, phone: str) -> Optional[dict]:
        """Look up customer by exact phone number. Returns None if not found."""
        row = self._conn.execute(
            "SELECT * FROM customers WHERE phone = ?", (phone,)
        ).fetchone()
        return self._row_to_dict(row)

    def search_customers(self, query: str) -> list[dict]:
        """Full-text search across name, phone, email, account_number."""
        like = f"%{query}%"
        rows = self._conn.execute(
            """SELECT * FROM customers
               WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? OR account_number LIKE ?
               ORDER BY name""",
            (like, like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_customers(self) -> list[dict]:
        """Returns all customers ordered by frustration score descending."""
        rows = self._conn.execute(
            "SELECT * FROM customers ORDER BY frustration_score DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_customer_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    def update_customer_field(self, customer_id: str, field: str, value) -> None:
        """Generic field update. Only safe for known field names."""
        allowed = {"name", "phone", "email", "area", "plan", "equipment",
                   "account_number", "address", "last_call_at",
                   "total_calls", "frustration_score",
                   "plan_expiry", "plan_status", "monthly_rate"}
        if field not in allowed:
            raise ValueError(f"Field '{field}' not allowed for update")
        self._conn.execute(
            f"UPDATE customers SET {field} = ? WHERE id = ?", (value, customer_id)
        )
        self._conn.commit()

    def update_frustration_score(self, customer_id: str, score: float) -> None:
        self._conn.execute(
            "UPDATE customers SET frustration_score = ? WHERE id = ?",
            (round(score, 2), customer_id),
        )
        self._conn.commit()

    def bump_call_count(self, customer_id: str) -> None:
        self._conn.execute(
            "UPDATE customers SET total_calls = total_calls + 1, last_call_at = datetime('now') WHERE id = ?",
            (customer_id,),
        )
        self._conn.commit()

    # ── Ticket CRUD ───────────────────────────────────────────────────────────

    def add_ticket(
        self,
        customer_id: str,
        issue_type: str,
        description: str,
        resolution: str = "",
        status: str = "open",
    ) -> str:
        """Creates a ticket and returns its ID."""
        tid = self._new_id("T")
        self._conn.execute(
            """INSERT INTO tickets
               (id, customer_id, issue_type, description, resolution, status)
               VALUES (?,?,?,?,?,?)""",
            (tid, customer_id, issue_type, description, resolution, status),
        )
        self._conn.commit()
        return tid

    def get_tickets_for_customer(self, customer_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM tickets WHERE customer_id = ? ORDER BY date_opened DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_ticket(self, ticket_id: str, resolution: str) -> None:
        self._conn.execute(
            "UPDATE tickets SET status = 'resolved', resolution = ? WHERE id = ?",
            (resolution, ticket_id),
        )
        self._conn.commit()

    def get_ticket_count_by_type(self) -> dict[str, int]:
        """Returns {issue_type: count} for all tickets (any status)."""
        rows = self._conn.execute(
            """SELECT issue_type, COUNT(*) as cnt FROM tickets
               WHERE issue_type != '' GROUP BY issue_type ORDER BY cnt DESC"""
        ).fetchall()
        return {r["issue_type"]: r["cnt"] for r in rows}

    def get_open_tickets(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM tickets WHERE status = 'open' ORDER BY date_opened DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Call Logging ──────────────────────────────────────────────────────────

    def start_call(self, customer_id: str) -> str:
        """
        Creates an open call record. Returns the call_id.
        Call `end_call()` when the call finishes.
        """
        call_id = self._new_id("CALL")
        self._conn.execute(
            "INSERT INTO calls (id, customer_id) VALUES (?,?)",
            (call_id, customer_id),
        )
        self._conn.commit()
        self.bump_call_count(customer_id)
        return call_id

    def end_call(
        self,
        call_id: str,
        transcript: list,
        resolution_text: str,
        actions: list,
        extracted_notes: dict,
        post_call_summary: dict,
        memories_recalled: int,
    ) -> None:
        """Finalize a call record with all collected data."""
        started_row = self._conn.execute(
            "SELECT started_at FROM calls WHERE id = ?", (call_id,)
        ).fetchone()

        duration = 0
        if started_row:
            try:
                start = datetime.fromisoformat(started_row["started_at"])
                duration = int((datetime.now() - start).total_seconds())
            except Exception:
                pass

        self._conn.execute(
            """UPDATE calls SET
               ended_at = datetime('now'),
               duration_seconds = ?,
               transcript = ?,
               resolution_text = ?,
               actions = ?,
               extracted_notes = ?,
               post_call_summary = ?,
               memories_recalled = ?
               WHERE id = ?""",
            (
                duration,
                json.dumps(transcript),
                resolution_text,
                json.dumps(actions),
                json.dumps(extracted_notes),
                json.dumps(post_call_summary),
                memories_recalled,
                call_id,
            ),
        )
        self._conn.commit()

    def log_action(self, call_id: str, action: str, note: str = "") -> None:
        """
        Append a timestamped action to an in-progress call's actions list.
        Safe to call multiple times during a call.
        """
        row = self._conn.execute(
            "SELECT actions FROM calls WHERE id = ?", (call_id,)
        ).fetchone()
        if not row:
            return
        try:
            actions = json.loads(row["actions"] or "[]")
        except Exception:
            actions = []
        actions.append({
            "action":    action,
            "note":      note,
            "timestamp": datetime.now().strftime("%H:%M"),
        })
        self._conn.execute(
            "UPDATE calls SET actions = ? WHERE id = ?",
            (json.dumps(actions), call_id),
        )
        self._conn.commit()

    def get_calls_for_customer(self, customer_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM calls WHERE customer_id = ? ORDER BY started_at DESC",
            (customer_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Parse JSON blobs
            for field in ("transcript", "actions", "extracted_notes", "post_call_summary"):
                try:
                    d[field] = json.loads(d[field] or "[]" if field != "extracted_notes" else d[field] or "{}")
                except Exception:
                    d[field] = [] if field != "extracted_notes" else {}
            result.append(d)
        return result

    def get_recent_calls(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Incidents ─────────────────────────────────────────────────────────────

    def add_incident(
        self,
        sector: str,
        pattern: str,
        root_cause: str = "",
        resolution: str = "",
        affected_ids: list = None,
    ) -> str:
        iid = self._new_id("INC")
        self._conn.execute(
            """INSERT INTO incidents (id, sector, pattern, root_cause, resolution, affected_ids)
               VALUES (?,?,?,?,?,?)""",
            (iid, sector, pattern, root_cause, resolution,
             json.dumps(affected_ids or [])),
        )
        self._conn.commit()
        return iid

    def get_open_incidents(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM incidents WHERE status = 'open' ORDER BY reported_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_incident(self, incident_id: str, resolution: str) -> None:
        self._conn.execute(
            "UPDATE incidents SET status = 'resolved', resolution = ? WHERE id = ?",
            (resolution, incident_id),
        )
        self._conn.commit()

    # ── Dashboard helpers ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Returns aggregate stats for the dashboard metrics row."""
        total_customers = self._conn.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]
        total_calls = self._conn.execute(
            "SELECT COUNT(*) FROM calls WHERE ended_at IS NOT NULL"
        ).fetchone()[0]
        total_tickets = self._conn.execute(
            "SELECT COUNT(*) FROM tickets"
        ).fetchone()[0]
        total_incidents = self._conn.execute(
            "SELECT COUNT(*) FROM incidents"
        ).fetchone()[0]
        avg_duration = self._conn.execute(
            "SELECT AVG(duration_seconds) FROM calls WHERE duration_seconds > 0"
        ).fetchone()[0] or 0

        return {
            "total_customers":  total_customers,
            "total_calls":      total_calls,
            "total_tickets":    total_tickets,
            "total_incidents":  total_incidents,
            "avg_duration_sec": int(avg_duration),
        }

    def get_high_frustration_customers(self, threshold: float = 6.0) -> list[dict]:
        rows = self._conn.execute(
            """SELECT * FROM customers WHERE frustration_score >= ?
               ORDER BY frustration_score DESC""",
            (threshold,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sector_activity(self) -> dict[str, int]:
        """
        Returns {sector: call_count} for calls started in the last 24 hours.
        Joins calls → customers to get the sector.
        """
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        rows = self._conn.execute(
            """SELECT c.area as sector, COUNT(*) as cnt
               FROM calls ca JOIN customers c ON ca.customer_id = c.id
               WHERE ca.started_at >= ?
               GROUP BY c.area""",
            (cutoff,),
        ).fetchall()
        return {r["sector"]: r["cnt"] for r in rows}

    def upsert_customer(
        self,
        customer_id: str,
        name: str,
        phone: str,
        **kwargs,
    ) -> None:
        """
        Insert or update a customer by ID. Used by demo_seeder.
        Silently ignores phone uniqueness conflicts if ID matches.
        """
        existing = self.get_customer_by_id(customer_id)
        if existing:
            # Update plan fields if caller provides them (allows re-seeding to refresh plan data)
            updates = {}
            for fld in ("plan_expiry", "plan_status", "monthly_rate"):
                if fld in kwargs and kwargs[fld] not in (None, ""):
                    updates[fld] = kwargs[fld]
            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                self._conn.execute(
                    f"UPDATE customers SET {set_clause} WHERE id = ?",
                    (*updates.values(), customer_id),
                )
                self._conn.commit()
            return
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO customers
                   (id, name, phone, email, area, plan, equipment, account_number,
                    address, plan_expiry, plan_status, monthly_rate)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    customer_id, name, phone,
                    kwargs.get("email", ""),
                    kwargs.get("area", ""),
                    kwargs.get("plan", ""),
                    kwargs.get("equipment", ""),
                    kwargs.get("account_number", f"NET-{customer_id}"),
                    kwargs.get("address", ""),
                    kwargs.get("plan_expiry", ""),
                    kwargs.get("plan_status", "active"),
                    kwargs.get("monthly_rate", 0),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass  # phone collision with different ID — caller handles

    def upsert_ticket(self, ticket_id: str, customer_id: str, **kwargs) -> None:
        """Insert a ticket by ID. Used by demo_seeder."""
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO tickets
                   (id, customer_id, issue_type, description, resolution, status, date_opened)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    ticket_id, customer_id,
                    kwargs.get("issue_type", ""),
                    kwargs.get("description", ""),
                    kwargs.get("resolution", ""),
                    kwargs.get("status", "resolved"),
                    kwargs.get("date_opened", ""),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass


# ── Twilio Real-Time Integration ─────────────────────────────────────────────

    def register_incoming_call(
        self,
        call_sid:   str,
        from_phone: str,
        to_phone:   str = "",
    ) -> str:
        """
        Write a new ringing call row when Twilio fires the /incoming webhook.
        Idempotent — if call_sid already exists (Twilio retry), ignores silently.
        Returns an internal ID (IC-xxxxxxxx).
        """
        ic_id = self._new_id("IC")
        try:
            self._conn.execute(
                """INSERT INTO incoming_calls
                   (id, call_sid, from_phone, to_phone, status)
                   VALUES (?, ?, ?, ?, 'ringing')""",
                (ic_id, call_sid, from_phone, to_phone),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass  # Twilio retry — already registered
        return ic_id

    def get_pending_incoming_call(self) -> Optional[dict]:
        """
        Return the oldest unhandled ringing call, or None.
        'Unhandled' means status='ringing' AND customer_id IS NULL.
        Streamlit ringing watcher polls this every 2 s.
        """
        row = self._conn.execute(
            """SELECT * FROM incoming_calls
               WHERE status = 'ringing' AND customer_id IS NULL
               ORDER BY received_at ASC LIMIT 1"""
        ).fetchone()
        return self._row_to_dict(row)

    def mark_incoming_call_answered(
        self,
        call_sid:    str,
        customer_id: str,
    ) -> None:
        """Mark an incoming call as answered and link it to a customer."""
        self._conn.execute(
            """UPDATE incoming_calls
               SET status = 'answered',
                   customer_id = ?,
                   answered_at = datetime('now')
               WHERE call_sid = ?""",
            (customer_id, call_sid),
        )
        self._conn.commit()

    def add_live_transcript(
        self,
        call_sid:   str,
        text:       str,
        confidence: float = 0.0,
        speaker:    str   = "customer",
    ) -> int:
        """
        Append one Twilio STT result line.
        Empty/whitespace text is silently dropped.
        Returns the autoincrement row id (high-water mark for polling).
        """
        text = (text or "").strip()
        if not text:
            return 0
        cur = self._conn.execute(
            """INSERT INTO live_transcripts
               (call_sid, speaker, text, confidence)
               VALUES (?, ?, ?, ?)""",
            (call_sid, speaker, text, round(confidence, 3)),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_new_transcripts(
        self,
        call_sid: str,
        after_id: int = 0,
    ) -> list[dict]:
        """
        Return all live_transcripts rows for call_sid with id > after_id.
        Streamlit transcript watcher calls this with last_tx_id as after_id.
        """
        rows = self._conn.execute(
            """SELECT * FROM live_transcripts
               WHERE call_sid = ? AND id > ?
               ORDER BY id ASC""",
            (call_sid, after_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def write_call_signal(
        self,
        call_sid: str,
        signal:   str,
        payload:  dict = None,
    ) -> int:
        """
        Write a signal row (e.g. 'ringing', 'in-progress', 'completed').
        Called by the webhook server on Twilio status callbacks.
        Returns autoincrement row id.
        """
        cur = self._conn.execute(
            """INSERT INTO call_signals (call_sid, signal, payload)
               VALUES (?, ?, ?)""",
            (call_sid, signal, json.dumps(payload or {})),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_new_signals(
        self,
        call_sid: str,
        after_id: int = 0,
    ) -> list[dict]:
        """
        Return call_signals rows for call_sid with id > after_id.
        Streamlit hangup watcher uses this to detect terminal call status.
        """
        rows = self._conn.execute(
            """SELECT * FROM call_signals
               WHERE call_sid = ? AND id > ?
               ORDER BY id ASC""",
            (call_sid, after_id),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.get("payload") or "{}")
            except Exception:
                d["payload"] = {}
            result.append(d)
        return result

    def get_incoming_call_by_sid(self, call_sid: str) -> Optional[dict]:
        """Return the incoming_calls row for a given Twilio CallSid."""
        row = self._conn.execute(
            "SELECT * FROM incoming_calls WHERE call_sid = ?",
            (call_sid,),
        ).fetchone()
        return self._row_to_dict(row)


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    test_path = "test_netrecall.db"
    if os.path.exists(test_path):
        os.remove(test_path)

    db = CustomerDB(test_path)
    print("Tables created OK")

    # Add customer
    cid = db.add_customer("Priya Sharma", "+91-9876501001",
                          area="Sector 4", plan="100Mbps",
                          equipment="TP-Link ONT (SN: TL-4A2B9C)")
    print(f"Added customer: {cid}")

    # Lookup by phone
    c = db.get_customer_by_phone("+91-9876501001")
    assert c["name"] == "Priya Sharma"
    print(f"Phone lookup OK: {c['name']}")

    # Add tickets
    t1 = db.add_ticket(cid, "ONT light blinking red",
                       "Customer called. ONT red LOS light.",
                       "Remote ONT reboot via OLT portal.", "resolved")
    t2 = db.add_ticket(cid, "ONT light blinking red",
                       "Same red LOS issue again.",
                       "Remote ONT reboot again. Escalated.", "resolved")
    print(f"Tickets added: {t1}, {t2}")

    tickets = db.get_tickets_for_customer(cid)
    assert len(tickets) == 2
    print(f"Ticket count: {len(tickets)}")

    # Call lifecycle
    call_id = db.start_call(cid)
    print(f"Call started: {call_id}")

    db.log_action(call_id, "olt_reboot", "OLT port rebooted remotely")
    db.log_action(call_id, "escalate", "Scheduled field visit")

    db.end_call(
        call_id,
        transcript=[{"speaker": "customer", "text": "My internet is down", "ts": "10:00"}],
        resolution_text="Scheduled field visit",
        actions=[],
        extracted_notes={"symptoms": ["ONT red light"], "what_was_tried": ["reboot"]},
        post_call_summary={"summary": "Recurring ONT issue. Field visit scheduled."},
        memories_recalled=5,
    )
    print("Call ended OK")

    calls = db.get_calls_for_customer(cid)
    assert len(calls) == 1
    assert calls[0]["memories_recalled"] == 5
    print(f"Call log verified: {calls[0]['resolution_text']}")

    # Stats
    stats = db.get_stats()
    print(f"Stats: {stats}")
    assert stats["total_customers"] == 1
    assert stats["total_tickets"] == 2
    assert stats["total_calls"] == 1

    # Frustration update
    db.update_frustration_score(cid, 7.5)
    c2 = db.get_customer_by_id(cid)
    assert c2["frustration_score"] == 7.5
    print(f"Frustration score updated: {c2['frustration_score']}")

    # Search
    results = db.search_customers("Priya")
    assert len(results) == 1
    print(f"Search OK: found {results[0]['name']}")

    db._conn.close()
    os.remove(test_path)
    print()
    print("ALL TESTS PASSED — database.py is working correctly")
