"""
seed_data.py — Populate Hindsight memory banks with realistic ISP customer data.

Run standalone:  python seed_data.py
Or call seed_all() from within the Streamlit app.
"""

from __future__ import annotations
import os
import sys
from datetime import datetime
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Customer + ticket corpus
# ──────────────────────────────────────────────────────────────────────────────

CUSTOMERS: list[dict] = [
    {
        "id": "CUST001",
        "name": "Priya Sharma",
        "phone": "+91-9876501001",
        "email": "priya.sharma@gmail.com",
        "area": "Sector 4",
        "plan": "100Mbps",
        "equipment": "TP-Link ONT (SN: TL-4A2B9C)",
        "account_number": "NET-2021-04-0001",
        "address": "House 12, Lane 3, Sector 4",
        "plan_expiry": "2026-04-20",
        "plan_status": "active",
        "monthly_rate": 999,
        "tickets": [
            {
                "id": "TKT-001-A",
                "type": "ONT light blinking red",
                "date": "2024-01-15",
                "description": "Customer called at 9 AM. ONT showing red LOS light. No internet for 2 hours.",
                "resolution": "Remote ONT reboot via OLT portal. LOS cleared after 3-minute reboot cycle. Service restored.",
                "status": "resolved",
            },
            {
                "id": "TKT-001-B",
                "type": "ONT light blinking red",
                "date": "2024-02-03",
                "description": "Same red LOS issue. Third time this month. Customer frustrated.",
                "resolution": "Remote ONT reboot again. Escalated to field team to inspect fiber splice at junction box Sector 4-J2.",
                "status": "resolved",
            },
            {
                "id": "TKT-001-C",
                "type": "ONT light blinking red",
                "date": "2024-03-11",
                "description": "Recurring red LOS. Field visit confirmed micro-bend in fiber at J2. Repaired.",
                "resolution": "Physical fiber repair at junction J2, Sector 4. Issue root-caused and resolved permanently.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST002",
        "name": "Rahul Verma",
        "phone": "+91-9876501002",
        "email": "rahul.verma@yahoo.com",
        "area": "Sector 2",
        "plan": "50Mbps",
        "equipment": "Huawei ONT (SN: HW-2C4D8E)",
        "account_number": "NET-2020-02-0002",
        "address": "Flat 5B, Green Apartments, Sector 2",
        "plan_expiry": "2026-03-15",
        "plan_status": "suspended",
        "monthly_rate": 599,
        "tickets": [
            {
                "id": "TKT-002-A",
                "type": "Slow speed complaint",
                "date": "2024-01-22",
                "description": "Customer getting 8 Mbps on 50 Mbps plan. Evening hours, 7-10 PM.",
                "resolution": "Found port oversubscription on OLT card. Migrated to uncongested port. Speeds normalized.",
                "status": "resolved",
            },
            {
                "id": "TKT-002-B",
                "type": "Intermittent disconnection",
                "date": "2024-02-14",
                "description": "Drops every 20-30 minutes, auto-reconnects. Happening during work hours.",
                "resolution": "Faulty SFP module on OLT replaced. Drops stopped after replacement.",
                "status": "resolved",
            },
            {
                "id": "TKT-002-C",
                "type": "DNS resolution failures",
                "date": "2024-03-28",
                "description": "Customer cannot open websites but ping to IP addresses works. DNS issue suspected.",
                "resolution": "Pushed DNS server update via DHCP. Flushed customer DNS cache remotely. Resolved.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST003",
        "name": "Anjali Patel",
        "phone": "+91-9876501003",
        "email": "anjali.patel@hotmail.com",
        "area": "Sector 6",
        "plan": "200Mbps",
        "equipment": "MikroTik RouterBOARD (SN: MT-6F1E2A)",
        "account_number": "NET-2022-06-0003",
        "address": "Villa 7, Palm Colony, Sector 6",
        "plan_expiry": "2026-05-30",
        "plan_status": "active",
        "monthly_rate": 1999,
        "tickets": [
            {
                "id": "TKT-003-A",
                "type": "WiFi not reaching certain rooms",
                "date": "2024-01-10",
                "description": "Strong signal in living room, dead zones in bedrooms and kitchen. 3-floor bungalow.",
                "resolution": "Advised to use MikroTik as wired backbone with two additional access points. Customer implemented and confirmed fix.",
                "status": "resolved",
            },
            {
                "id": "TKT-003-B",
                "type": "No internet after power outage",
                "date": "2024-02-08",
                "description": "Power cut in Sector 6 at night. After power restored, internet not working.",
                "resolution": "MikroTik config corrupted on unclean shutdown. Remote config push restored settings.",
                "status": "resolved",
            },
            {
                "id": "TKT-003-C",
                "type": "Slow speed complaint",
                "date": "2024-04-01",
                "description": "Getting 80 Mbps on 200 Mbps plan consistently. No time pattern.",
                "resolution": "Found policing rule misconfigured to 80 Mbps cap. Fixed on OLT profile. Now getting 195-198 Mbps.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST004",
        "name": "Vikram Singh",
        "phone": "+91-9876501004",
        "email": "vikram.singh@gmail.com",
        "area": "Sector 1",
        "plan": "100Mbps",
        "equipment": "TP-Link ONT (SN: TL-1B3C7D)",
        "account_number": "NET-2021-01-0004",
        "address": "Block A, Sector 1 Heights",
        "plan_expiry": "2026-04-14",
        "plan_status": "active",
        "monthly_rate": 999,
        "tickets": [
            {
                "id": "TKT-004-A",
                "type": "IP conflict issues",
                "date": "2024-01-30",
                "description": "Customer getting IP conflict errors on multiple devices. Started after neighbor moved in.",
                "resolution": "Assigned static IP outside DHCP pool range. Conflict resolved.",
                "status": "resolved",
            },
            {
                "id": "TKT-004-B",
                "type": "Intermittent disconnection",
                "date": "2024-02-20",
                "description": "Connection drops once or twice daily, mostly late night.",
                "resolution": "Scheduled maintenance in Sector 1 was causing brief disruptions. Informed customer.",
                "status": "resolved",
            },
            {
                "id": "TKT-004-C",
                "type": "Slow speed complaint",
                "date": "2024-03-15",
                "description": "Speeds fine on laptop but slow on smart TV. Getting 12 Mbps on TV.",
                "resolution": "TV using 2.4 GHz band with congestion. Advised 5 GHz band. Speeds improved to 85 Mbps.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST005",
        "name": "Sneha Gupta",
        "phone": "+91-9876501005",
        "email": "sneha.gupta@rediffmail.com",
        "area": "Sector 3",
        "plan": "50Mbps",
        "equipment": "Huawei ONT (SN: HW-3A5B0C)",
        "account_number": "NET-2020-03-0005",
        "address": "House 22, Shivaji Nagar, Sector 3",
        "plan_expiry": "2026-06-15",
        "plan_status": "active",
        "monthly_rate": 599,
        "tickets": [
            {
                "id": "TKT-005-A",
                "type": "No internet after power outage",
                "date": "2024-01-25",
                "description": "Power cut, ONT not coming online after power restored. ONT lights cycling.",
                "resolution": "ONT was in factory reset state. Remotely provisioned via OLT OMCI. Service restored.",
                "status": "resolved",
            },
            {
                "id": "TKT-005-B",
                "type": "DNS resolution failures",
                "date": "2024-03-02",
                "description": "Can access websites by IP but domain names fail. Affecting all devices.",
                "resolution": "ISP DNS servers were under attack. Temporarily pointed to Cloudflare 1.1.1.1 via DHCP push.",
                "status": "resolved",
            },
            {
                "id": "TKT-005-C",
                "type": "Slow speed complaint",
                "date": "2024-04-10",
                "description": "Evening speed drops from 48 Mbps to under 5 Mbps between 8-11 PM.",
                "resolution": "Port congestion issue. Moved to high-capacity port on OLT. Evening speeds now 44-47 Mbps.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST006",
        "name": "Arjun Nair",
        "phone": "+91-9876501006",
        "email": "arjun.nair@gmail.com",
        "area": "Sector 7",
        "plan": "200Mbps",
        "equipment": "MikroTik hAP ac3 (SN: MT-7D2F6B)",
        "account_number": "NET-2022-07-0006",
        "address": "Tower C, Flat 1402, Sector 7",
        "plan_expiry": "2026-05-10",
        "plan_status": "active",
        "monthly_rate": 1999,
        "tickets": [
            {
                "id": "TKT-006-A",
                "type": "Intermittent disconnection",
                "date": "2024-01-18",
                "description": "High-rise apartment, fiber entry point at basement. Drops correlate with lift usage.",
                "resolution": "Lift motor causing EMI on fiber splice. Added proper shielding at basement splice box.",
                "status": "resolved",
            },
            {
                "id": "TKT-006-B",
                "type": "ONT light blinking red",
                "date": "2024-02-25",
                "description": "Red LOS light on MikroTik SFP module. Loss of signal.",
                "resolution": "SFP transceiver in MikroTik was failing. Replaced SFP. Service restored.",
                "status": "resolved",
            },
            {
                "id": "TKT-006-C",
                "type": "IP conflict issues",
                "date": "2024-03-20",
                "description": "Getting 169.254.x.x APIPA address occasionally. DHCP lease issues.",
                "resolution": "DHCP pool exhaustion on segment. Expanded DHCP pool and reduced lease time.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST007",
        "name": "Deepika Rao",
        "phone": "+91-9876501007",
        "email": "deepika.rao@gmail.com",
        "area": "Sector 4",
        "plan": "100Mbps",
        "equipment": "TP-Link ONT (SN: TL-4C7D1E)",
        "account_number": "NET-2021-04-0007",
        "address": "Plot 45, Gandhi Road, Sector 4",
        "plan_expiry": "2026-04-08",
        "plan_status": "active",
        "monthly_rate": 999,
        "tickets": [
            {
                "id": "TKT-007-A",
                "type": "ONT light blinking red",
                "date": "2024-01-20",
                "description": "Red LOS light. Sector 4 junction issue affecting multiple customers.",
                "resolution": "Area-wide: J2 junction box damaged in rainfall. Field team replaced junction enclosure.",
                "status": "resolved",
            },
            {
                "id": "TKT-007-B",
                "type": "Slow speed complaint",
                "date": "2024-02-28",
                "description": "Getting 30 Mbps on 100 Mbps plan. Started after apartment block added more units.",
                "resolution": "OLT port was oversubscribed. Reconfigured uplink and balanced load.",
                "status": "resolved",
            },
            {
                "id": "TKT-007-C",
                "type": "WiFi not reaching certain rooms",
                "date": "2024-03-25",
                "description": "Dead zone in study room at far end of apartment.",
                "resolution": "Recommended powerline adapter + access point. Customer confirmed 80 Mbps in study.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST008",
        "name": "Kiran Mehta",
        "phone": "+91-9876501008",
        "email": "kiran.mehta@outlook.com",
        "area": "Sector 5",
        "plan": "50Mbps",
        "equipment": "Huawei EG8141A5 ONT (SN: HW-5E8F3A)",
        "account_number": "NET-2020-05-0008",
        "address": "Shop No 3, Commercial Complex, Sector 5",
        "plan_expiry": "2026-04-30",
        "plan_status": "active",
        "monthly_rate": 599,
        "tickets": [
            {
                "id": "TKT-008-A",
                "type": "DNS resolution failures",
                "date": "2024-01-08",
                "description": "Business customer. E-commerce site not loading. Other sites fine.",
                "resolution": "Specific DNS entry was cached incorrectly. Cleared cache and updated resolver.",
                "status": "resolved",
            },
            {
                "id": "TKT-008-B",
                "type": "No internet after power outage",
                "date": "2024-02-15",
                "description": "Power cut in commercial area. UPS kept systems up but internet died.",
                "resolution": "OLT port had hung. Soft reset from NOC. Service restored without field visit.",
                "status": "resolved",
            },
            {
                "id": "TKT-008-C",
                "type": "Intermittent disconnection",
                "date": "2024-04-05",
                "description": "Drops every night between 11 PM and midnight. Very consistent timing.",
                "resolution": "NOC scheduled backup causing brief link resets. Moved backup window to 3 AM.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST009",
        "name": "Suresh Pillai",
        "phone": "+91-9876501009",
        "email": "suresh.pillai@gmail.com",
        "area": "Sector 2",
        "plan": "200Mbps",
        "equipment": "MikroTik CCR1009 (SN: MT-2H4K9L)",
        "account_number": "NET-2022-02-0009",
        "address": "Tech Hub, Block B, Sector 2",
        "plan_expiry": "2026-05-20",
        "plan_status": "active",
        "monthly_rate": 1999,
        "tickets": [
            {
                "id": "TKT-009-A",
                "type": "Slow speed complaint",
                "date": "2024-01-12",
                "description": "Speeds inconsistent. Sometimes 180 Mbps, sometimes 40 Mbps. No pattern.",
                "resolution": "Fiber connector at customer premises had dust contamination. Cleaned and re-polished.",
                "status": "resolved",
            },
            {
                "id": "TKT-009-B",
                "type": "IP conflict issues",
                "date": "2024-02-18",
                "description": "Multiple public IPs conflicting. Customer runs small server farm.",
                "resolution": "Mis-announced routes in BGP peering. Updated route map. Conflicts resolved.",
                "status": "resolved",
            },
            {
                "id": "TKT-009-C",
                "type": "ONT light blinking red",
                "date": "2024-03-30",
                "description": "SFP on MikroTik showing RX power drop. Intermittent red signal.",
                "resolution": "Fiber splice at sector distribution box was failing. Re-spliced. RX power stable now.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST010",
        "name": "Pooja Iyer",
        "phone": "+91-9876501010",
        "email": "pooja.iyer@gmail.com",
        "area": "Sector 8",
        "plan": "100Mbps",
        "equipment": "TP-Link ONT (SN: TL-8G2H5K)",
        "account_number": "NET-2021-08-0010",
        "address": "42, Lake View Road, Sector 8",
        "plan_expiry": "2026-06-01",
        "plan_status": "active",
        "monthly_rate": 999,
        "tickets": [
            {
                "id": "TKT-010-A",
                "type": "WiFi not reaching certain rooms",
                "date": "2024-01-05",
                "description": "Large 4BHK. ONT in one corner, bedrooms on opposite side. Weak signal.",
                "resolution": "Set up mesh WiFi using ONT + 2 TP-Link Deco units. Full coverage confirmed.",
                "status": "resolved",
            },
            {
                "id": "TKT-010-B",
                "type": "Intermittent disconnection",
                "date": "2024-02-22",
                "description": "Connection dropping whenever microwave runs. Classic 2.4 GHz interference.",
                "resolution": "Switched all devices to 5 GHz. Microwave-correlated drops completely stopped.",
                "status": "resolved",
            },
            {
                "id": "TKT-010-C",
                "type": "No internet after power outage",
                "date": "2024-04-02",
                "description": "ONT not recovering after outage. Stuck in initialization loop.",
                "resolution": "ONT firmware had a bug with unclean shutdown. Factory reset + reprovisioned. Fixed.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST011",
        "name": "Amit Kumar",
        "phone": "+91-9876501011",
        "email": "amit.kumar99@gmail.com",
        "area": "Sector 3",
        "plan": "50Mbps",
        "equipment": "Huawei ONT (SN: HW-3B7C2D)",
        "account_number": "NET-2020-03-0011",
        "address": "Row House 8, Patel Colony, Sector 3",
        "plan_expiry": "2026-04-10",
        "plan_status": "suspended",
        "monthly_rate": 599,
        "tickets": [
            {
                "id": "TKT-011-A",
                "type": "ONT light blinking red",
                "date": "2024-01-28",
                "description": "Red LOS after heavy rain. Sector 3 area affected.",
                "resolution": "Water ingress at outdoor splice enclosure. Sealed and re-spliced. All customers restored.",
                "status": "resolved",
            },
            {
                "id": "TKT-011-B",
                "type": "DNS resolution failures",
                "date": "2024-02-10",
                "description": "Student, online exam platform not loading. Exam in 30 minutes.",
                "resolution": "Escalated to priority. DNS cache cleared, switched to backup DNS. Platform loaded.",
                "status": "resolved",
            },
            {
                "id": "TKT-011-C",
                "type": "Slow speed complaint",
                "date": "2024-03-22",
                "description": "Only getting 10 Mbps after plan upgrade to 50 Mbps.",
                "resolution": "Plan upgrade not applied to OLT speed profile. Updated profile. Now getting 48 Mbps.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST012",
        "name": "Divya Sharma",
        "phone": "+91-9876501012",
        "email": "divya.sharma@gmail.com",
        "area": "Sector 6",
        "plan": "200Mbps",
        "equipment": "MikroTik RB4011 (SN: MT-6B3E8F)",
        "account_number": "NET-2022-06-0012",
        "address": "Bungalow 3, Rose Garden, Sector 6",
        "plan_expiry": "2026-07-15",
        "plan_status": "active",
        "monthly_rate": 1999,
        "tickets": [
            {
                "id": "TKT-012-A",
                "type": "No internet after power outage",
                "date": "2024-01-16",
                "description": "Sector 6 power grid failure for 4 hours. MikroTik config lost.",
                "resolution": "Pushed backed-up config via remote access. Service restored in 10 minutes.",
                "status": "resolved",
            },
            {
                "id": "TKT-012-B",
                "type": "Intermittent disconnection",
                "date": "2024-02-05",
                "description": "Drops during peak hours (6-9 PM). Work from home, very disruptive.",
                "resolution": "Sector 6 OLT was congested. Added new uplink card. Peak hours now stable.",
                "status": "resolved",
            },
            {
                "id": "TKT-012-C",
                "type": "IP conflict issues",
                "date": "2024-04-08",
                "description": "Two devices showing same IP. One is a smart home hub.",
                "resolution": "Smart home hub had a static IP set that clashed with DHCP range. Adjusted DHCP start.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST013",
        "name": "Ravi Krishnan",
        "phone": "+91-9876501013",
        "email": "ravi.krishnan@gmail.com",
        "area": "Sector 1",
        "plan": "100Mbps",
        "equipment": "TP-Link ONT (SN: TL-1D5E2F)",
        "account_number": "NET-2021-01-0013",
        "address": "Flat 304, Sunrise Towers, Sector 1",
        "plan_expiry": "2026-04-17",
        "plan_status": "active",
        "monthly_rate": 999,
        "tickets": [
            {
                "id": "TKT-013-A",
                "type": "Slow speed complaint",
                "date": "2024-01-09",
                "description": "Speed test shows 10 Mbps download but 95 Mbps upload. Reversed somehow.",
                "resolution": "TX/RX fiber strands swapped at junction. Corrected polarity at J1. Now 96 Mbps down.",
                "status": "resolved",
            },
            {
                "id": "TKT-013-B",
                "type": "WiFi not reaching certain rooms",
                "date": "2024-02-12",
                "description": "Thick concrete walls in old building. Signal drops to 1 bar in far rooms.",
                "resolution": "Installed two access points connected via Ethernet over existing building wiring.",
                "status": "resolved",
            },
            {
                "id": "TKT-013-C",
                "type": "Intermittent disconnection",
                "date": "2024-03-18",
                "description": "Brief disconnections 3-4 times a day. Customer tracks outages in a spreadsheet.",
                "resolution": "Tracked to loose connector at patch panel in Sector 1 distribution room. Re-crimped.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST014",
        "name": "Meera Desai",
        "phone": "+91-9876501014",
        "email": "meera.desai@yahoo.com",
        "area": "Sector 7",
        "plan": "50Mbps",
        "equipment": "Huawei ONT (SN: HW-7F3G1H)",
        "account_number": "NET-2020-07-0014",
        "address": "Building 11, 2nd Floor, Sector 7",
        "plan_expiry": "2026-04-28",
        "plan_status": "active",
        "monthly_rate": 599,
        "tickets": [
            {
                "id": "TKT-014-A",
                "type": "ONT light blinking red",
                "date": "2024-01-22",
                "description": "Red LOS. Same building as Arjun Nair. Possible shared fiber path.",
                "resolution": "Sector 7 riser cable had a damaged section. Repaired. Both customers restored.",
                "status": "resolved",
            },
            {
                "id": "TKT-014-B",
                "type": "No internet after power outage",
                "date": "2024-02-28",
                "description": "Power restored but internet down. ONT showing amber light.",
                "resolution": "OLT GPON port needed soft reset after power fluctuation. Resolved remotely.",
                "status": "resolved",
            },
            {
                "id": "TKT-014-C",
                "type": "DNS resolution failures",
                "date": "2024-03-14",
                "description": "Office 365 and Teams not working. Other sites loading fine.",
                "resolution": "Microsoft DNS entries had stale cache on our resolver. Cleared cache, updated TTL handling.",
                "status": "resolved",
            },
        ],
    },
    {
        "id": "CUST015",
        "name": "Sanjay Bhat",
        "phone": "+91-9876501015",
        "email": "sanjay.bhat@gmail.com",
        "area": "Sector 5",
        "plan": "200Mbps",
        "equipment": "MikroTik CRS326 (SN: MT-5C6D4E)",
        "account_number": "NET-2022-05-0015",
        "address": "Office Park, Suite 201, Sector 5",
        "plan_expiry": "2026-05-31",
        "plan_status": "active",
        "monthly_rate": 1999,
        "tickets": [
            {
                "id": "TKT-015-A",
                "type": "Slow speed complaint",
                "date": "2024-01-20",
                "description": "Business customer. Getting 50 Mbps on 200 Mbps during business hours only.",
                "resolution": "QoS policy was incorrectly limiting daytime traffic. Removed incorrect policy.",
                "status": "resolved",
            },
            {
                "id": "TKT-015-B",
                "type": "IP conflict issues",
                "date": "2024-02-26",
                "description": "New CCTV system causing IP conflicts on office LAN.",
                "resolution": "CCTV NVR had hardcoded IPs clashing with DHCP. Isolated CCTV to separate VLAN.",
                "status": "resolved",
            },
            {
                "id": "TKT-015-C",
                "type": "Intermittent disconnection",
                "date": "2024-03-05",
                "description": "SLA-critical: financial services. Drops causing transaction failures.",
                "resolution": "Upgraded to dedicated fiber path. SLA upgraded to 99.9% uptime with monitoring.",
                "status": "resolved",
            },
        ],
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Historical area-wide incidents (for network pattern memory)
# ──────────────────────────────────────────────────────────────────────────────

HISTORICAL_NETWORK_INCIDENTS: list[dict] = [
    {
        "sector": "Sector 4",
        "date": "2024-01-20",
        "pattern": "3 customers reported ONT red LOS within 1 hour",
        "root_cause": "Fiber junction box J2 damaged by rainfall. Water ingress caused signal loss.",
        "resolution": "Field team replaced junction enclosure and re-spliced affected fibers. All customers restored in 3 hours.",
        "tag": "sector-4",
    },
    {
        "sector": "Sector 3",
        "date": "2024-01-28",
        "pattern": "4 customers reported complete outage after heavy rain",
        "root_cause": "Outdoor splice enclosure at Sector 3 distribution point had water ingress.",
        "resolution": "Sealed enclosure, re-spliced 6 fiber pairs. Added waterproofing gel. Preventive: all outdoor enclosures in Sector 3 inspected.",
        "tag": "sector-3",
    },
    {
        "sector": "Sector 6",
        "date": "2024-01-16",
        "pattern": "Multiple customers offline after 4-hour power grid failure",
        "root_cause": "Extended power outage drained OLT UPS. MikroTik routers lost configs on unclean shutdown.",
        "resolution": "NOC pushed backed-up configs to all MikroTik units remotely. OLT restored on generator power.",
        "tag": "sector-6",
    },
    {
        "sector": "Sector 2",
        "date": "2024-02-14",
        "pattern": "2 customers with intermittent drops traced to OLT card",
        "root_cause": "Failing SFP module on OLT card causing packet loss and random disconnections.",
        "resolution": "Replaced SFP module on OLT. All affected ports now stable.",
        "tag": "sector-2",
    },
    {
        "sector": "Sector 7",
        "date": "2024-01-22",
        "pattern": "2 customers in same building with simultaneous ONT red LOS",
        "root_cause": "Riser cable in building had physical damage from construction work in basement.",
        "resolution": "New riser cable pulled through conduit. Both customers restored. Contractor notified.",
        "tag": "sector-7",
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Seeder functions
# ──────────────────────────────────────────────────────────────────────────────

CUSTOMER_BANK = "netrecall-customers"
NETWORK_BANK = "netrecall-network"
RESOLUTION_BANK = "netrecall-resolutions"


def _make_sector_tag(area: str) -> str:
    return f"sector:{area.lower().replace(' ', '-')}"


def seed_all(hindsight_client, progress_callback=None) -> dict:
    """
    Seed all customer profiles, tickets, and network incidents into Hindsight.
    Returns a summary dict with counts.
    """
    results = {"customers": 0, "tickets": 0, "network_incidents": 0, "errors": []}

    total_ops = len(CUSTOMERS) + sum(len(c["tickets"]) for c in CUSTOMERS) + len(HISTORICAL_NETWORK_INCIDENTS)
    done = 0

    def _progress(msg: str):
        nonlocal done
        done += 1
        if progress_callback:
            progress_callback(done / total_ops, msg)

    # ── 1. Customer profiles ────────────────────────────────────────────────
    for customer in CUSTOMERS:
        try:
            sector_tag = _make_sector_tag(customer["area"])
            customer_tag = f"customer:{customer['id']}"

            profile_content = (
                f"{customer['name']} (Account: {customer['account_number']}, ID: {customer['id']}) "
                f"is a customer in {customer['area']}. "
                f"Plan: {customer['plan']} fiber broadband. "
                f"Equipment: {customer['equipment']}. "
                f"Contact: {customer['phone']}, {customer['email']}. "
                f"Address: {customer['address']}."
            )

            hindsight_client.retain(
                bank_id=CUSTOMER_BANK,
                content=profile_content,
                context="customer-profile",
                tags=[customer_tag, sector_tag],
                document_id=f"profile-{customer['id']}",
            )
            results["customers"] += 1
            _progress(f"Seeded profile: {customer['name']}")

        except Exception as e:
            results["errors"].append(f"Profile {customer['id']}: {e}")
            _progress(f"Error: {customer['id']}")

    # ── 2. Support tickets ──────────────────────────────────────────────────
    for customer in CUSTOMERS:
        sector_tag = _make_sector_tag(customer["area"])
        customer_tag = f"customer:{customer['id']}"

        for ticket in customer["tickets"]:
            try:
                ticket_content = (
                    f"Support ticket {ticket['id']} for {customer['name']} ({customer['id']}) "
                    f"on {ticket['date']}: Issue type: {ticket['type']}. "
                    f"Description: {ticket['description']} "
                    f"Resolution: {ticket['resolution']} Status: {ticket['status']}."
                )

                hindsight_client.retain(
                    bank_id=CUSTOMER_BANK,
                    content=ticket_content,
                    context="support-ticket",
                    tags=[customer_tag, sector_tag, f"issue:{ticket['type'].lower().replace(' ', '-')}"],
                    document_id=ticket["id"],
                    timestamp=f"{ticket['date']}T00:00:00Z",
                )

                # Also retain resolutions in the resolution bank for cross-customer learning
                resolution_content = (
                    f"For issue type '{ticket['type']}' in {customer['area']} with {customer['equipment']}: "
                    f"{ticket['resolution']}"
                )
                hindsight_client.retain(
                    bank_id=RESOLUTION_BANK,
                    content=resolution_content,
                    context="resolution-knowledge",
                    tags=[f"issue:{ticket['type'].lower().replace(' ', '-')}", sector_tag],
                    document_id=f"res-{ticket['id']}",
                    timestamp=f"{ticket['date']}T00:00:00Z",
                )

                results["tickets"] += 1
                _progress(f"Seeded ticket: {ticket['id']}")

            except Exception as e:
                results["errors"].append(f"Ticket {ticket['id']}: {e}")
                _progress(f"Error: {ticket['id']}")

    # ── 3. Historical network incidents ─────────────────────────────────────
    for incident in HISTORICAL_NETWORK_INCIDENTS:
        try:
            sector_tag = f"sector:{incident['tag']}"
            incident_content = (
                f"Historical area-wide incident in {incident['sector']} on {incident['date']}: "
                f"Pattern observed: {incident['pattern']}. "
                f"Root cause: {incident['root_cause']} "
                f"Resolution: {incident['resolution']}"
            )

            hindsight_client.retain(
                bank_id=NETWORK_BANK,
                content=incident_content,
                context="network-incident",
                tags=[sector_tag, "historical-incident"],
                document_id=f"incident-{incident['sector'].lower().replace(' ', '-')}-{incident['date']}",
                timestamp=f"{incident['date']}T00:00:00Z",
            )
            results["network_incidents"] += 1
            _progress(f"Seeded incident: {incident['sector']} {incident['date']}")

        except Exception as e:
            results["errors"].append(f"Incident {incident['sector']}: {e}")
            _progress(f"Error: {incident['sector']}")

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Standalone execution
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from hindsight_client import Hindsight

    load_dotenv()
    base_url = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    api_key  = os.getenv("HINDSIGHT_API_KEY", "")
    print(f"Connecting to Hindsight Cloud at {base_url} ...")
    client = Hindsight(base_url=base_url, api_key=api_key if api_key else None)

    def show_progress(pct: float, msg: str):
        bar = "#" * int(pct * 30)
        print(f"\r[{bar:<30}] {pct*100:.0f}%  {msg:<60}", end="", flush=True)

    print("Starting seed...")
    results = seed_all(client, progress_callback=show_progress)
    print(f"\n\nSeed complete:")
    print(f"  Customers   : {results['customers']}")
    print(f"  Tickets     : {results['tickets']}")
    print(f"  Network events : {results['network_incidents']}")
    if results["errors"]:
        print(f"  Errors ({len(results['errors'])}):")
        for e in results["errors"]:
            print(f"    - {e}")
