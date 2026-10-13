#!/usr/bin/env python3
"""
ASTERIA - Sample TESS FITS Downloader
Downloads 3 verified NASA TESS Light Curve FITS files directly to your computer
so you can immediately test the drag-and-drop ingestion pipeline.
"""

import os
import sys

def main():
    print("========================================================")
    print("      ASTERIA - NASA TESS FITS Sample Downloader        ")
    print("========================================================")

    output_dir = os.path.join(os.path.dirname(__file__), "sample_fits")
    os.makedirs(output_dir, exist_ok=True)

    try:
        import lightkurve as lk
    except ImportError:
        print("Lightkurve not found. Please activate your .venv first:")
        print("  source .venv/bin/activate")
        sys.exit(1)

    targets = [
        {"name": "Pi Mensae c (Confirmed Super-Earth)", "tic": "TIC 261136679", "sector": 1},
        {"name": "TOI-700 d (Habitable Earth Analog)", "tic": "TIC 150428135", "sector": 11},
        {"name": "WASP-18 b (Ultra-Hot Gas Giant)", "tic": "TIC 100100827", "sector": 2},
    ]

    for item in targets:
        print(f"\n[+] Searching MAST for {item['name']} ({item['tic']})...")
        try:
            search = lk.search_lightcurve(item["tic"], mission="TESS", sector=item["sector"], author="SPOC")
            if len(search) > 0:
                print(f"    Downloading SPOC 2-min cadence FITS to {output_dir}/...")
                lc = search[0].download(download_dir=output_dir)
                print(f"    ✓ Successfully saved: {os.path.basename(lc.filename)}")
            else:
                print("    ! No SPOC product found, trying default author...")
                search = lk.search_lightcurve(item["tic"], mission="TESS", sector=item["sector"])
                if len(search) > 0:
                    lc = search[0].download(download_dir=output_dir)
                    print(f"    ✓ Successfully saved: {os.path.basename(lc.filename)}")
        except Exception as e:
            print(f"    ✗ Download error: {e}")

    print("\n========================================================")
    print(f"Done! Sample files are in: {os.path.abspath(output_dir)}")
    print("You can now drag & drop any of these files into http://127.0.0.1:8000/select")
    print("========================================================")

if __name__ == "__main__":
    main()
