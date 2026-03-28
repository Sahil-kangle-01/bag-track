"""
routes/bags.py — Core Bag Endpoints

Three endpoints:
  POST /bags              → Create bag at check-in
  GET  /bags/{bag_id}     → Track a bag (passenger view)
  POST /bags/{bag_id}/status → Update bag status (staff scan)

This is where the main business logic lives.
"""

import random
import string
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from database import supabase
from models import (
    CreateBagRequest,
    StatusUpdateRequest,
    BagCreatedResponse,
    BagDetailResponse,
    EventResponse,
    STATUS_TRANSITIONS,
)
from services.qr_service import generate_qr_code

router = APIRouter()


def generate_id(prefix: str, length: int = 5) -> str:
    """
    Generates a random ID with a prefix.
    Example: generate_id("BAG") → "BAG-X7K2P"
    Example: generate_id("EVT") → "EVT-A3M9Q"
    """
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=length))
    return f"{prefix}-{suffix}"


# ──────────────────────────────────────────────
# POST /bags — Create a new bag at check-in
# ──────────────────────────────────────────────

@router.post("/bags", response_model=BagCreatedResponse)
def create_bag(request: CreateBagRequest):
    """
    Called when staff creates a new bag at check-in counter.

    Flow:
    1. Generate unique BAG ID
    2. Generate QR code image for this bag
    3. Insert row into bags table (status = CHECKED_IN)
    4. Insert first event into events table
    5. Return bag details + QR code URL to frontend
    """

    # Step 1 — Generate unique bag ID
    bag_id = generate_id("BAG")

    # Step 2 — Generate QR code (saved to static/qr/ folder)
    qr_code_url = generate_qr_code(bag_id)

    now = datetime.now(timezone.utc).isoformat()

    # Step 3 — Insert into bags table
    bag_data = {
        "bag_id": bag_id,
        "pnr": request.pnr.upper().strip(),           # Normalize PNR to uppercase
        "passenger_name": request.passenger_name.strip(),
        "current_status": "CHECKED_IN",
        "location": "Check-in Counter",
        "qr_code_url": qr_code_url,
        "created_at": now,
        "last_updated": now,
    }

    bags_response = supabase.table("bags").insert(bag_data).execute()

    if not bags_response.data:
        raise HTTPException(status_code=500, detail="Failed to create bag in database")

    # Step 4 — Insert first event into events table
    event_data = {
        "event_id": generate_id("EVT"),
        "bag_id": bag_id,
        "status": "CHECKED_IN",
        "location": "Check-in Counter",
        "timestamp": now,
    }

    supabase.table("events").insert(event_data).execute()

    # Step 5 — Return response to frontend
    return BagCreatedResponse(
        bag_id=bag_id,
        pnr=request.pnr.upper().strip(),
        passenger_name=request.passenger_name.strip(),
        qr_code_url=qr_code_url,
        current_status="CHECKED_IN",
    )


# ──────────────────────────────────────────────
# GET /bags/{bag_id} — Track a bag
# ──────────────────────────────────────────────

@router.get("/bags/{bag_id}", response_model=BagDetailResponse)
def track_bag(bag_id: str):
    """
    Called when passenger opens the tracking page (via QR code scan).

    Flow:
    1. Fetch current bag state from bags table
    2. Fetch all events for this bag from events table
    3. Sort events by timestamp (oldest first = top of timeline)
    4. Return everything bundled together
    """

    # Step 1 — Fetch bag from bags table
    bag_response = (
        supabase.table("bags")
        .select("*")
        .eq("bag_id", bag_id)
        .execute()
    )

    if not bag_response.data:
        raise HTTPException(status_code=404, detail=f"Bag {bag_id} not found")

    bag = bag_response.data[0]

    # Step 2 — Fetch all events for this bag
    events_response = (
        supabase.table("events")
        .select("*")
        .eq("bag_id", bag_id)
        .order("timestamp", desc=False)   # Oldest first
        .execute()
    )

    # Step 3 — Convert events to EventResponse objects
    timeline = [
        EventResponse(
            event_id=e["event_id"],
            status=e["status"],
            location=e.get("location"),
            timestamp=datetime.fromisoformat(e["timestamp"]),
        )
        for e in events_response.data
    ]

    # Step 4 — Return full bag detail with timeline
    return BagDetailResponse(
        bag_id=bag["bag_id"],
        pnr=bag["pnr"],
        passenger_name=bag["passenger_name"],
        current_status=bag["current_status"],
        qr_code_url=bag.get("qr_code_url"),
        last_updated=datetime.fromisoformat(bag["last_updated"]),
        timeline=timeline,
    )


# ──────────────────────────────────────────────
# POST /bags/{bag_id}/status — Update bag status
# ──────────────────────────────────────────────

@router.post("/bags/{bag_id}/status")
def update_status(bag_id: str, request: StatusUpdateRequest):
    """
    Called when staff scans a bag (or clicks a button in Scanner UI).

    Flow:
    1. Fetch current bag to know its current status
    2. Validate the transition is allowed (can't go backwards)
    3. Update bags table with new status
    4. Insert new event into events table
    5. Return success
    """

    new_status = request.status.upper().strip()

    # Step 1 — Fetch current bag
    bag_response = (
        supabase.table("bags")
        .select("bag_id, current_status")
        .eq("bag_id", bag_id)
        .execute()
    )

    if not bag_response.data:
        raise HTTPException(status_code=404, detail=f"Bag {bag_id} not found")

    bag = bag_response.data[0]
    current_status = bag["current_status"]

    # Step 2 — Validate transition
    # Is the new status allowed from the current status?
    allowed_next = STATUS_TRANSITIONS.get(current_status, [])

    if new_status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current_status} to {new_status}. Allowed: {allowed_next}"
        )

    now = datetime.now(timezone.utc).isoformat()

    # Step 3 — Update bags table (overwrites current state)
    supabase.table("bags").update({
        "current_status": new_status,
        "location": request.location,
        "last_updated": now,
    }).eq("bag_id", bag_id).execute()

    # Step 4 — Insert new event (appends to history)
    event_data = {
        "event_id": generate_id("EVT"),
        "bag_id": bag_id,
        "status": new_status,
        "location": request.location,
        "timestamp": now,
    }

    supabase.table("events").insert(event_data).execute()

    # Step 5 — Return success
    return {
        "success": True,
        "bag_id": bag_id,
        "previous_status": current_status,
        "new_status": new_status,
        "location": request.location,
        "timestamp": now,
    }
