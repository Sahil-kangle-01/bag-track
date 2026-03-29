"""
main.py — FastAPI Application Entry Point

This is the file you run to start the entire backend.
Command: uvicorn main:app --reload

What happens here:
1. FastAPI app is created
2. CORS is configured (allows frontend to talk to backend)
3. Static files are mounted (QR code images served from here)
4. All routes are connected
5. On startup → delay detection background task begins
6. Health check endpoint available at GET /
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from routes import bags, admin
from services.delay_service import start_delay_detection
from routes import bags, admin, incidents  # add incidents here



# ──────────────────────────────────────────────
# LIFESPAN — Startup & Shutdown logic
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs on startup.
    Code after `yield` runs on shutdown.

    On startup: begin delay detection background task.
    asyncio.create_task runs it in the background — doesn't block anything.
    """
    print("[Startup] BagTrack backend starting...")

    # Start delay detection as a background task
    # It runs every 10 minutes forever, silently
    asyncio.create_task(start_delay_detection())

    print("[Startup] Delay detection started.")
    print("[Startup] Backend ready.")

    yield  # App runs here

    # Shutdown logic (if needed later)
    print("[Shutdown] BagTrack backend shutting down.")


# ──────────────────────────────────────────────
# APP CREATION
# ──────────────────────────────────────────────

app = FastAPI(
    title="BagTrack Lite API",
    description="Real-time baggage tracking system — MVP",
    version="1.0.0",
    lifespan=lifespan,
)


# ──────────────────────────────────────────────
# CORS — Allow frontend to talk to backend
# ──────────────────────────────────────────────

# CORS = Cross Origin Resource Sharing
# Without this, your React frontend (localhost:5173) cannot call
# your FastAPI backend (localhost:8000) — browser blocks it.

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# STATIC FILES — Serve QR code images
# ──────────────────────────────────────────────

# QR codes are saved to static/qr/ by qr_service.py
# This makes them accessible via /static/qr/BAG-X7K2P.png
os.makedirs("static/qr", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ──────────────────────────────────────────────
# ROUTES — Connect all endpoint routers
# ──────────────────────────────────────────────

app.include_router(bags.router, tags=["Bags"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(incidents.router, tags=["Incidents"])


# ──────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────

@app.get("/")
def health_check():
    """
    Simple endpoint to confirm the backend is running.
    Visit http://localhost:8000 in browser → should see this response.
    Also check http://localhost:8000/docs for auto-generated API docs.
    """
    return {
        "status": "ok",
        "service": "BagTrack Lite API",
        "version": "1.0.0",
        "docs": "/docs",
    }
