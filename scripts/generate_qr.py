from __future__ import annotations

import argparse
from pathlib import Path

import qrcode
import qrcode.image.svg
from qrcode.constants import ERROR_CORRECT_Q

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate robust QR files for the public Streamlit URL.")
    parser.add_argument("url", help="Public HTTPS URL, for example https://example.streamlit.app/")
    args = parser.parse_args()

    if not args.url.startswith("https://"):
        raise SystemExit("ERROR: the public QR must use an https:// URL, never localhost.")

    ASSETS.mkdir(exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=24,
        border=4,
    )
    qr.add_data(args.url)
    qr.make(fit=True)
    png = qr.make_image(fill_color="black", back_color="white")
    png_path = ASSETS / "qr_app.png"
    png.save(png_path)

    svg_qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    svg_qr.add_data(args.url)
    svg_qr.make(fit=True)
    svg = svg_qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    svg_path = ASSETS / "qr_app.svg"
    svg.save(svg_path)

    print(f"OK: PNG created at {png_path}")
    print(f"OK: SVG created at {svg_path}")
    print(f"Encoded URL: {args.url}")


if __name__ == "__main__":
    main()
