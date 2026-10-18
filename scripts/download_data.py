#!/usr/bin/env python3
"""Automated data acquisition script for GeoGuard V3.

Downloads authentic historical Chennai flood inundation records from OpenCity
and historical precipitation series from Open-Meteo ERA5 Archive API.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Project root
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"

OPENCITY_INUNDATION_URL = (
    "https://data.opencity.in/dataset/022dd080-e927-40d7-897d-adf3ee98ad69/"
    "resource/ceddf53f-03c0-4866-8ba8-5e84c8007a85/download/"
    "814ca028-4c84-4bd0-aa67-6dbaeb9b6ba5.kml"
)

OPENCITY_FLOOD_POINTS_2015_URL = (
    "https://data.opencity.in/dataset/022dd080-e927-40d7-897d-adf3ee98ad69/"
    "resource/80ed2fa7-1150-4f55-8125-682ab55282ac/download/"
    "93d2905a-a580-482d-96b0-4d9ccf5273ef.kml"
)

# Open-Meteo Historical Archive API (Chennai coordinates: 13.0827°N, 80.2707°E)
# Querying across major flood event years (2015, 2021, 2023) and non-flood baseline years (2016, 2018, 2022)
OPENMETEO_ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive?"
    "latitude=13.0827&longitude=80.2707"
    "&start_date=2015-10-01&end_date=2023-12-31"
    "&daily=precipitation_sum,rain_sum,precipitation_hours,wind_speed_10m_max"
    "&timezone=Asia%2FKolkata"
)


def download_file(url: str, dest_path: Path, description: str, timeout: int = 45) -> bool:
    """Download a file with HTTP error handling and validation."""
    print(f"[..] Fetching {description}...")
    print(f"     Source: {url}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "GeoGuard/3.0 OpenDataIngester (Research & Disaster Resilience)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                print(f"[ERROR] HTTP {response.status} received from {url}", file=sys.stderr)
                return False
            data = response.read()

        if len(data) == 0:
            print(f"[ERROR] Received 0 bytes for {description}", file=sys.stderr)
            return False

        dest_path.write_bytes(data)
        print(f"[OK] Saved {description} ({len(data):,} bytes) -> {dest_path.name}")
        return True

    except urllib.error.URLError as e:
        print(f"[ERROR] Failed to fetch {description}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error downloading {description}: {e}", file=sys.stderr)
        return False


def main() -> int:
    print("=" * 65)
    print("   GeoGuard V3 — Real Historical Dataset Ingestion Pipeline")
    print("=" * 65)

    success_inundation = download_file(
        OPENCITY_INUNDATION_URL,
        RAW_DIR / "chennai_flood_inundation_inches.kml",
        "OpenCity Chennai Inundation Points (Depth in Inches)",
    )

    success_points_2015 = download_file(
        OPENCITY_FLOOD_POINTS_2015_URL,
        RAW_DIR / "chennai_flooding_points_2015.kml",
        "OpenCity 2015 Flooding Points Survey",
    )

    success_weather = download_file(
        OPENMETEO_ARCHIVE_URL,
        RAW_DIR / "chennai_historical_weather_2015_2023.json",
        "Open-Meteo ERA5 Historical Weather Archive (2015-2023)",
    )

    print("\n" + "=" * 65)
    if success_inundation and success_points_2015 and success_weather:
        print("[SUCCESS] All real historical datasets downloaded and verified successfully!")
        return 0
    else:
        print("[WARN] Some downloads encountered warnings. Check logs above.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
