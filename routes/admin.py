"""
routes/admin.py — Admin Dashboard Endpoints

One endpoint:
  GET /admin/bags → Get all bags with optional filters

Kept separate from bags.py so you can later add
admin authentication middleware here without touching
the passenger-facing routes at all.
"""

from datetime import datetime
from fastapi import APIRouter, Query
from typing import Optional
from database import supabase
from models import BagSummaryResponse

router = APIRouter()


# ──────────────────────────────────────────────
# GET /admin/bags — Get all bags (admin view)
# ──────────────────────────────────────────────

@router.get("/admin/bags", response_model=list[BagSummaryResponse])
def get_all_bags(
    status: Optional[str] = Query(default=None, description="Filter by status e.g. DELAYED"),
    pnr: Optional[str] = Query(default=None, description="Filter by PNR e.g. PNR-9921"),
):
    """
    Called by the admin dashboard to show the bags table.

    Supports two optional query parameters:
      GET /admin/bags                         → all bags
      GET /admin/bags?status=DELAYED          → only delayed bags
      GET /admin/bags?pnr=PNR-9921           → bags for this PNR
      GET /admin/bags?status=LOADED&pnr=PNR-9921 → combine both

    Flow:
    1. Build query with optional filters
    2. Return list of bag summaries sorted by last_updated (newest first)
    """

    # Start building the query
    query = supabase.table("bags").select("*")

    # Apply filters only if provided
    if status:
        query = query.eq("current_status", status.upper().strip())

    if pnr:
        query = query.eq("pnr", pnr.upper().strip())

    # Sort newest activity first
    query = query.order("last_updated", desc=True)

    response = query.execute()

    # Convert to response model
    return [
        BagSummaryResponse(
            bag_id=bag["bag_id"],
            pnr=bag["pnr"],
            passenger_name=bag["passenger_name"],
            current_status=bag["current_status"],
            location=bag.get("location"),
            last_updated=datetime.fromisoformat(bag["last_updated"]),
        )
        for bag in response.data
    ]
