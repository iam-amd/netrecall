"""
dashboard.py — NetRecall Network Intelligence Dashboard.

Reads from live CustomerDB (SQLite) — no hardcoded data.
When the database is empty, renders an "empty state" automatically.
When data exists, renders real metrics, real customers, real patterns.
"""

from __future__ import annotations
import streamlit as st
from resolution_engine import ResolutionEngine
from network_patterns import PatternDetector

SECTORS = [f"Sector {i}" for i in range(1, 9)]


def render_dashboard(
    db,
    resolution_engine: ResolutionEngine,
    pattern_detector: PatternDetector,
    active_customers: set,
    last_alerts: dict,
) -> None:
    """Top-level render entry point. Call from inside a Streamlit tab."""
    try:
        customer_count = db.get_customer_count()
    except Exception:
        customer_count = 0

    if customer_count == 0:
        _empty_state()
        return

    _render_metrics_row(db, resolution_engine)
    st.markdown("---")
    _render_sector_and_risk(db, resolution_engine, active_customers, last_alerts)
    st.markdown("---")
    _render_knowledge_and_alerts(resolution_engine, last_alerts)


# ── Sections ──────────────────────────────────────────────────────────────────

def _render_metrics_row(db, re: ResolutionEngine) -> None:
    db_stats = db.get_stats()
    kb       = re.get_knowledge_stats()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Customers",          db_stats["total_customers"],
              help="Customers with records in system")
    m2.metric("Support Calls",      db_stats["total_calls"],
              help="Total calls logged and analyzed")
    m3.metric("Tickets Logged",     db_stats["total_tickets"],
              help="Individual support tickets on record")
    m4.metric("Issue Types Known",  kb["total_issue_types"],
              help="Distinct problem categories with resolution data")
    m5.metric("Memory Banks",       "3",
              help="Customer · Network · Resolution banks in Hindsight Cloud")


def _render_sector_and_risk(
    db,
    re: ResolutionEngine,
    active_customers: set,
    last_alerts: dict,
) -> None:
    col_map, col_risk = st.columns([3, 2], gap="large")

    # ── Sector Map ────────────────────────────────────────────────────────────
    with col_map:
        st.markdown("#### 🗺️ Live Sector Health Map")

        # Count active tickets per sector from DB
        sector_counts: dict[str, int]         = {s: 0 for s in SECTORS}
        sector_customers: dict[str, list[str]] = {s: [] for s in SECTORS}

        try:
            all_customers = db.get_all_customers()
            for c in all_customers:
                if c["id"] in active_customers:
                    sector = c.get("area", "")
                    if sector in sector_counts:
                        sector_counts[sector] += 1
                        sector_customers[sector].append(c["name"].split()[0])
        except Exception:
            pass

        # Also count recent calls per sector (last 24h)
        try:
            sector_activity = db.get_sector_activity()
            for sector, count in sector_activity.items():
                if sector in sector_counts:
                    sector_counts[sector] = max(sector_counts[sector], count)
        except Exception:
            pass

        alerted: set[str] = set()
        for alert in last_alerts.values():
            if alert:
                alerted.add(alert["sector"])

        for row in [SECTORS[:4], SECTORS[4:]]:
            cols = st.columns(4)
            for col, sector in zip(cols, row):
                count    = sector_counts[sector]
                is_alert = sector in alerted

                if is_alert or count >= 2:
                    bg, border, icon, label = "#3b0808", "#ef4444", "🔴", "ALERT"
                elif count == 1:
                    bg, border, icon, label = "#2d1a00", "#f97316", "🟠", "ACTIVE"
                else:
                    bg, border, icon, label = "#052e16", "#22c55e", "🟢", "CLEAR"

                names_str = (
                    "<br><span style='color:#fca5a5;font-size:0.65rem;'>"
                    + ", ".join(sector_customers[sector][:2])
                    + ("…" if len(sector_customers[sector]) > 2 else "")
                    + "</span>"
                ) if sector_customers[sector] else ""

                col.markdown(
                    f"""<div style="background:{bg};border:1px solid {border};border-radius:10px;
padding:12px 6px;text-align:center;margin:3px 0;min-height:90px;">
<div style="font-size:1.4rem;">{icon}</div>
<div style="color:#f1f5f9;font-weight:700;font-size:0.8rem;margin:2px 0;">{sector}</div>
<div style="color:#94a3b8;font-size:0.68rem;">{label}</div>
{names_str}
</div>""",
                    unsafe_allow_html=True,
                )

        st.markdown(
            "<div style='color:#64748b;font-size:0.72rem;margin-top:6px;'>"
            "🟢 Clear &nbsp;|&nbsp; 🟠 Active — 1 ticket &nbsp;|&nbsp; "
            "🔴 Alert — 2+ tickets (area pattern suspected)"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Customer Risk Leaderboard ─────────────────────────────────────────────
    with col_risk:
        st.markdown("#### 🚨 Customer Risk Leaderboard")
        st.caption("Sorted by frustration score. Proactively reach out to red customers.")

        try:
            all_customers = db.get_all_customers()
        except Exception:
            all_customers = []

        scored = []
        for c in all_customers:
            fs = re.compute_frustration_score(c)
            scored.append((c, fs))
        scored.sort(key=lambda x: -x[1]["score"])

        for c, fs in scored[:8]:
            is_active   = c["id"] in active_customers
            active_dot  = " ●" if is_active else ""
            drivers_str = " · ".join(fs["drivers"][:2])
            bar_pct     = int(fs["score"] * 10)

            st.markdown(
                f"""<div style="background:#0f172a;border:1px solid #1e3a5f;
border-radius:8px;padding:9px 12px;margin:4px 0;">
<div style="display:flex;justify-content:space-between;align-items:center;">
  <span style="color:#e2e8f0;font-weight:600;font-size:0.83rem;">
    {fs['badge']} {c['name']}{active_dot}
  </span>
  <span style="color:{fs['color']};font-weight:700;font-size:0.9rem;">
    {fs['score']}/10
  </span>
</div>
<div style="background:#1e293b;border-radius:3px;height:4px;margin:5px 0;">
  <div style="background:{fs['color']};width:{bar_pct}%;height:4px;border-radius:3px;"></div>
</div>
<div style="color:#64748b;font-size:0.7rem;">{c.get('area','–')} · {drivers_str}</div>
</div>""",
                unsafe_allow_html=True,
            )


def _render_knowledge_and_alerts(re: ResolutionEngine, last_alerts: dict) -> None:
    col_kb, col_alerts = st.columns([3, 2], gap="large")

    # ── Resolution Knowledge Base ─────────────────────────────────────────────
    with col_kb:
        st.markdown("#### 📚 Resolution Knowledge Base")
        st.caption(
            "Every resolved ticket strengthens confidence. "
            "The system learns which fixes work for which equipment in which area."
        )
        kb = re.get_knowledge_stats()
        total_cases = kb["total_resolutions"]

        if total_cases == 0:
            st.markdown(
                """<div style="background:#0f172a;border:1px dashed #334155;border-radius:10px;
padding:20px;text-align:center;color:#64748b;font-size:0.82rem;">
No resolution data yet.<br>Complete calls to build the knowledge base.
</div>""",
                unsafe_allow_html=True,
            )
        else:
            for issue_type, count in kb["top_issues"]:
                conf    = re.compute_confidence(issue_type)
                pct     = int((count / max(1, total_cases)) * 100)
                bar_w   = max(4, pct * 3)
                preview = conf["primary_fix"][:90] + "…" if len(conf["primary_fix"]) > 90 else conf["primary_fix"]
                col     = "#22c55e" if conf["confidence"] >= 80 else "#f97316" if conf["confidence"] >= 60 else "#94a3b8"

                st.markdown(
                    f"""<div style="background:#0f172a;border:1px solid #1e3a5f;
border-radius:8px;padding:11px 14px;margin:6px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
    <span style="color:#e2e8f0;font-weight:600;font-size:0.85rem;">{issue_type}</span>
    <span style="color:{col};font-weight:700;font-size:0.82rem;">{conf['confidence']}% · {count} cases</span>
  </div>
  <div style="background:#1e293b;border-radius:4px;height:5px;margin-bottom:6px;">
    <div style="background:{col};width:{min(100,bar_w)}%;height:5px;border-radius:4px;"></div>
  </div>
  <div style="color:#64748b;font-size:0.72rem;">Primary fix: {preview}</div>
</div>""",
                    unsafe_allow_html=True,
                )

    # ── Alerts ────────────────────────────────────────────────────────────────
    with col_alerts:
        st.markdown("#### ⚠️ Active Pattern Alerts")

        active_alerts = {
            a["sector"]: a
            for a in last_alerts.values()
            if a
        }

        if not active_alerts:
            st.markdown(
                """<div style="background:#0f172a;border:1px dashed #334155;border-radius:10px;
padding:28px;text-align:center;color:#64748b;font-size:0.82rem;">
All sectors nominal.<br>No area-wide patterns detected.
</div>""",
                unsafe_allow_html=True,
            )
        else:
            for sector, alert in active_alerts.items():
                affected = ", ".join(alert["affected_customers"][:3])
                issues   = "; ".join(list(set(alert["issues"]))[:2])
                hist     = alert.get("historical_match", "") or ""
                hist_preview = (hist[:120] + "…") if len(hist) > 120 else (hist or "No prior match found.")

                st.markdown(
                    f"""<div style="background:#3b0808;border:1px solid #ef4444;
border-radius:10px;padding:12px;margin:6px 0;">
  <div style="color:#fca5a5;font-weight:800;font-size:0.88rem;">⚠️ {sector}</div>
  <div style="color:#ffedd5;font-size:0.78rem;margin-top:5px;">
    <b>{alert['ticket_count']} tickets</b> in {alert['window_minutes']} min<br>
    Customers: {affected}<br>Issues: {issues}
  </div>
  <div style="color:#fed7aa;font-size:0.72rem;margin-top:6px;
  border-top:1px solid #7c2d12;padding-top:6px;">
    <b>Historical match:</b> {hist_preview}
  </div>
</div>""",
                    unsafe_allow_html=True,
                )

        # Memory growth panel
        st.markdown("#### 📈 System Intelligence")
        try:
            db_stats = re._db.get_stats() if re._db else {}
            kb_stats = re.get_knowledge_stats()

            rows = [
                ("Customers in System",  str(db_stats.get("total_customers", 0)), ""),
                ("Calls Analyzed",       str(db_stats.get("total_calls", 0)), ""),
                ("Issue Types Known",    str(kb_stats.get("total_issue_types", 0)), ""),
                ("Avg Call Duration",
                 f"{db_stats.get('avg_duration_sec', 0) // 60}m {db_stats.get('avg_duration_sec', 0) % 60:02d}s", ""),
            ]
            st.markdown(
                """<div style="background:#0f172a;border:1px solid #1e3a5f;
border-radius:8px;padding:14px;">""",
                unsafe_allow_html=True,
            )
            for label, value, delta in rows:
                st.markdown(
                    f"""<div style="display:flex;justify-content:space-between;
align-items:center;padding:5px 0;border-bottom:1px solid #1e293b;">
<span style="color:#94a3b8;font-size:0.78rem;">{label}</span>
<b style="color:#e2e8f0;font-size:0.85rem;">{value}</b>
</div>""",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)
        except Exception:
            pass


# ── Empty state ───────────────────────────────────────────────────────────────

def _empty_state() -> None:
    st.markdown(
        """<div style="background:#0a0f1e;border:1px dashed #334155;border-radius:14px;
padding:40px 32px;text-align:center;margin:20px 0;">
<div style="font-size:2.8rem;margin-bottom:14px;">🌑</div>
<div style="color:#94a3b8;font-weight:700;font-size:1.1rem;">System Empty — Day 1</div>
<div style="color:#64748b;font-size:0.84rem;margin-top:10px;line-height:1.8;">
  No customers in memory.<br>
  No resolutions indexed.<br>
  No patterns to detect.<br><br>
  <b style="color:#38bdf8;">Start taking calls</b> to build institutional knowledge.<br>
  Use <b>Load Demo Data</b> to see a 2-customer demo scenario.
</div>
</div>""",
        unsafe_allow_html=True,
    )

    st.markdown("#### 🗺️ Sector Map — Awaiting Data")
    for row in [SECTORS[:4], SECTORS[4:]]:
        cols = st.columns(4)
        for col, sector in zip(cols, row):
            col.markdown(
                f"""<div style="background:#1e293b;border:1px solid #334155;
border-radius:10px;padding:12px 6px;text-align:center;min-height:90px;">
<div style="font-size:1.4rem;">⬜</div>
<div style="color:#475569;font-size:0.8rem;">{sector}</div>
<div style="color:#334155;font-size:0.68rem;">NO DATA</div>
</div>""",
                unsafe_allow_html=True,
            )
