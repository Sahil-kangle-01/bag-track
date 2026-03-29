"""
models.py — Request and Response shapes

Pydantic models define what data is expected and what data is returned.
FastAPI automatically validates every incoming request against these models.
If the request doesn't match → FastAPI returns a 422 error automatically.
You don't write any validation code yourself.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ──────────────────────────────────────────────
# REQUEST MODELS (what frontend sends to us)
# ──────────────────────────────────────────────

class CreateBagRequest(BaseModel):
    """
    Used by: POST /bags
    Staff enters this at check-in counter.
    """
    pnr: str                  # Passenger booking number e.g. "PNR-9921"
    passenger_name: str       # e.g. "Rahul Sharma"


class StatusUpdateRequest(BaseModel):
    """
    Used by: POST /bags/{bag_id}/status
    Staff scans bag and updates its status.
    """
    status: str               # Must be one of the VALID_STATUSES
    location: str             # Where the scan happened e.g. "Loading Bay B"


# ──────────────────────────────────────────────
# RESPONSE MODELS (what we send back to frontend)
# ──────────────────────────────────────────────

class EventResponse(BaseModel):
    """
    A single item in the bag's timeline.
    Returned as a list inside BagDetailResponse.
    """
    event_id: str
    status: str
    location: Optional[str]
    timestamp: datetime


class BagDetailResponse(BaseModel):
    """
    Used by: GET /bags/{bag_id}
    Full bag info + complete timeline.
    This is what the passenger tracking page displays.
    """
    bag_id: str
    pnr: str
    passenger_name: str
    current_status: str
    qr_code_url: Optional[str]
    last_updated: datetime
    timeline: List[EventResponse]   # Sorted oldest → newest


class BagCreatedResponse(BaseModel):
    """
    Used by: POST /bags (response)
    Returned to staff after bag is created at check-in.
    """
    bag_id: str
    pnr: str
    passenger_name: str
    qr_code_url: str
    current_status: str


class BagSummaryResponse(BaseModel):
    """
    Used by: GET /admin/bags
    One row in the admin dashboard table.
    Doesn't include the full timeline — just current state.
    """
    bag_id: str
    pnr: str
    passenger_name: str
    current_status: str
    location: Optional[str]
    last_updated: datetime


# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────

# Valid statuses in the correct order of progression
VALID_STATUSES = ["CHECKED_IN", "LOADED", "IN_TRANSIT", "ARRIVED", "DELAYED"]

# Status transition rules — a bag can only move forward
# Key = current status, Value = statuses it's allowed to move to
STATUS_TRANSITIONS = {
    "CHECKED_IN": ["LOADED", "DELAYED"],
    "LOADED":     ["IN_TRANSIT", "DELAYED"],
    "IN_TRANSIT": ["ARRIVED", "DELAYED"],
    "ARRIVED":    ["COLLECTED"],
    "COLLECTED":  [],
    "DELAYED":    ["LOADED", "IN_TRANSIT", "ARRIVED"],
    "SECURITY_ALERT": ["ARRIVED"],
}
