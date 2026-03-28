"""
services/delay_service.py — Delay Detection Background Task

This runs silently in the background every 10 minutes while
FastAPI is running. Nobody calls it manually.

Logic:
  Every 10 minutes:
    1. Fetch all bags that haven't ARRIVED yet
    2. For each bag, check: now - last_updated > threshold
    3. If yes → mark as DELAYED in both tables
    4. Sleep. Repeat forever.

The threshold is configurable via DELAY_THRESHOLD_HOURS in .env
Set it to 0.1 during demo = triggers after 6 minutes instead of 2 hours
"""

import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from database import supabase

load_dotenv()

# How many hours before a bag is marked delayed
# Read from .env so you can change it without touching code
DELAY_THRESHOLD_HOURS = float(os.environ.get("DELAY_THRESHOLD_HOURS", 2))

# How often the checker runs (in seconds)
# 600 seconds = 10 minutes
CHECK_INTERVAL_SECONDS = 600


async def check_and_mark_delayed():
    """
    Single run of the delay check.
    Fetches all non-arrived bags and marks delayed ones.

    This function is also called once on startup so you don't
    have to wait 10 minutes for the first check.
    """
    print(f"[Delay Check] Running at {datetime.now(timezone.utc).isoformat()}")

    try:
        # Fetch all bags that are NOT yet arrived
        # We check everything except ARRIVED (journey complete) 
        response = (
            supabase.table("bags")
            .select("bag_id, current_status, last_updated")
            .neq("current_status", "ARRIVED")   # neq = not equal
            .execute()
        )

        bags = response.data
        print(f"[Delay Check] Checking {len(bags)} active bags")

        now = datetime.now(timezone.utc)
        delayed_count = 0

        for bag in bags:
            # Skip bags that are already marked delayed
            if bag["current_status"] == "DELAYED":
                continue

            # Parse the last_updated timestamp from Supabase
            last_updated_str = bag["last_updated"]
            last_updated = datetime.fromisoformat(last_updated_str)

            # Make sure it's timezone-aware for comparison
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)

            # Calculate how many hours since last update
            hours_since_update = (now - last_updated).total_seconds() / 3600

            if hours_since_update > DELAY_THRESHOLD_HOURS:
                bag_id = bag["bag_id"]
                print(f"[Delay Check] Marking {bag_id} as DELAYED ({hours_since_update:.1f}h since update)")

                # 1. Update the bags table (current state)
                supabase.table("bags").update({
                    "current_status": "DELAYED",
                    "last_updated": now.isoformat()
                }).eq("bag_id", bag_id).execute()

                # 2. Insert into events table (historical record)
                import random, string
                event_id = "EVT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))

                supabase.table("events").insert({
                    "event_id": event_id,
                    "bag_id": bag_id,
                    "status": "DELAYED",
                    "location": "System Auto-Detected",
                    "timestamp": now.isoformat()
                }).execute()

                delayed_count += 1

        print(f"[Delay Check] Done. Marked {delayed_count} bags as DELAYED.")

    except Exception as e:
        # Never crash the background task — just log and continue
        print(f"[Delay Check] Error: {e}")


async def start_delay_detection():
    """
    Infinite loop that runs delay checks every CHECK_INTERVAL_SECONDS.
    Called once on FastAPI startup — runs forever in background.

    asyncio.sleep is non-blocking — FastAPI handles requests normally
    while this is sleeping. It doesn't freeze anything.
    """
    print(f"[Delay Detection] Started. Threshold: {DELAY_THRESHOLD_HOURS}h. Interval: {CHECK_INTERVAL_SECONDS}s")

    while True:
        await check_and_mark_delayed()
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
