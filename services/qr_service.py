"""
services/qr_service.py — QR Code Generation

Single responsibility: take a bag_id, return a QR code.

The QR code encodes the full tracking URL so when a passenger
scans it, their phone opens the tracking page directly.

Example:
  Input:  "BAG-X7K2P"
  Encoded URL: "https://yourapp.vercel.app/track?bag=BAG-X7K2P"
  Output: QR code saved as static file, URL returned as string
"""

import qrcode
import os
from dotenv import load_dotenv

load_dotenv()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Where QR code images are saved on the server
QR_DIR = "static/qr"


def generate_qr_code(bag_id: str) -> str:
    """
    Generates a QR code image for the given bag_id.

    Steps:
    1. Build the tracking URL (passenger will land here after scanning)
    2. Generate QR code image from that URL
    3. Save image to static/qr/ folder
    4. Return the URL path to the image (stored in DB)

    Args:
        bag_id: The unique bag identifier e.g. "BAG-X7K2P"

    Returns:
        str: URL to access the QR image e.g. "/static/qr/BAG-X7K2P.png"
    """

    # Make sure the output directory exists
    os.makedirs(QR_DIR, exist_ok=True)

    # This is the URL the QR code will open when scanned
    tracking_url = f"{FRONTEND_URL}/track?bag={bag_id}"

    # Create QR code with good error correction
    # ERROR_CORRECT_H = even if 30% of QR is damaged, still scannable
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(tracking_url)
    qr.make(fit=True)

    # Create image (black QR on white background)
    img = qr.make_image(fill_color="black", back_color="white")

    # Save to file
    filename = f"{bag_id}.png"
    filepath = os.path.join(QR_DIR, filename)
    img.save(filepath)

    # Return the URL path — this gets stored in Supabase bags table
    return f"/static/qr/{filename}"
