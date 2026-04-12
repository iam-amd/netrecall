"""
demo_seeder.py — Load demo customers into SQLite + Hindsight Cloud.

Seeds 2 customers in the same sector (Sector 4) so the area-alert
pattern fires during the demo. They arrive with ticket history so
the co-pilot can immediately reference past issues on the first demo call.

Called from the UI via a "Load Demo Data" button in the IDLE state.
Running it multiple times is safe — upsert_customer / upsert_ticket
skip records that already exist.
"""

from __future__ import annotations
from typing import Callable, Optional


# ── Demo customers (2 in Sector 4 to trigger area alert) ─────────────────────

DEMO_CUSTOMERS = [
    {
        "id":             "CUST001",
        "name":           "Priya Sharma",
        "phone":          "+91-9876501001",
        "email":          "priya.sharma@gmail.com",
        "area":           "Sector 4",
        "plan":           "100Mbps",
        "equipment":      "TP-Link ONT (SN: TL-4A2B9C)",
        "account_number": "NET-2021-04-0001",
        "address":        "House 12, Lane 3, Sector 4",
        "plan_expiry":    "2026-04-20",
        "plan_status":    "active",
        "monthly_rate":   999,
        "tickets": [
            {
                "id":          "TKT-001-A",
                "issue_type":  "ONT light blinking red",
                "date_opened": "2024-01-15",
                "description": "Customer called at 9 AM. ONT showing red LOS light. No internet for 2 hours.",
                "resolution":  "Remote ONT reboot via OLT portal. LOS cleared after 3-minute reboot cycle.",
                "status":      "resolved",
            },
            {
                "id":          "TKT-001-B",
                "issue_type":  "ONT light blinking red",
                "date_opened": "2024-02-03",
                "description": "Same red LOS issue. Second time this month. Customer frustrated.",
                "resolution":  "Remote ONT reboot again. Escalated to field team for fiber splice inspection at J2.",
                "status":      "resolved",
            },
            {
                "id":          "TKT-001-C",
                "issue_type":  "ONT light blinking red",
                "date_opened": "2024-03-11",
                "description": "Recurring red LOS. Field visit confirmed micro-bend in fiber at J2. Repaired.",
                "resolution":  "Physical fiber repair at junction J2, Sector 4. Root cause resolved.",
                "status":      "resolved",
            },
        ],
    },
    {
        "id":             "CUST002",
        "name":           "Deepika Rao",
        "phone":          "+91-9876501002",
        "email":          "deepika.rao@yahoo.com",
        "area":           "Sector 4",
        "plan":           "50Mbps",
        "equipment":      "Huawei ONT (SN: HW-2C4D8E)",
        "account_number": "NET-2020-04-0002",
        "address":        "Flat 3A, Sunrise Apartments, Sector 4",
        "plan_expiry":    "2026-04-05",
        "plan_status":    "active",
        "monthly_rate":   599,
        "tickets": [
            {
                "id":          "TKT-002-A",
                "issue_type":  "Intermittent disconnection",
                "date_opened": "2024-01-22",
                "description": "Drops every 20-30 minutes, auto-reconnects. Started this week.",
                "resolution":  "Found flapping SFP module on OLT. Replaced. Drops stopped.",
                "status":      "resolved",
            },
            {
                "id":          "TKT-002-B",
                "issue_type":  "No internet after power outage",
                "date_opened": "2024-02-14",
                "description": "Internet down after area power cut. ONT cycling through colors.",
                "resolution":  "ONT required hard reset — factory reset button + OLT re-registration.",
                "status":      "resolved",
            },
            {
                "id":          "TKT-002-C",
                "issue_type":  "Slow speed complaint",
                "date_opened": "2024-03-20",
                "description": "Getting 6 Mbps on 50 Mbps plan. Evenings only.",
                "resolution":  "OLT port oversubscription identified. Migrated to uncongested port.",
                "status":      "resolved",
            },
        ],
    },
]


# ── Historical network incidents (seeded into Hindsight NETWORK bank) ─────────

DEMO_INCIDENTS = [
    {
        "sector":      "Sector 4",
        "date":        "2024-01-20",
        "pattern":     "Multiple customers reporting ONT red LOS within a 2-hour window",
        "root_cause":  "Fiber junction box J2 was damaged by heavy rainfall. Water ingress caused LOS on 4 ONTs.",
        "resolution":  "Field team replaced junction enclosure and re-spliced 4 affected fibers. All services restored within 6 hours.",
    },
    {
        "sector":      "Sector 4",
        "date":        "2024-03-15",
        "pattern":     "Widespread intermittent disconnections in Sector 4 during evening peak",
        "root_cause":  "OLT card port group oversubscription during 7-10 PM peak. Card had 40 customers on a 1 Gbps uplink.",
        "resolution":  "Emergency load balancing: 20 customers migrated to spare OLT card. Upstream capacity doubled.",
    },
]


# ── Hindsight bank IDs ────────────────────────────────────────────────────────

CUSTOMER_BANK   = "netrecall-customers"
NETWORK_BANK    = "netrecall-network"
RESOLUTION_BANK = "netrecall-resolutions"


# ── Public seeding function ───────────────────────────────────────────────────

def seed_demo(
    db,
    hindsight_client,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> dict:
    """
    Seed demo customers into SQLite and Hindsight Cloud.

    Args:
        db:               CustomerDB instance
        hindsight_client: Hindsight client (or None to skip Hindsight seeding)
        progress_callback: optional callable(progress_0_to_1, message)

    Returns:
        {"customers": int, "tickets": int, "incidents": int, "errors": list[str]}
    """
    errors = []
    n_customers = 0
    n_tickets   = 0
    n_incidents = 0

    total_steps = (
        len(DEMO_CUSTOMERS) +
        sum(len(c["tickets"]) for c in DEMO_CUSTOMERS) +
        len(DEMO_INCIDENTS)
    )
    step = 0

    def _progress(msg: str) -> None:
        nonlocal step
        step += 1
        if progress_callback:
            progress_callback(step / total_steps, msg)

    # ── 1. Seed customers into SQLite ─────────────────────────────────────────
    for c in DEMO_CUSTOMERS:
        try:
            db.upsert_customer(
                customer_id=c["id"],
                name=c["name"],
                phone=c["phone"],
                email=c["email"],
                area=c["area"],
                plan=c["plan"],
                equipment=c["equipment"],
                account_number=c["account_number"],
                address=c["address"],
                plan_expiry=c.get("plan_expiry", ""),
                plan_status=c.get("plan_status", "active"),
                monthly_rate=c.get("monthly_rate", 0),
            )
            n_customers += 1
            _progress(f"Customer: {c['name']}")
        except Exception as e:
            errors.append(f"Customer {c['id']}: {e}")
            _progress(f"Customer {c['name']} (error)")

    # ── 2. Seed tickets into SQLite ───────────────────────────────────────────
    for c in DEMO_CUSTOMERS:
        for t in c["tickets"]:
            try:
                db.upsert_ticket(
                    ticket_id=t["id"],
                    customer_id=c["id"],
                    issue_type=t["issue_type"],
                    description=t["description"],
                    resolution=t["resolution"],
                    status=t["status"],
                    date_opened=t["date_opened"],
                )
                n_tickets += 1
                _progress(f"Ticket: {t['id']}")
            except Exception as e:
                errors.append(f"Ticket {t['id']}: {e}")
                _progress(f"Ticket {t['id']} (error)")

    # ── 3. Seed into Hindsight Cloud (optional) ───────────────────────────────
    if hindsight_client:
        # Customer profiles + tickets → CUSTOMER_BANK
        for c in DEMO_CUSTOMERS:
            cid_tag     = f"customer:{c['id']}"
            sector_tag  = f"sector:{c['area'].lower().replace(' ', '-')}"

            # Customer profile
            try:
                profile_content = (
                    f"{c['name']} is a customer with account {c['account_number']} "
                    f"and ID {c['id']}. | Involving: {c['name']}\n"
                    f"Area: {c['area']}, Plan: {c['plan']}, Equipment: {c['equipment']}, "
                    f"Phone: {c['phone']}, Address: {c['address']}"
                )
                hindsight_client.retain(
                    bank_id=CUSTOMER_BANK,
                    content=profile_content,
                    context="customer-profile",
                    tags=[cid_tag, sector_tag],
                    document_id=f"profile-{c['id']}",
                )
            except Exception as e:
                errors.append(f"Hindsight profile {c['id']}: {e}")

            # Tickets
            for t in c["tickets"]:
                try:
                    ticket_content = (
                        f"Support ticket {t['id']} for {c['name']} ({c['id']}) "
                        f"on {t['date_opened']}:\n"
                        f"Issue: {t['issue_type']}\n"
                        f"Description: {t['description']}\n"
                        f"Resolution: {t['resolution']}\n"
                        f"Status: {t['status']}"
                    )
                    hindsight_client.retain(
                        bank_id=CUSTOMER_BANK,
                        content=ticket_content,
                        context="support-ticket",
                        tags=[cid_tag, sector_tag,
                              f"issue:{t['issue_type'].lower().replace(' ', '-')}"],
                        document_id=f"{t['id']}",
                    )
                    # Also seed into resolution bank
                    if t["status"] == "resolved" and t["resolution"]:
                        hindsight_client.retain(
                            bank_id=RESOLUTION_BANK,
                            content=(
                                f"Issue: {t['issue_type']}\n"
                                f"Equipment: {c['equipment']}\n"
                                f"Area: {c['area']}\n"
                                f"Resolution: {t['resolution']}"
                            ),
                            context="resolution-knowledge",
                            tags=[f"issue:{t['issue_type'].lower().replace(' ', '-')}",
                                  sector_tag],
                            document_id=f"res-{t['id']}",
                        )
                except Exception as e:
                    errors.append(f"Hindsight ticket {t['id']}: {e}")

        # Area incidents → NETWORK_BANK
        for inc in DEMO_INCIDENTS:
            n_incidents += 1
            try:
                sector_tag = f"sector:{inc['sector'].lower().replace(' ', '-')}"
                content = (
                    f"Historical network incident in {inc['sector']} on {inc['date']}:\n"
                    f"Pattern: {inc['pattern']}\n"
                    f"Root cause: {inc['root_cause']}\n"
                    f"Resolution: {inc['resolution']}"
                )
                hindsight_client.retain(
                    bank_id=NETWORK_BANK,
                    content=content,
                    context="historical-incident",
                    tags=[sector_tag, "historical-incident"],
                    document_id=f"inc-{inc['sector'].replace(' ', '-')}-{inc['date']}",
                )
                _progress(f"Incident: {inc['sector']} {inc['date']}")
            except Exception as e:
                errors.append(f"Incident {inc['sector']}: {e}")
                _progress(f"Incident {inc['sector']} (error)")

    return {
        "customers": n_customers,
        "tickets":   n_tickets,
        "incidents": n_incidents,
        "errors":    errors,
    }
