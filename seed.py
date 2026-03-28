"""
seed.py — Demo Data Generator

Run this on Day 7 to populate 50 bags for the demo.
Command: python seed.py

Creates bags at various stages of the journey so the
admin dashboard looks realistic with mixed statuses.
"""

import random
import string
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = "http://localhost:8000"

# Indian passenger names for realistic demo
PASSENGER_NAMES = [
    "Rahul Sharma", "Priya Patel", "Amit Verma", "Neha Singh", "Rohit Kumar",
    "Anjali Mehta", "Vikram Nair", "Deepika Reddy", "Suresh Iyer", "Kavita Joshi",
    "Arjun Gupta", "Pooja Agarwal", "Manish Tiwari", "Sneha Desai", "Kiran Shah",
    "Raj Malhotra", "Anita Bose", "Sanjay Rao", "Meera Pillai", "Vivek Chandra",
    "Divya Nair", "Aakash Jain", "Ritu Kapoor", "Nikhil Saxena", "Sunita Mishra",
]

# Sample PNR numbers
def random_pnr():
    return "PNR-" + "".join(random.choices(string.digits, k=4))

# Statuses to simulate mixed state in dashboard
STATUS_SEQUENCE = [
    ["CHECKED_IN"],
    ["CHECKED_IN", "LOADED"],
    ["CHECKED_IN", "LOADED", "IN_TRANSIT"],
    ["CHECKED_IN", "LOADED", "IN_TRANSIT", "ARRIVED"],
]

LOCATIONS = {
    "CHECKED_IN": ["Counter 1", "Counter 2", "Counter 3", "Counter 4", "Counter 7"],
    "LOADED":     ["Loading Bay A", "Loading Bay B", "Loading Bay C", "Makeup Area 2"],
    "IN_TRANSIT": ["Aircraft Hold", "Gate B12", "Tarmac Transfer"],
    "ARRIVED":    ["Carousel 1", "Carousel 2", "Carousel 3", "Baggage Claim DEL"],
}

def create_bag(pnr, name):
    response = requests.post(f"{BASE_URL}/bags", json={
        "pnr": pnr,
        "passenger_name": name
    })
    if response.status_code == 200:
        return response.json()["bag_id"]
    else:
        print(f"Failed to create bag: {response.text}")
        return None

def update_status(bag_id, status):
    location = random.choice(LOCATIONS[status])
    response = requests.post(f"{BASE_URL}/bags/{bag_id}/status", json={
        "status": status,
        "location": location
    })
    return response.status_code == 200

def seed():
    print(f"Seeding 50 bags into BagTrack...\n")
    success = 0

    for i in range(50):
        name = random.choice(PASSENGER_NAMES)
        pnr = random_pnr()

        # Pick a random journey stage
        journey = random.choice(STATUS_SEQUENCE)

        bag_id = create_bag(pnr, name)
        if not bag_id:
            continue

        # Apply each status update in sequence (skip CHECKED_IN, already set)
        for status in journey[1:]:
            updated = update_status(bag_id, status)
            if not updated:
                print(f"  Warning: Failed to update {bag_id} to {status}")

        final_status = journey[-1]
        print(f"  [{i+1:02d}] {bag_id} | {name} | {pnr} | {final_status}")
        success += 1

    print(f"\nDone. {success}/50 bags created successfully.")
    print(f"Open your admin dashboard to see them.")
    print(f"Tip: Set DELAY_THRESHOLD_HOURS=0.1 in .env to trigger DELAYED in 6 minutes.")

if __name__ == "__main__":
    seed()
