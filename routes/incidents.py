"""
routes/incidents.py — Security Incidents + Staff Assignment

Handles:
  - RFID exit detection → auto-raise incident
  - Smart staff assignment logic
  - Incident resolution by staff
  - Active incidents list for dashboard
"""

import random
import string
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from database import supabase

router = APIRouter()


def generate_id(prefix: str, length: int = 5) -> str:
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}-" + "".join(random.choices(chars, k=length))


def find_best_staff(terminal_id: str, airport_code: str) -> dict | None:
    """
    Smart staff assignment — finds best available staff member.
    
    Priority:
    1. Staff assigned to exact terminal + available
    2. Staff of same terminal type + available  
    3. Any SECURITY role staff + available
    4. Any SUPERVISOR + available
    5. None found → return None (manual assignment needed)
    """

    # Get the terminal info to know its type
    terminal_response = (
        supabase.table("terminals")
        .select("*")
        .eq("terminal_id", terminal_id)
        .execute()
    )

    terminal_type = None
    if terminal_response.data:
        terminal_type = terminal_response.data[0]["terminal_type"]

    # Priority 1 — exact terminal match
    response = (
        supabase.table("staff")
        .select("*")
        .eq("terminal_id", terminal_id)
        .eq("is_available", True)
        .eq("is_active", True)
        .eq("airport_code", airport_code)
        .execute()
    )
    if response.data:
        return response.data[0]

    # Priority 2 — same terminal type
    if terminal_type:
        terminals_of_type = (
            supabase.table("terminals")
            .select("terminal_id")
            .eq("terminal_type", terminal_type)
            .eq("airport_code", airport_code)
            .execute()
        )
        terminal_ids = [t["terminal_id"] for t in terminals_of_type.data]

        response = (
            supabase.table("staff")
            .select("*")
            .in_("terminal_id", terminal_ids)
            .eq("is_available", True)
            .eq("is_active", True)
            .execute()
        )
        if response.data:
            return response.data[0]

    # Priority 3 — any SECURITY staff
    response = (
        supabase.table("staff")
        .select("*")
        .eq("role", "SECURITY")
        .eq("is_available", True)
        .eq("is_active", True)
        .eq("airport_code", airport_code)
        .execute()
    )
    if response.data:
        return response.data[0]

    # Priority 4 — any SUPERVISOR
    response = (
        supabase.table("staff")
        .select("*")
        .eq("role", "SUPERVISOR")
        .eq("is_available", True)
        .eq("is_active", True)
        .eq("airport_code", airport_code)
        .execute()
    )
    if response.data:
        return response.data[0]

    # Nobody available
    return None


# ──────────────────────────────────────────────
# POST /incidents/raise — Raise a security incident
# Called automatically by RFID exit scan
# ──────────────────────────────────────────────

@router.post("/incidents/raise")
def raise_incident(payload: dict):
    """
    Raises a security incident and auto-assigns staff.
    
    Called when:
    - RFID detects bag at exit before passenger confirms collection
    - Manual staff raises a concern
    
    Body: {
      "bag_id": "BAG-X7K2P",
      "incident_type": "UNAUTHORIZED_EXIT",
      "detected_at": "T-PNQ-EXIT-01",
      "detected_by": "RFID-READER-EXIT-01",
      "airport_code": "PNQ"
    }
    """

    bag_id = payload.get("bag_id")
    incident_type = payload.get("incident_type", "UNAUTHORIZED_EXIT")
    detected_at = payload.get("detected_at")
    detected_by = payload.get("detected_by", "SYSTEM")
    airport_code = payload.get("airport_code", "PNQ")

    if not bag_id:
        raise HTTPException(status_code=400, detail="bag_id is required")

    # Verify bag exists
    bag_response = (
        supabase.table("bags")
        .select("*")
        .eq("bag_id", bag_id)
        .execute()
    )

    if not bag_response.data:
        raise HTTPException(status_code=404, detail="Bag not found")

    bag = bag_response.data[0]

    # Find best available staff to assign
    assigned_staff = None
    if detected_at:
        assigned_staff = find_best_staff(detected_at, airport_code)

    now = datetime.now(timezone.utc)

    # Create incident record
    incident_id = generate_id("INC")
    incident_data = {
        "incident_id": incident_id,
        "bag_id": bag_id,
        "incident_type": incident_type,
        "detected_at": detected_at,
        "detected_by": detected_by,
        "assigned_to": assigned_staff["staff_id"] if assigned_staff else None,
        "assigned_at": now.isoformat() if assigned_staff else None,
        "status": "ASSIGNED" if assigned_staff else "UNASSIGNED",
        "created_at": now.isoformat(),
    }

    supabase.table("incidents").insert(incident_data).execute()

    # Mark bag as SECURITY_ALERT
    supabase.table("bags").update({
        "current_status": "SECURITY_ALERT",
        "last_updated": now.isoformat(),
    }).eq("bag_id", bag_id).execute()

    # Insert event
    supabase.table("events").insert({
        "event_id": generate_id("EVT"),
        "bag_id": bag_id,
        "status": "SECURITY_ALERT",
        "location": detected_at or "Unknown",
        "timestamp": now.isoformat(),
    }).execute()

    # Mark assigned staff as unavailable
    if assigned_staff:
        supabase.table("staff").update({
            "is_available": False
        }).eq("staff_id", assigned_staff["staff_id"]).execute()

    return {
        "success": True,
        "incident_id": incident_id,
        "bag_id": bag_id,
        "incident_type": incident_type,
        "assigned_to": {
            "staff_id": assigned_staff["staff_id"],
            "name": assigned_staff["name"],
            "role": assigned_staff["role"],
            "phone": assigned_staff["phone"],
        } if assigned_staff else None,
        "status": "ASSIGNED" if assigned_staff else "UNASSIGNED",
        "message": (
            f"Incident raised and assigned to {assigned_staff['name']}"
            if assigned_staff
            else "Incident raised but no staff available. Manual assignment needed."
        )
    }


# ──────────────────────────────────────────────
# POST /incidents/{incident_id}/resolve
# Staff marks incident as resolved
# ──────────────────────────────────────────────

@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, payload: dict):
    """
    Staff resolves an incident after handling it.
    Frees up the staff member for next assignment.
    
    Body: {
      "resolution": "Bag returned to rightful owner",
      "resolved_by": "STF-001"
    }
    """

    resolution = payload.get("resolution", "Resolved by staff")
    resolved_by = payload.get("resolved_by")

    # Fetch incident
    response = (
        supabase.table("incidents")
        .select("*")
        .eq("incident_id", incident_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = response.data[0]
    now = datetime.now(timezone.utc)

    # Update incident
    supabase.table("incidents").update({
        "status": "RESOLVED",
        "resolution": resolution,
        "resolved_at": now.isoformat(),
    }).eq("incident_id", incident_id).execute()

    # Update bag status back to ARRIVED
    supabase.table("bags").update({
        "current_status": "ARRIVED",
        "last_updated": now.isoformat(),
    }).eq("bag_id", incident["bag_id"]).execute()

    # Insert resolution event
    supabase.table("events").insert({
        "event_id": generate_id("EVT"),
        "bag_id": incident["bag_id"],
        "status": "ARRIVED",
        "location": "Security Resolved",
        "timestamp": now.isoformat(),
    }).execute()

    # Free up the assigned staff member
    if incident.get("assigned_to"):
        supabase.table("staff").update({
            "is_available": True
        }).eq("staff_id", incident["assigned_to"]).execute()

    return {
        "success": True,
        "incident_id": incident_id,
        "resolution": resolution,
        "bag_status_reset_to": "ARRIVED"
    }


# ──────────────────────────────────────────────
# GET /incidents — All active incidents
# For admin dashboard alerts panel
# ──────────────────────────────────────────────

@router.get("/incidents")
def get_incidents(status: str = None):
    """
    Returns all incidents, optionally filtered by status.
    Used by admin dashboard to show active security alerts.
    
    GET /incidents           → all incidents
    GET /incidents?status=OPEN     → unresolved only
    GET /incidents?status=ASSIGNED → assigned but not resolved
    """

    query = (
        supabase.table("incidents")
        .select("*, bags(passenger_name, pnr), staff(name, role, phone)")
        .order("created_at", desc=True)
    )

    if status:
        query = query.eq("status", status.upper())

    response = query.execute()
    return response.data


# ──────────────────────────────────────────────
# GET /staff — All staff with availability
# ──────────────────────────────────────────────

@router.get("/staff")
def get_staff(airport_code: str = "PNQ"):
    """
    Returns all staff for an airport with their 
    current availability status.
    Used by admin dashboard staff panel.
    """

    response = (
        supabase.table("staff")
        .select("*, terminals(terminal_name, terminal_type)")
        .eq("airport_code", airport_code)
        .eq("is_active", True)
        .order("role")
        .execute()
    )

    return response.data