"""`/dispatcher/*` — consignment assignment surface.

Three endpoints:
  GET  /dispatcher/loads/unassigned          → list planned/unassigned loads.
  GET  /dispatcher/load/{load_id}/candidates → top-5 ranked drivers + Claude
                                               recommendation paragraph.
  POST /dispatcher/load/{load_id}/assign     → attach driver, flip status,
                                               bump last_assigned_at.

All Bearer-protected. Envelope-wrapped. Rejects assigning a driver that
wasn't in the scorer's qualified list — prevents the dispatcher from
accidentally handing work to an off-duty driver.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.models.db import Broker, Driver, Load
from backend.services.auth import require_relay_token
from backend.services.consignment import rank_candidates
from backend.services.consignment_agent import recommend
from backend.services.envelope import EnvelopeError, ok

logger = logging.getLogger("relay.routes.consignment")

router = APIRouter(
    prefix="/dispatcher", dependencies=[Depends(require_relay_token)]
)


class AssignRequest(BaseModel):
    driver_id: str


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/loads/unassigned")
async def list_unassigned_loads(db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(Load)
        .where(Load.driver_id.is_(None))
        .order_by(Load.delivery_appointment.asc())
    )
    loads = list(q.scalars().all())
    # Fetch broker names in one pass so the dashboard card has what it needs.
    broker_ids = {load.broker_id for load in loads}
    broker_map: dict[str, str] = {}
    if broker_ids:
        bq = await db.execute(select(Broker).where(Broker.id.in_(broker_ids)))
        broker_map = {b.id: b.name for b in bq.scalars().all()}
    data = [
        {
            "load_id": load.id,
            "load_number": load.load_number,
            "status": load.status,
            "broker_name": broker_map.get(load.broker_id, ""),
            "pickup_name": load.pickup_name,
            "pickup_appointment": _iso(load.pickup_appointment),
            "delivery_name": load.delivery_name,
            "delivery_appointment": _iso(load.delivery_appointment),
            "rate_linehaul": float(load.rate_linehaul),
        }
        for load in loads
    ]
    return ok({"count": len(data), "loads": data})


@router.get("/load/{load_id}/candidates")
async def candidates_for_load(load_id: str, db: AsyncSession = Depends(get_db)):
    try:
        load, ranked = await rank_candidates(db, load_id, top_n=5)
    except ValueError:
        raise EnvelopeError(
            "load_not_found", "No load found for that ID.", http_status=404
        )
    if load.driver_id is not None:
        raise EnvelopeError(
            "load_already_assigned",
            f"Load {load.load_number} already assigned to a driver.",
            http_status=409,
        )

    ai = await recommend(load, ranked)

    logger.info(
        "event=consignment_candidates_ranked load=%s top_driver=%s score=%.1f ai=%s",
        load.load_number,
        ranked[0].driver_id if ranked else "",
        ranked[0].total if ranked else 0.0,
        ai.get("recommended_driver_id", ""),
    )
    return ok(
        {
            "load_id": load.id,
            "load_number": load.load_number,
            "haul_miles": round(ranked[0].haul_miles, 1) if ranked else 0.0,
            "ranking": [s.to_public() for s in ranked],
            "ai_recommendation": ai,
        }
    )


@router.post("/load/{load_id}/assign")
async def assign_load(
    load_id: str, body: AssignRequest, db: AsyncSession = Depends(get_db)
):
    load = await db.get(Load, load_id)
    if load is None:
        raise EnvelopeError(
            "load_not_found", "No load found for that ID.", http_status=404
        )
    if load.driver_id is not None:
        raise EnvelopeError(
            "load_already_assigned",
            f"Load {load.load_number} is already assigned.",
            http_status=409,
        )

    # Validate: the driver must currently be in the qualified candidate list.
    _, ranked = await rank_candidates(db, load_id, top_n=10)
    qualified_ids = {s.driver_id for s in ranked if s.qualified}
    if body.driver_id not in qualified_ids:
        raise EnvelopeError(
            "driver_not_qualified",
            f"Driver {body.driver_id} is not in the qualified candidate list for this load.",
            http_status=400,
        )

    driver = await db.get(Driver, body.driver_id)
    if driver is None:
        raise EnvelopeError(
            "driver_not_found", "Driver not found.", http_status=404
        )

    now = datetime.now(timezone.utc)
    load.driver_id = driver.id
    load.status = "in_transit"
    driver.last_assigned_at = now
    await db.commit()

    logger.info(
        "event=load_assigned load=%s driver=%s",
        load.load_number,
        driver.name,
    )
    return ok(
        {
            "load_id": load.id,
            "load_number": load.load_number,
            "driver_id": driver.id,
            "driver_name": driver.name,
            "assigned_at": _iso(now),
            "status": load.status,
        }
    )


__all__ = ["router"]
