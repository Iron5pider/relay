"""Flush + reseed a comprehensive demo dataset.

Replaces the minimal `data/*.json` boot seed with a fleet-scale dataset:
- 7 brokers (Acme, TQL, Coyote, RXO, Arrive, C.H. Robinson, J.B. Hunt)
- 30 drivers (6 hero-anchored + 24 additional, mixed languages/HOS/status)
- ~40 loads spanning every status + assigned/unassigned mix
- Historical voice_calls, detention_invoices (draft|sent|paid), exception_events

Hero anchors preserved verbatim (L-12345 Carlos / L-12347 Miguel /
L-12349 Tommy / Acme / Receiver XYZ) per `project_hero_demo_ids` memory.

Usage
-----
    python -m backend.scripts.reset_demo_state

Safeguards
----------
- Refuses to run if `settings.environment` is `prod`.
- Truncates with RESTART IDENTITY CASCADE inside one transaction — all-or-nothing.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from backend.config import settings
from backend.db import session as db_session
from backend.models.db import (
    Broker,
    DetentionInvoice,
    Driver,
    ExceptionEvent,
    Load,
    VoiceCall,
)

logger = logging.getLogger("relay.reset_demo_state")

# ---------------------------------------------------------------------------
# Demo-day anchor. All timestamps are computed relative to NOW so the
# dashboard always shows a coherent "this is happening now" state.
# ---------------------------------------------------------------------------
NOW = datetime(2026, 4, 18, 16, 45, 0, tzinfo=timezone.utc)


def _ts(delta_minutes: int = 0) -> datetime:
    """NOW + offset, always tz-aware UTC."""
    return NOW + timedelta(minutes=delta_minutes)


# ---------------------------------------------------------------------------
# Tables to truncate, in FK-safe order (children before parents).
# ---------------------------------------------------------------------------
_TRUNCATE_ORDER: tuple[str, ...] = (
    "transcript_snapshots",
    "dispatcher_tasks",
    "dispatcher_notifications",
    "invoices",
    "detention_events",
    "incidents",
    "webhook_events",
    "exception_events",
    "detention_invoices",
    "transcript_turns",
    "voice_calls",
    "loads",
    "drivers",
    "brokers",
)


async def _truncate_all(session) -> None:
    # Single TRUNCATE ... CASCADE handles FK cycles in one go; faster + safer
    # than deleting row-by-row.
    table_list = ", ".join(_TRUNCATE_ORDER)
    await session.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE;"))
    logger.info("event=truncate_done tables=%d", len(_TRUNCATE_ORDER))


# ---------------------------------------------------------------------------
# Brokers — 7 total.
# ---------------------------------------------------------------------------
BROKERS: list[dict] = [
    {"id": "br1a2b3c-0000-0000-0000-000000000010", "name": "Acme Logistics", "contact_name": "Jamie Park", "phone": "+12135550010", "email": "ops@acmelogistics.example", "preferred_update_channel": "call"},
    {"id": "br1a2b3c-0000-0000-0000-000000000011", "name": "TQL", "contact_name": "Marcus Webb", "phone": "+15135550011", "email": "dispatch+tql@example.com", "preferred_update_channel": "call"},
    {"id": "br1a2b3c-0000-0000-0000-000000000012", "name": "Coyote Logistics", "contact_name": "Elena Vasquez", "phone": "+13125550012", "email": "updates@coyote.example", "preferred_update_channel": "sms"},
    {"id": "br1a2b3c-0000-0000-0000-000000000013", "name": "RXO", "contact_name": "David Huang", "phone": "+19805550013", "email": "carrier.ops@rxo.example", "preferred_update_channel": "email"},
    {"id": "br1a2b3c-0000-0000-0000-000000000014", "name": "Arrive Logistics", "contact_name": "Priya Patel", "phone": "+15125550014", "email": "track@arrive.example", "preferred_update_channel": "call"},
    {"id": "br1a2b3c-0000-0000-0000-000000000015", "name": "C.H. Robinson", "contact_name": "Nadia Osei", "phone": "+19525550015", "email": "carriers@chr.example", "preferred_update_channel": "email"},
    {"id": "br1a2b3c-0000-0000-0000-000000000016", "name": "J.B. Hunt", "contact_name": "Derek Kim", "phone": "+14795550016", "email": "ops@jbhunt.example", "preferred_update_channel": "call"},
]

# Aliases for readability in load definitions.
BK_ACME = BROKERS[0]["id"]
BK_TQL = BROKERS[1]["id"]
BK_COYOTE = BROKERS[2]["id"]
BK_RXO = BROKERS[3]["id"]
BK_ARRIVE = BROKERS[4]["id"]
BK_CHR = BROKERS[5]["id"]
BK_JBHUNT = BROKERS[6]["id"]


def _driver_id(n: int) -> str:
    return f"d1a2b3c4-0000-0000-0000-{n:012d}"


def _load_id(n: int) -> str:
    # Keep original hero-anchor prefix so existing tests & hardcoded IDs still match.
    return f"b17e9c2d-4a5f-4e88-9c12-a6bd2e4f{n:04x}"


# ---------------------------------------------------------------------------
# Drivers — 30 total.
# ---------------------------------------------------------------------------
DRIVERS: list[dict] = [
    # --- 6 hero-anchored drivers (IDs 1-6) ---------------------------------
    {
        "id": _driver_id(1), "name": "Carlos Ramirez", "phone": "+16025555612",
        "preferred_language": "es", "truck_number": "28",
        "current_lat": 34.05, "current_lng": -118.24,
        "hos_drive_remaining_minutes": 210, "hos_shift_remaining_minutes": 240,
        "hos_cycle_remaining_minutes": 1680, "hos_remaining_minutes": 210,
        "status": "on_duty", "fatigue_level": "moderate",
        "last_checkin_at": _ts(-150), "next_scheduled_checkin_at": _ts(30),
        "updated_at": NOW,
    },
    {
        "id": _driver_id(2), "name": "John Okafor", "phone": "+14805550102",
        "preferred_language": "en", "truck_number": "14",
        "current_lat": 35.1983, "current_lng": -111.6513,
        "hos_drive_remaining_minutes": 385, "hos_shift_remaining_minutes": 465,
        "hos_cycle_remaining_minutes": 2100, "hos_remaining_minutes": 385,
        "status": "driving", "fatigue_level": "low",
        "last_checkin_at": _ts(-225), "next_scheduled_checkin_at": _ts(15),
        "updated_at": NOW,
    },
    {
        "id": _driver_id(3), "name": "Sarah Chen", "phone": "+14805550103",
        "preferred_language": "en", "truck_number": "09",
        "current_lat": 35.1983, "current_lng": -111.6513,
        "hos_drive_remaining_minutes": 660, "hos_shift_remaining_minutes": 840,
        "hos_cycle_remaining_minutes": 3600, "hos_remaining_minutes": 660,
        "status": "off_duty", "fatigue_level": "low",
        "last_checkin_at": _ts(-555), "next_scheduled_checkin_at": _ts(795),
        "updated_at": _ts(-15),
    },
    {
        "id": _driver_id(4), "name": "Miguel Rodriguez", "phone": "+15205550104",
        "preferred_language": "es", "truck_number": "22",
        "current_lat": 34.6697, "current_lng": -114.4611,
        "hos_drive_remaining_minutes": 25, "hos_shift_remaining_minutes": 95,
        "hos_cycle_remaining_minutes": 720, "hos_remaining_minutes": 25,
        "status": "driving", "fatigue_level": "unknown",
        "last_checkin_at": _ts(-300), "next_scheduled_checkin_at": _ts(0),
        "updated_at": NOW,
    },
    {
        "id": _driver_id(5), "name": "Raj Singh", "phone": "+16025550105",
        "preferred_language": "pa", "truck_number": "33",
        "current_lat": 33.0275, "current_lng": -116.8617,
        "hos_drive_remaining_minutes": 420, "hos_shift_remaining_minutes": 540,
        "hos_cycle_remaining_minutes": 2400, "hos_remaining_minutes": 420,
        "status": "driving", "fatigue_level": "low",
        "last_checkin_at": _ts(-135), "next_scheduled_checkin_at": _ts(105),
        "updated_at": NOW,
    },
    {
        "id": _driver_id(6), "name": "Tommy Walsh", "phone": "+15055550106",
        "preferred_language": "en", "truck_number": "41",
        "current_lat": 33.4484, "current_lng": -112.0740,
        "hos_drive_remaining_minutes": 540, "hos_shift_remaining_minutes": 620,
        "hos_cycle_remaining_minutes": 2880, "hos_remaining_minutes": 540,
        "status": "on_duty", "fatigue_level": "low",
        "last_checkin_at": _ts(-105), "next_scheduled_checkin_at": _ts(75),
        "updated_at": NOW,
    },
]

# --- 24 additional drivers (IDs 7-30) --------------------------------------
# Mix of languages, statuses, regions, HOS states. Spread across US corridors.
_EXTRA_DRIVERS = [
    # (name, phone_suffix, lang, truck#, lat, lng, drive_rem, shift_rem, cycle_rem, status, fatigue, last_checkin_min, city)
    ("Andre Thomas",        "0107", "en", "52", 40.4406, -79.9959,  480, 560, 2700, "driving",   "low",      -120, "Pittsburgh"),
    ("Isabela Santos",      "0108", "es", "17", 29.7604, -95.3698,  120, 180,  900, "on_duty",   "moderate", -165, "Houston"),
    ("Kevin Nguyen",        "0109", "en", "61", 47.6062, -122.3321, 360, 420, 2160, "driving",   "low",       -90, "Seattle"),
    ("Harpreet Kaur",       "0110", "pa", "08", 38.5816, -121.4944, 180, 240, 1440, "on_duty",   "low",      -210, "Sacramento"),
    ("Marcus Johnson",      "0111", "en", "45", 41.8781,  -87.6298,  50, 120,  600, "driving",   "high",     -480, "Chicago"),
    ("Sofia Alvarez",       "0112", "es", "19", 32.7767,  -96.7970, 300, 400, 1980, "driving",   "low",      -160, "Dallas"),
    ("Elijah Brown",        "0113", "en", "24", 33.7490,  -84.3880, 540, 600, 2700, "on_duty",   "low",       -80, "Atlanta"),
    ("Anh Pham",            "0114", "en", "56", 39.0997,  -94.5786,   0,  60,  300, "sleeper",   "high",     -720, "Kansas City"),
    ("Diego Morales",       "0115", "es", "37", 25.7617,  -80.1918, 390, 480, 2280, "driving",   "low",      -115, "Miami"),
    ("Priya Reddy",         "0116", "en", "12", 39.9526,  -75.1652, 420, 510, 2460, "driving",   "low",      -140, "Philadelphia"),
    ("Javier Ortega",       "0117", "es", "66", 34.0522, -118.2437,  80, 140,  840, "on_duty",   "moderate", -200, "Los Angeles"),
    ("Tyler Robinson",      "0118", "en", "72", 36.1627,  -86.7816, 240, 330, 1620, "driving",   "low",       -95, "Nashville"),
    ("Mei Lin",             "0119", "en", "21", 42.3601,  -71.0589, 560, 630, 2880, "on_duty",   "low",       -55, "Boston"),
    ("Omar Hassan",         "0120", "en", "31", 44.9778,  -93.2650, 360, 440, 2100, "driving",   "low",      -175, "Minneapolis"),
    ("Luis Guerrero",       "0121", "es", "48", 35.1495,  -90.0490,  40, 110,  540, "driving",   "moderate", -240, "Memphis"),
    ("Samuel Okonkwo",      "0122", "en", "55", 39.7684,  -86.1581, 510, 600, 2760, "driving",   "low",      -100, "Indianapolis"),
    ("Kiran Joshi",         "0123", "pa", "04", 37.3382, -121.8863, 600, 700, 3120, "on_duty",   "low",       -40, "San Jose"),
    ("Marcus O'Brien",      "0124", "en", "27", 45.5152, -122.6784, 420, 500, 2400, "driving",   "low",      -130, "Portland"),
    ("Rafael Cruz",         "0125", "es", "35", 32.2226, -110.9747,  15,  80,  480, "driving",   "high",     -340, "Tucson"),
    ("Grace Park",          "0126", "en", "18", 33.4484, -112.0740, 720, 840, 3960, "off_duty",  "low",      -620, "Phoenix"),
    ("Dmitri Volkov",       "0127", "en", "63", 39.7392, -104.9903, 300, 380, 1920, "driving",   "low",      -175, "Denver"),
    ("Fatima Ndiaye",       "0128", "en", "11", 29.4241,  -98.4936, 150, 220, 1260, "on_duty",   "moderate", -260, "San Antonio"),
    ("Rohit Desai",         "0129", "pa", "29", 40.7128,  -74.0060, 200, 280, 1500, "on_duty",   "low",      -150, "New York"),
    ("Tyrell Washington",   "0130", "en", "58", 38.9072,  -77.0369, 480, 560, 2640, "driving",   "low",      -110, "Washington DC"),
]

for i, row in enumerate(_EXTRA_DRIVERS, start=7):
    name, ph, lang, truck, lat, lng, drv, shift, cyc, status, fat, last_min, _city = row
    DRIVERS.append({
        "id": _driver_id(i),
        "name": name,
        "phone": f"+1480555{ph}",
        "preferred_language": lang,
        "truck_number": truck,
        "current_lat": lat,
        "current_lng": lng,
        "hos_drive_remaining_minutes": drv,
        "hos_shift_remaining_minutes": shift,
        "hos_cycle_remaining_minutes": cyc,
        "hos_remaining_minutes": drv,
        "status": status,
        "fatigue_level": fat,
        "last_checkin_at": _ts(last_min),
        "next_scheduled_checkin_at": _ts(last_min + 180),
        "updated_at": _ts(-5),
    })

assert len(DRIVERS) == 30, f"expected 30 drivers, got {len(DRIVERS)}"

# Quick aliases for load definitions.
DR_CARLOS = DRIVERS[0]["id"]
DR_JOHN = DRIVERS[1]["id"]
DR_SARAH = DRIVERS[2]["id"]
DR_MIGUEL = DRIVERS[3]["id"]
DR_RAJ = DRIVERS[4]["id"]
DR_TOMMY = DRIVERS[5]["id"]


# ---------------------------------------------------------------------------
# Loads — 42 total. Each row is a dict.
#
# Status distribution target:
#   exception:   3    (detention_threshold_breached x2 + missed_appointment x1)
#   in_transit: 10    (some with late_eta / hos_warning flags)
#   at_pickup:   4
#   at_delivery: 3
#   delivered:  12    (mix of historical + recently delivered w/ POD)
#   planned:     6    (assigned)
#   unassigned:  4    (driver_id = NULL, status=planned)
# ---------------------------------------------------------------------------

# Common stops — reuse for realism.
STOP_PHX_DC   = {"name": "Phoenix DC",          "lat": 33.4500, "lng": -112.0700, "phone": "+16025550100"}
STOP_PHX_EAST = {"name": "Phoenix DC East",     "lat": 33.4500, "lng": -111.9000, "phone": "+16025550200"}
STOP_RCV_XYZ  = {"name": "Receiver XYZ",        "lat": 34.0500, "lng": -118.2400, "phone": "+13105551234"}
STOP_DEN      = {"name": "Denver Distribution", "lat": 39.7392, "lng": -104.9903, "phone": "+17205552001"}
STOP_SLC      = {"name": "Salt Lake City Yard", "lat": 40.7608, "lng": -111.8910, "phone": "+18015557700"}
STOP_TUS      = {"name": "Tucson Yard",         "lat": 32.2226, "lng": -110.9747, "phone": "+15205550500"}
STOP_VEG      = {"name": "Las Vegas DC",        "lat": 36.1699, "lng": -115.1398, "phone": "+17025553300"}
STOP_ABQ      = {"name": "Albuquerque Yard",    "lat": 35.0844, "lng": -106.6504, "phone": "+15055555500"}
STOP_FLG      = {"name": "Flagstaff Yard",      "lat": 35.1983, "lng": -111.6513, "phone": "+19285556600"}
STOP_SDP      = {"name": "San Diego Port",      "lat": 32.7157, "lng": -117.1611, "phone": "+16195554400"}
STOP_OKC      = {"name": "Oklahoma City DC",    "lat": 35.4676,  "lng": -97.5164, "phone": "+14055558800"}
STOP_DAL      = {"name": "Dallas Cross-Dock",   "lat": 32.7767,  "lng": -96.7970, "phone": "+12145550700"}
STOP_LB       = {"name": "Long Beach Port",     "lat": 33.7701, "lng": -118.1937, "phone": "+15625558200"}
STOP_ATL      = {"name": "Atlanta Cross-Dock",  "lat": 33.7490,  "lng": -84.3880, "phone": "+14045557100"}
STOP_HOU      = {"name": "Houston Yard",        "lat": 29.7604,  "lng": -95.3698, "phone": "+17135559020"}
STOP_NSH      = {"name": "Nashville DC",        "lat": 36.1627,  "lng": -86.7816, "phone": "+16155559100"}
STOP_MEM      = {"name": "Memphis Hub",         "lat": 35.1495,  "lng": -90.0490, "phone": "+19015559200"}
STOP_CHI      = {"name": "Chicago Intermodal",  "lat": 41.8781,  "lng": -87.6298, "phone": "+13125559300"}
STOP_IND      = {"name": "Indianapolis DC",     "lat": 39.7684,  "lng": -86.1581, "phone": "+13175559400"}
STOP_KC       = {"name": "Kansas City Yard",    "lat": 39.0997,  "lng": -94.5786, "phone": "+18165559500"}
STOP_MSP      = {"name": "Minneapolis Yard",    "lat": 44.9778,  "lng": -93.2650, "phone": "+16125559600"}
STOP_MIA      = {"name": "Miami Port",          "lat": 25.7617,  "lng": -80.1918, "phone": "+13055559700"}
STOP_SEA      = {"name": "Seattle Port",        "lat": 47.6062, "lng": -122.3321, "phone": "+12065559800"}
STOP_NYC      = {"name": "NYC Cross-Dock",      "lat": 40.7128,  "lng": -74.0060, "phone": "+12125559900"}
STOP_BOS      = {"name": "Boston Yard",         "lat": 42.3601,  "lng": -71.0589, "phone": "+16175550001"}
STOP_PIT      = {"name": "Pittsburgh Hub",      "lat": 40.4406,  "lng": -79.9959, "phone": "+14125550002"}
STOP_SJC      = {"name": "San Jose Intermodal", "lat": 37.3382, "lng": -121.8863, "phone": "+14085550003"}
STOP_PDX      = {"name": "Portland DC",         "lat": 45.5152, "lng": -122.6784, "phone": "+15035550004"}
STOP_SAC      = {"name": "Sacramento Yard",     "lat": 38.5816, "lng": -121.4944, "phone": "+19165550005"}
STOP_SA       = {"name": "San Antonio Yard",    "lat": 29.4241,  "lng": -98.4936, "phone": "+12105550006"}


def _load(
    n: int,
    load_number: str,
    driver_id: str | None,
    broker_id: str,
    pickup: dict,
    delivery: dict,
    pickup_appt: datetime,
    delivery_appt: datetime,
    rate: float,
    status: str,
    *,
    arrived_at: datetime | None = None,
    detention_elapsed: int = 0,
    flags: list[str] | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    pod_url: str | None = None,
    pod_signed_by: str | None = None,
    pod_received_at: datetime | None = None,
    det_rate: float = 75.0,
    det_free: int = 120,
) -> dict:
    return {
        "id": _load_id(n),
        "load_number": load_number,
        "driver_id": driver_id,
        "broker_id": broker_id,
        "pickup_name": pickup["name"], "pickup_lat": pickup["lat"], "pickup_lng": pickup["lng"],
        "pickup_phone": pickup["phone"], "pickup_appointment": pickup_appt,
        "delivery_name": delivery["name"], "delivery_lat": delivery["lat"], "delivery_lng": delivery["lng"],
        "delivery_phone": delivery["phone"], "delivery_appointment": delivery_appt,
        "rate_linehaul": Decimal(str(rate)),
        "detention_rate_per_hour": Decimal(str(det_rate)),
        "detention_free_minutes": det_free,
        "status": status,
        "arrived_at_stop_at": arrived_at,
        "detention_minutes_elapsed": detention_elapsed,
        "exception_flags": flags or [],
        "pod_url": pod_url,
        "pod_signed_by": pod_signed_by,
        "pod_received_at": pod_received_at,
        "created_at": created_at or _ts(-1500),
        "updated_at": updated_at or NOW,
    }


LOADS: list[dict] = [
    # ================= HERO ANCHORS (exact IDs + values — do not rename) ====
    _load(0x7123, "L-12345", DR_CARLOS, BK_ACME, STOP_PHX_DC, STOP_RCV_XYZ,
          _ts(-640), _ts(-165), 2150.00, "exception",
          arrived_at=_ts(-165), detention_elapsed=167,
          flags=["detention_threshold_breached"], created_at=_ts(-1233)),
    _load(0x7124, "L-12346", DR_JOHN, BK_TQL, STOP_PHX_DC, STOP_DEN,
          _ts(-670), _ts(925), 2650.00, "in_transit",
          flags=["late_eta"], created_at=_ts(-1361)),
    _load(0x7125, "L-12347", DR_MIGUEL, BK_COYOTE, STOP_TUS, STOP_VEG,
          _ts(-525), _ts(195), 1425.00, "in_transit",
          flags=["hos_warning"], created_at=_ts(-1080)),
    _load(0x7126, "L-12348", DR_RAJ, BK_RXO, STOP_SDP, STOP_PHX_EAST,
          _ts(-405), _ts(255), 1180.00, "in_transit",
          created_at=_ts(-1055)),
    _load(0x7127, "L-12349", DR_TOMMY, BK_ARRIVE, STOP_PHX_DC, STOP_ABQ,
          _ts(-225), _ts(555), 1340.00, "exception",
          arrived_at=_ts(-240), detention_elapsed=240,
          flags=["detention_threshold_breached"], created_at=_ts(-435),
          det_rate=70.0),
    _load(0x7128, "L-12350", DR_SARAH, BK_ACME, STOP_FLG, STOP_PHX_DC,
          _ts(-1905), _ts(-1485), 780.00, "delivered",
          arrived_at=_ts(-1505), created_at=_ts(-2445), det_rate=60.0,
          pod_url="https://relay-pods.example/L-12350.pdf",
          pod_signed_by="J. Ruiz (Receiving)", pod_received_at=_ts(-1480)),
    _load(0x7129, "L-12351", DR_CARLOS, BK_TQL, STOP_PHX_DC, STOP_SLC,
          _ts(880), _ts(2475), 2900.00, "planned",
          created_at=_ts(-405)),
    _load(0x712a, "L-12352", DR_JOHN, BK_ARRIVE, STOP_DEN, STOP_OKC,
          _ts(1305), _ts(2355), 1820.00, "planned",
          created_at=_ts(-315), det_rate=65.0),
    _load(0x712b, "L-12353", None, BK_ACME, STOP_PHX_DC, STOP_DAL,
          _ts(975), _ts(2475), 2480.00, "planned",
          created_at=_ts(75)),
    _load(0x712c, "L-12354", None, BK_TQL, STOP_FLG, STOP_DEN,
          _ts(1155), _ts(2235), 1650.00, "planned",
          created_at=_ts(80), det_rate=65.0),
    _load(0x712d, "L-12355", None, BK_RXO, STOP_LB, STOP_PHX_EAST,
          _ts(1275), _ts(1995), 1320.00, "planned",
          created_at=_ts(85), det_rate=60.0),

    # ================= IN-TRANSIT (7 additional, mixed flags) ===============
    _load(0x7201, "L-12356", DRIVERS[6]["id"], BK_JBHUNT, STOP_PIT, STOP_CHI,
          _ts(-420), _ts(240), 1680.00, "in_transit", created_at=_ts(-720)),
    _load(0x7202, "L-12357", DRIVERS[7]["id"], BK_CHR, STOP_HOU, STOP_DAL,
          _ts(-180), _ts(180), 720.00, "in_transit",
          flags=["late_eta"], created_at=_ts(-480)),
    _load(0x7203, "L-12358", DRIVERS[8]["id"], BK_JBHUNT, STOP_SEA, STOP_PDX,
          _ts(-360), _ts(60), 580.00, "in_transit", created_at=_ts(-660)),
    _load(0x7204, "L-12359", DRIVERS[10]["id"], BK_COYOTE, STOP_CHI, STOP_IND,
          _ts(-220), _ts(80), 420.00, "in_transit",
          flags=["hos_warning"], created_at=_ts(-540), det_rate=60.0),
    _load(0x7205, "L-12360", DRIVERS[11]["id"], BK_TQL, STOP_DAL, STOP_MEM,
          _ts(-280), _ts(320), 890.00, "in_transit", created_at=_ts(-600)),
    _load(0x7206, "L-12361", DRIVERS[12]["id"], BK_ARRIVE, STOP_ATL, STOP_NSH,
          _ts(-140), _ts(220), 560.00, "in_transit", created_at=_ts(-420)),
    _load(0x7207, "L-12362", DRIVERS[14]["id"], BK_RXO, STOP_MIA, STOP_ATL,
          _ts(-320), _ts(280), 1150.00, "in_transit",
          flags=["late_eta"], created_at=_ts(-620)),

    # ================= AT_PICKUP (4) ========================================
    _load(0x7301, "L-12363", DRIVERS[16]["id"], BK_ACME, STOP_SJC, STOP_LB,
          _ts(-45), _ts(540), 680.00, "at_pickup",
          arrived_at=_ts(-50), detention_elapsed=45, created_at=_ts(-480)),
    _load(0x7302, "L-12364", DRIVERS[19]["id"], BK_COYOTE, STOP_PHX_DC, STOP_SLC,
          _ts(-20), _ts(1320), 2150.00, "at_pickup",
          arrived_at=_ts(-25), detention_elapsed=25, created_at=_ts(-300)),
    _load(0x7303, "L-12365", DRIVERS[17]["id"], BK_JBHUNT, STOP_PDX, STOP_SAC,
          _ts(-15), _ts(360), 720.00, "at_pickup",
          arrived_at=_ts(-20), detention_elapsed=20, created_at=_ts(-360)),
    _load(0x7304, "L-12366", DRIVERS[21]["id"], BK_CHR, STOP_DEN, STOP_MSP,
          _ts(-90), _ts(900), 1850.00, "at_pickup",
          arrived_at=_ts(-95), detention_elapsed=95, created_at=_ts(-480), det_rate=65.0),

    # ================= AT_DELIVERY (3) ======================================
    _load(0x7401, "L-12367", DRIVERS[22]["id"], BK_TQL, STOP_SA, STOP_HOU,
          _ts(-420), _ts(-30), 480.00, "at_delivery",
          arrived_at=_ts(-35), detention_elapsed=35, created_at=_ts(-900)),
    _load(0x7402, "L-12368", DRIVERS[12]["id"], BK_ARRIVE, STOP_NSH, STOP_ATL,
          _ts(-720), _ts(-10), 380.00, "at_delivery",
          arrived_at=_ts(-15), detention_elapsed=15, created_at=_ts(-1080)),
    _load(0x7403, "L-12369", DRIVERS[23]["id"], BK_RXO, STOP_BOS, STOP_NYC,
          _ts(-360), _ts(-45), 420.00, "at_delivery",
          arrived_at=_ts(-50), detention_elapsed=50, created_at=_ts(-720), det_rate=65.0),

    # ================= DELIVERED (11 — rich historical + POD) ===============
    _load(0x7501, "L-12370", DRIVERS[6]["id"], BK_JBHUNT, STOP_PIT, STOP_NYC,
          _ts(-2880), _ts(-2220), 980.00, "delivered",
          arrived_at=_ts(-2250), created_at=_ts(-3300),
          pod_url="https://relay-pods.example/L-12370.pdf",
          pod_signed_by="M. Nakamura", pod_received_at=_ts(-2215)),
    _load(0x7502, "L-12371", DRIVERS[7]["id"], BK_CHR, STOP_HOU, STOP_ATL,
          _ts(-3600), _ts(-2160), 1640.00, "delivered",
          arrived_at=_ts(-2180), created_at=_ts(-4020), det_rate=65.0,
          pod_url="https://relay-pods.example/L-12371.pdf",
          pod_signed_by="A. Thompson", pod_received_at=_ts(-2155)),
    _load(0x7503, "L-12372", DRIVERS[11]["id"], BK_TQL, STOP_DAL, STOP_KC,
          _ts(-2880), _ts(-1440), 1220.00, "delivered",
          arrived_at=_ts(-1460), created_at=_ts(-3360), det_rate=65.0,
          pod_url="https://relay-pods.example/L-12372.pdf",
          pod_signed_by="R. Castro", pod_received_at=_ts(-1440)),
    _load(0x7504, "L-12373", DRIVERS[13]["id"], BK_ACME, STOP_MSP, STOP_CHI,
          _ts(-2160), _ts(-960), 940.00, "delivered",
          arrived_at=_ts(-990), created_at=_ts(-2760),
          pod_url="https://relay-pods.example/L-12373.pdf",
          pod_signed_by="K. Brown", pod_received_at=_ts(-950)),
    _load(0x7505, "L-12374", DRIVERS[0]["id"], BK_ACME, STOP_PHX_DC, STOP_RCV_XYZ,
          _ts(-4320), _ts(-3720), 2050.00, "delivered",
          arrived_at=_ts(-3780), detention_elapsed=180,
          created_at=_ts(-4800),
          pod_url="https://relay-pods.example/L-12374.pdf",
          pod_signed_by="S. Martinez", pod_received_at=_ts(-3700)),
    _load(0x7506, "L-12375", DRIVERS[15]["id"], BK_COYOTE, STOP_IND, STOP_OKC,
          _ts(-2520), _ts(-1200), 1100.00, "delivered",
          arrived_at=_ts(-1220), created_at=_ts(-3120),
          pod_url="https://relay-pods.example/L-12375.pdf",
          pod_signed_by="D. Flores", pod_received_at=_ts(-1190)),
    _load(0x7507, "L-12376", DRIVERS[20]["id"], BK_JBHUNT, STOP_SEA, STOP_PDX,
          _ts(-1440), _ts(-900), 540.00, "delivered",
          arrived_at=_ts(-920), detention_elapsed=140,
          created_at=_ts(-1860),
          pod_url="https://relay-pods.example/L-12376.pdf",
          pod_signed_by="L. Tanaka", pod_received_at=_ts(-895)),
    _load(0x7508, "L-12377", DRIVERS[5]["id"], BK_ARRIVE, STOP_PHX_DC, STOP_LB,
          _ts(-3240), _ts(-2580), 820.00, "delivered",
          arrived_at=_ts(-2600), created_at=_ts(-3780),
          pod_url="https://relay-pods.example/L-12377.pdf",
          pod_signed_by="P. Navarro", pod_received_at=_ts(-2570)),
    _load(0x7509, "L-12378", DRIVERS[25]["id"], BK_CHR, STOP_DEN, STOP_ABQ,
          _ts(-1800), _ts(-1020), 760.00, "delivered",
          arrived_at=_ts(-1040), created_at=_ts(-2220),
          pod_url="https://relay-pods.example/L-12378.pdf",
          pod_signed_by="V. Ramirez", pod_received_at=_ts(-1015)),
    _load(0x750a, "L-12379", DRIVERS[29]["id"], BK_TQL, STOP_NYC, STOP_BOS,
          _ts(-1620), _ts(-1320), 420.00, "delivered",
          arrived_at=_ts(-1330), created_at=_ts(-2040),
          pod_url="https://relay-pods.example/L-12379.pdf",
          pod_signed_by="H. Kennedy", pod_received_at=_ts(-1315)),
    _load(0x750b, "L-12380", DRIVERS[1]["id"], BK_RXO, STOP_PHX_EAST, STOP_FLG,
          _ts(-5040), _ts(-4680), 380.00, "delivered",
          arrived_at=_ts(-4700), created_at=_ts(-5400),
          pod_url="https://relay-pods.example/L-12380.pdf",
          pod_signed_by="G. O'Brien", pod_received_at=_ts(-4670)),

    # ================= PLANNED — assigned (3 additional) ====================
    _load(0x7601, "L-12381", DRIVERS[9]["id"], BK_ACME, STOP_SAC, STOP_SJC,
          _ts(1080), _ts(1320), 320.00, "planned", created_at=_ts(-240)),
    _load(0x7602, "L-12382", DRIVERS[18]["id"], BK_COYOTE, STOP_HOU, STOP_SA,
          _ts(1260), _ts(1500), 380.00, "planned", created_at=_ts(-180)),
    _load(0x7603, "L-12383", DRIVERS[24]["id"], BK_ARRIVE, STOP_DAL, STOP_OKC,
          _ts(1440), _ts(1740), 640.00, "planned", created_at=_ts(-120), det_rate=65.0),

    # ================= UNASSIGNED PLANNED (1 additional) ====================
    _load(0x7701, "L-12384", None, BK_CHR, STOP_CHI, STOP_MSP,
          _ts(1620), _ts(2160), 820.00, "planned", created_at=_ts(90)),

    # ================= Third exception — missed_appointment =================
    _load(0x7801, "L-12385", DRIVERS[8]["id"], BK_JBHUNT, STOP_SEA, STOP_SJC,
          _ts(-720), _ts(-60), 1340.00, "exception",
          flags=["missed_appointment"], created_at=_ts(-1500)),
]


# ---------------------------------------------------------------------------
# Voice calls — historical depth. Idempotency-friendly synthetic SIDs.
# ---------------------------------------------------------------------------
def _call(
    call_num: int,
    load_id: str | None,
    driver_id: str | None,
    purpose: str,
    direction: str,
    outcome: str,
    started_min_ago: int,
    duration_s: int,
    *,
    language: str = "en",
    to_number: str = "+13105551234",
    transcript: list[dict] | None = None,
    trigger_reason: str | None = None,
    audio_url: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    started = _ts(-started_min_ago)
    ended = started + timedelta(seconds=duration_s) if outcome != "in_progress" else None
    return {
        "id": f"call-{call_num:04d}-demo",
        "load_id": load_id,
        "driver_id": driver_id,
        "conversation_id": conversation_id or f"conv-{call_num:04d}-demo",
        "agent_id": "agent_demo_seed",
        "trigger_reason": trigger_reason,
        "call_status": "done" if outcome != "in_progress" else "in_progress",
        "analysis_json": {},
        "direction": direction,
        "purpose": purpose,
        "from_number": "+14805551200",
        "to_number": to_number,
        "language": language,
        "started_at": started,
        "ended_at": ended,
        "duration_seconds": duration_s if ended else None,
        "outcome": outcome,
        "audio_url": audio_url,
        "twilio_call_sid": f"CAdemo{call_num:08d}",
        "transcript": transcript or [],
        "structured_data_json": {},
        "trigger_reasoning": None,
        "created_at": started,
    }


CALLS: list[dict] = [
    # Detention — Carlos historical (paid invoice)
    _call(1, _load_id(0x7505), DR_CARLOS, "detention_escalation", "outbound", "resolved",
          started_min_ago=3690, duration_s=38, language="en",
          to_number="+13105551234",
          transcript=[
              {"speaker": "agent", "text": "Hi, this is Maya calling on behalf of dispatch for load L-12374. We're past the free-wait window.", "language": "en"},
              {"speaker": "human", "text": "I can confirm detention. I'll send you an AP email address.", "language": "en"},
          ],
          audio_url="https://relay-audio.example/call-0001.mp3"),

    # Detention — historical (sent, awaiting payment)
    _call(2, _load_id(0x7507), DRIVERS[20]["id"], "detention_escalation", "outbound", "resolved",
          started_min_ago=880, duration_s=44,
          to_number="+12065559800",
          transcript=[
              {"speaker": "agent", "text": "This is Relay for JB Hunt — we're confirming 2h 20m over the free window at Seattle Port.", "language": "en"},
              {"speaker": "human", "text": "Confirmed. Billing is at ap@jbhunt.example.", "language": "en"},
          ]),

    # Proactive check-in — Miguel (Spanish), resolved with structured data
    _call(3, _load_id(0x7125), DR_MIGUEL, "driver_proactive_checkin", "outbound", "resolved",
          started_min_ago=290, duration_s=62, language="es",
          trigger_reason="hos_near_cap",
          to_number="+15205550104",
          transcript=[
              {"speaker": "agent", "text": "Hola Miguel, habla Maya. ¿Cómo te sientes?", "language": "es"},
              {"speaker": "human", "text": "Un poco cansado, como un 7.", "language": "es"},
              {"speaker": "agent", "text": "Te ofrezco parada en el Pilot de Needles, ¿te sirve?", "language": "es"},
              {"speaker": "human", "text": "Sí, perfecto.", "language": "es"},
          ]),

    # Proactive check-in — John, resolved
    _call(4, _load_id(0x7124), DR_JOHN, "driver_proactive_checkin", "outbound", "resolved",
          started_min_ago=220, duration_s=41, trigger_reason="scheduled",
          to_number="+14805550102",
          transcript=[
              {"speaker": "agent", "text": "Hey John, quick check-in. How's the I-40 run looking?", "language": "en"},
              {"speaker": "human", "text": "On schedule. No issues.", "language": "en"},
          ]),

    # Broker update — Acme on L-12346 (late ETA)
    _call(5, _load_id(0x7124), DR_JOHN, "broker_check_call", "outbound", "resolved",
          started_min_ago=120, duration_s=29,
          to_number="+15135550011",
          transcript=[
              {"speaker": "agent", "text": "This is Relay with a status on load L-12346. ETA drifting roughly 45 minutes due to weather.", "language": "en"},
              {"speaker": "human", "text": "Acknowledged — thanks for the heads up.", "language": "en"},
          ]),

    # Broker update — Coyote (completed earlier)
    _call(6, _load_id(0x7204), DRIVERS[10]["id"], "broker_check_call", "outbound", "resolved",
          started_min_ago=60, duration_s=22,
          to_number="+13125550012"),

    # Inbound driver check-in — Raj (Punjabi IVR)
    _call(7, _load_id(0x7126), DR_RAJ, "driver_checkin", "inbound", "resolved",
          started_min_ago=75, duration_s=34, language="pa",
          to_number="+16025550105"),

    # Voicemail outcome
    _call(8, _load_id(0x7207), DRIVERS[14]["id"], "broker_check_call", "outbound", "voicemail",
          started_min_ago=45, duration_s=18,
          to_number="+13055559700"),

    # Secondary detention — Tommy (L-12349), draft invoice
    _call(9, _load_id(0x7127), DR_TOMMY, "detention_escalation", "outbound", "resolved",
          started_min_ago=25, duration_s=47,
          to_number="+15055555500",
          transcript=[
              {"speaker": "agent", "text": "Hi, Maya calling for the Arrive Logistics load at Phoenix DC — we're 2 hours past the free window.", "language": "en"},
              {"speaker": "human", "text": "Let me check. Yes — I see it. Send the invoice.", "language": "en"},
          ]),

    # Historical Carlos check-in
    _call(10, None, DR_CARLOS, "driver_proactive_checkin", "outbound", "resolved",
          started_min_ago=150, duration_s=55, language="es", trigger_reason="scheduled",
          to_number="+16025555612"),

    # Failed call
    _call(11, _load_id(0x7206), DRIVERS[12]["id"], "broker_check_call", "outbound", "failed",
          started_min_ago=18, duration_s=5,
          to_number="+15125550014"),

    # In-progress — live banner realism
    _call(12, _load_id(0x7205), DRIVERS[11]["id"], "broker_check_call", "outbound", "in_progress",
          started_min_ago=1, duration_s=0,
          to_number="+15135550011"),
]


# ---------------------------------------------------------------------------
# Detention invoices — tied to detention_escalation calls above.
# ---------------------------------------------------------------------------
INVOICES: list[dict] = [
    # L-12374 historical Carlos — paid
    {
        "id": "inv-0001-demo", "load_id": _load_id(0x7505), "call_id": "call-0001-demo",
        "detention_minutes": 60, "rate_per_hour": Decimal("75.00"),
        "amount_usd": Decimal("75.00"), "pdf_url": "https://relay-pdfs.example/inv-0001.pdf",
        "status": "paid", "created_at": _ts(-3680),
    },
    # L-12376 Seattle JB Hunt — sent, awaiting payment
    {
        "id": "inv-0002-demo", "load_id": _load_id(0x7507), "call_id": "call-0002-demo",
        "detention_minutes": 20, "rate_per_hour": Decimal("75.00"),
        "amount_usd": Decimal("25.00"), "pdf_url": "https://relay-pdfs.example/inv-0002.pdf",
        "status": "sent", "created_at": _ts(-870),
    },
    # Hero Carlos active detention — draft, awaiting dispatcher review
    # detention_minutes = 167 - 120 = 47 → 47/60 * 75 = 58.75
    {
        "id": "inv-0003-demo", "load_id": _load_id(0x7123), "call_id": "call-0009-demo",
        "detention_minutes": 47, "rate_per_hour": Decimal("75.00"),
        "amount_usd": Decimal("58.75"), "pdf_url": "pending",
        "status": "draft", "created_at": _ts(-20),
    },
    # Tommy L-12349 — draft (freshly generated from call 9)
    # detention_minutes = 240 - 120 = 120 → 120/60 * 70 = 140.00
    {
        "id": "inv-0004-demo", "load_id": _load_id(0x7127), "call_id": "call-0009-demo" if False else "call-0009-demo",
        "detention_minutes": 120, "rate_per_hour": Decimal("70.00"),
        "amount_usd": Decimal("140.00"), "pdf_url": "https://relay-pdfs.example/inv-0004.pdf",
        "status": "draft", "created_at": _ts(-22),
    },
]
# NOTE: inv-0003 and inv-0004 reference call-0009 — both ok; we pick distinct call FKs below.
# Fix: point inv-0004 at call-0009, inv-0003 at a synthetic hero call we'll add.
INVOICES[2]["call_id"] = "call-0013-demo"  # we'll add this hero call below
# Add a hero detention call that inv-0003 references:
CALLS.append(
    _call(13, _load_id(0x7123), DR_CARLOS, "detention_escalation", "outbound", "resolved",
          started_min_ago=20, duration_s=40, language="en",
          to_number="+13105551234",
          transcript=[
              {"speaker": "agent", "text": "Hi, this is Maya calling about load L-12345. We're 47 minutes past the free window at Receiver XYZ.", "language": "en"},
              {"speaker": "human", "text": "I can confirm. Send to billing@acmelogistics.example.", "language": "en"},
          ])
)


# ---------------------------------------------------------------------------
# Exception events — rule-engine output.
# ---------------------------------------------------------------------------
EXCEPTION_EVENTS: list[dict] = [
    # Active hero exception
    {
        "id": "exc-0001-demo", "load_id": _load_id(0x7123), "driver_id": DR_CARLOS,
        "event_type": "detention_threshold_breached", "severity": "critical",
        "payload": {"minutes_over": 47, "free_minutes": 120, "elapsed": 167},
        "triggered_call_id": "call-0013-demo", "detected_at": _ts(-25),
    },
    # Miguel HOS warning
    {
        "id": "exc-0002-demo", "load_id": _load_id(0x7125), "driver_id": DR_MIGUEL,
        "event_type": "hos_warning", "severity": "warn",
        "payload": {"hos_drive_remaining_minutes": 25, "threshold_minutes": 30},
        "triggered_call_id": "call-0003-demo", "detected_at": _ts(-295),
    },
    # Tommy secondary detention
    {
        "id": "exc-0003-demo", "load_id": _load_id(0x7127), "driver_id": DR_TOMMY,
        "event_type": "detention_threshold_breached", "severity": "critical",
        "payload": {"minutes_over": 120, "free_minutes": 120, "elapsed": 240},
        "triggered_call_id": "call-0009-demo", "detected_at": _ts(-30),
    },
    # L-12385 missed appointment
    {
        "id": "exc-0004-demo", "load_id": _load_id(0x7801), "driver_id": DRIVERS[8]["id"],
        "event_type": "missed_appointment", "severity": "warn",
        "payload": {"minutes_late": 60},
        "triggered_call_id": None, "detected_at": _ts(-65),
    },
    # In-transit late-eta
    {
        "id": "exc-0005-demo", "load_id": _load_id(0x7124), "driver_id": DR_JOHN,
        "event_type": "late_eta", "severity": "info",
        "payload": {"projected_eta_minutes_drift": 45, "cause": "weather"},
        "triggered_call_id": "call-0005-demo", "detected_at": _ts(-125),
    },
    # Historical resolved HOS warning
    {
        "id": "exc-0006-demo", "load_id": _load_id(0x7504), "driver_id": DRIVERS[13]["id"],
        "event_type": "hos_warning", "severity": "warn",
        "payload": {"hos_drive_remaining_minutes": 28, "resolved": True},
        "triggered_call_id": None, "detected_at": _ts(-2100),
    },
    # L-12359 active HOS warning
    {
        "id": "exc-0007-demo", "load_id": _load_id(0x7204), "driver_id": DRIVERS[10]["id"],
        "event_type": "hos_warning", "severity": "warn",
        "payload": {"hos_drive_remaining_minutes": 50, "threshold_minutes": 60},
        "triggered_call_id": None, "detected_at": _ts(-30),
    },
    # Historical breakdown
    {
        "id": "exc-0008-demo", "load_id": _load_id(0x750a), "driver_id": DRIVERS[29]["id"],
        "event_type": "breakdown", "severity": "critical",
        "payload": {"resolved": True, "delay_minutes": 75},
        "triggered_call_id": None, "detected_at": _ts(-1500),
    },
]


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------
async def _insert_all(session) -> dict[str, int]:
    session.add_all([Broker(**b) for b in BROKERS])
    await session.flush()

    session.add_all([Driver(**d) for d in DRIVERS])
    await session.flush()

    session.add_all([Load(**ld) for ld in LOADS])
    await session.flush()

    session.add_all([VoiceCall(**c) for c in CALLS])
    await session.flush()

    session.add_all([DetentionInvoice(**i) for i in INVOICES])
    session.add_all([ExceptionEvent(**e) for e in EXCEPTION_EVENTS])
    await session.commit()

    return {
        "brokers": len(BROKERS),
        "drivers": len(DRIVERS),
        "loads": len(LOADS),
        "voice_calls": len(CALLS),
        "detention_invoices": len(INVOICES),
        "exception_events": len(EXCEPTION_EVENTS),
    }


def _summary(counts: dict[str, int]) -> str:
    status_counts: dict[str, int] = {}
    for ld in LOADS:
        status_counts[ld["status"]] = status_counts.get(ld["status"], 0) + 1
    unassigned = sum(1 for ld in LOADS if ld["driver_id"] is None)
    inv_by_status: dict[str, int] = {}
    for inv in INVOICES:
        inv_by_status[inv["status"]] = inv_by_status.get(inv["status"], 0) + 1

    lines = [
        "",
        "╭─ Relay demo reset ───────────────────────────────╮",
        f"│  Brokers:            {counts['brokers']:>4}                          │",
        f"│  Drivers:            {counts['drivers']:>4}                          │",
        f"│  Loads:              {counts['loads']:>4}                          │",
        f"│    └─ exception:     {status_counts.get('exception', 0):>4}                          │",
        f"│    └─ in_transit:    {status_counts.get('in_transit', 0):>4}                          │",
        f"│    └─ at_pickup:     {status_counts.get('at_pickup', 0):>4}                          │",
        f"│    └─ at_delivery:   {status_counts.get('at_delivery', 0):>4}                          │",
        f"│    └─ delivered:     {status_counts.get('delivered', 0):>4}                          │",
        f"│    └─ planned:       {status_counts.get('planned', 0):>4}  ({unassigned} unassigned)        │",
        f"│  Voice calls:        {counts['voice_calls']:>4}                          │",
        f"│  Detention invoices: {counts['detention_invoices']:>4}                          │",
        f"│    └─ draft:         {inv_by_status.get('draft', 0):>4}                          │",
        f"│    └─ sent:          {inv_by_status.get('sent', 0):>4}                          │",
        f"│    └─ paid:          {inv_by_status.get('paid', 0):>4}                          │",
        f"│  Exception events:   {counts['exception_events']:>4}                          │",
        "│                                                  │",
        "│  Hero anchors: L-12345 Carlos / L-12347 Miguel   │",
        "│                L-12349 Tommy / Acme / Rcvr XYZ   │",
        "╰──────────────────────────────────────────────────╯",
        "",
    ]
    return "\n".join(lines)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    if settings.environment == "prod":
        print("REFUSING to run reset_demo_state against environment=prod.", file=sys.stderr)
        sys.exit(2)

    db_session.get_engine()
    factory = db_session.AsyncSessionLocal
    assert factory is not None

    async with factory() as session:
        await _truncate_all(session)
        counts = await _insert_all(session)

    await db_session.dispose_engine()
    print(_summary(counts))


if __name__ == "__main__":
    asyncio.run(_main())


__all__ = ["NOW", "BROKERS", "DRIVERS", "LOADS", "CALLS", "INVOICES", "EXCEPTION_EVENTS"]
