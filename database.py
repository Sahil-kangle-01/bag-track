"""
database.py — Supabase client setup

This is the ONLY file where the Supabase connection is configured.
Every other file imports `supabase` from here.
Never write your URL or KEY anywhere else.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()

SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

# This is the single shared Supabase client used across the entire app
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
