#!/usr/bin/env python3
"""Training dataset generation pipeline for GeoGuard V3.

Performs spatial alignment of OpenCity ground-truth inundation points to GeoGuard's
34 monitored sectors, temporal alignment with Open-Meteo ERA5 precipitation records,
feature engineering (3d/7d antecedent accumulation), and anti-leakage chronological splitting.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PLACES_CSV = ROOT_DIR / "data" / "chennai_places.csv"
OUTPUT_CSV = PROCESSED_DIR / "chennai_flood_training_dataset.csv"

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def parse_inundation_kml(kml_path: Path) -> list[dict[str, Any]]:
    """Parse OpenCity surveyed inundation points with depth in inches."""
    if not kml_path.exists():
        raise FileNotFoundError(f"Missing {kml_path}")

    tree = ET.parse(kml_path)
    root = tree.getroot()
    records = []

    for pm in root.findall(".//kml:Placemark", KML_NS):
        data: dict[str, Any] = {}
        for sdata in pm.findall(".//kml:SimpleData", KML_NS):
            name = sdata.attrib.get("name")
            data[name] = sdata.text

        coord_elem = pm.find(".//kml:coordinates", KML_NS)
        if coord_elem is not None and coord_elem.text:
            parts = coord_elem.text.strip().split(",")
            if len(parts) >= 2:
                lng, lat = float(parts[0]), float(parts[1])
                depth_val = float(data.get("DEPTH", 0) or 0)
                remarks = str(data.get("F_REMARKS", "") or "")
                records.append({
                    "lat": lat,
                    "lng": lng,
                    "depth_inches": depth_val,
                    "remarks": remarks,
                })
    return records


def parse_flooding_points_2015_kml(kml_path: Path) -> list[dict[str, Any]]:
    """Parse OpenCity 2015 municipal flooding points survey."""
    if not kml_path.exists():
        raise FileNotFoundError(f"Missing {kml_path}")

    tree = ET.parse(kml_path)
    root = tree.getroot()
    records = []

    for pm in root.findall(".//kml:Placemark", KML_NS):
        coord_elem = pm.find(".//kml:coordinates", KML_NS)
        if coord_elem is not None and coord_elem.text:
            parts = coord_elem.text.strip().split(",")
            if len(parts) >= 2:
                lng, lat = float(parts[0]), float(parts[1])
                records.append({"lat": lat, "lng": lng})
    return records


def load_chennai_sectors(csv_path: Path) -> list[dict[str, Any]]:
    """Load GeoGuard's 34 monitored sectors."""
    sectors = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            sectors.append({
                "grid_id": idx,
                "place_name": row["place"].strip(),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "elevation_m": float(row["elevation_m"]),
                "distance_to_water_m": float(row["distance_to_water"]),
            })
    return sectors


def load_weather_series(json_path: Path) -> dict[str, dict[str, float]]:
    """Load daily meteorological series and compute rolling accumulations."""
    with open(json_path, mode="r", encoding="utf-8") as f:
        raw = json.load(f)

    daily = raw.get("daily", {})
    dates = daily.get("time", [])
    precip = daily.get("precipitation_sum", [])
    wind = daily.get("wind_speed_10m_max", [])

    date_map: dict[str, dict[str, float]] = {}
    for i, d_str in enumerate(dates):
        p = float(precip[i] or 0.0)
        w = float(wind[i] or 0.0)
        date_map[d_str] = {"precip": p, "wind": w}

    # Compute rolling 3-day and 7-day antecedent precipitation
    sorted_dates = sorted(date_map.keys())
    accum_map: dict[str, dict[str, float]] = {}

    for idx, d_str in enumerate(sorted_dates):
        p_curr = date_map[d_str]["precip"]
        w_curr = date_map[d_str]["wind"]

        # 3-day sum (today + prior 2 days)
        start_3d = max(0, idx - 2)
        p_3d = sum(date_map[sorted_dates[k]]["precip"] for k in range(start_3d, idx + 1))

        # 7-day sum (today + prior 6 days)
        start_7d = max(0, idx - 6)
        p_7d = sum(date_map[sorted_dates[k]]["precip"] for k in range(start_7d, idx + 1))

        accum_map[d_str] = {
            "rainfall_current_mm": round(p_curr, 2),
            "rainfall_3d_accum_mm": round(p_3d, 2),
            "rainfall_7d_accum_mm": round(p_7d, 2),
            "wind_speed_max_kmh": round(w_curr, 2),
        }

    return accum_map


def classify_severity(depth_inches: float, flood_occurred: int) -> str:
    """Map measured depth in inches to standard categorical severity."""
    if flood_occurred == 0 or depth_inches <= 0.0:
        return "Low"
    elif depth_inches <= 6.0:
        return "Moderate"
    elif depth_inches <= 18.0:
        return "High"
    else:
        return "Severe"


def build_dataset() -> Path:
    """Execute complete dataset assembly and spatial-temporal alignment."""
    print("[..] Parsing OpenCity surveyed inundation records...")
    inundation_pts = parse_inundation_kml(RAW_DIR / "chennai_flood_inundation_inches.kml")
    flooding_2015_pts = parse_flooding_points_2015_kml(RAW_DIR / "chennai_flooding_points_2015.kml")
    print(f"[OK] Loaded {len(inundation_pts)} depth-surveyed points and {len(flooding_2015_pts)} 2015 flood points.")

    sectors = load_chennai_sectors(PLACES_CSV)
    print(f"[OK] Loaded {len(sectors)} GeoGuard monitored sectors.")

    # Spatial alignment: Associate each surveyed point to nearest sector within 2.5 km
    sector_flood_profiles: dict[int, dict[str, Any]] = {}
    for s in sectors:
        gid = s["grid_id"]
        # Find points within 2.5 km of sector centroid
        nearby_depths = [
            p["depth_inches"]
            for p in inundation_pts
            if haversine_km(s["latitude"], s["longitude"], p["lat"], p["lng"]) <= 2.5
        ]
        nearby_2015_count = sum(
            1
            for p in flooding_2015_pts
            if haversine_km(s["latitude"], s["longitude"], p["lat"], p["lng"]) <= 2.5
        )

        max_depth = max(nearby_depths) if nearby_depths else 0.0
        sector_flood_profiles[gid] = {
            "max_surveyed_depth_inches": max_depth,
            "flood_points_count": len(nearby_depths) + nearby_2015_count,
            "is_vulnerable": (max_depth > 0.0 or nearby_2015_count >= 2),
        }

    weather_series = load_weather_series(RAW_DIR / "chennai_historical_weather_2015_2023.json")
    print(f"[OK] Processed {len(weather_series)} daily weather observations with rolling accumulators.")

    # Define verified historical meteorological event windows:
    # 1. 2015 Catastrophic Floods: Nov 15, 2015 - Dec 10, 2015
    # 2. 2021 November Deep Depression / Flooding: Nov 05, 2021 - Nov 25, 2021
    # 3. 2023 Cyclone Michaung Catastrophe: Dec 01, 2023 - Dec 10, 2023
    # 4. Verified non-flood baseline dates: sample non-flood wet, moderate, and dry days across 2016-2022
    disaster_dates_2015 = [
        f"2015-11-{d:02d}" for d in range(15, 31)
    ] + [f"2015-12-{d:02d}" for d in range(1, 11)]

    disaster_dates_2021 = [
        f"2021-11-{d:02d}" for d in range(5, 26)
    ]

    disaster_dates_2023 = [
        f"2023-12-{d:02d}" for d in range(1, 11)]

    # Non-flood baseline dates: sampled across dry and moderate non-flood days
    baseline_dates: list[str] = []
    for yr in [2016, 2017, 2018, 2019, 2020, 2022]:
        # Sample non-monsoon and moderate rain days
        baseline_dates.extend([f"{yr}-02-{d:02d}" for d in range(10, 16)])
        baseline_dates.extend([f"{yr}-07-{d:02d}" for d in range(10, 16)])
        baseline_dates.extend([f"{yr}-10-{d:02d}" for d in range(10, 18)])

    # Chronological dataset construction
    rows: list[dict[str, Any]] = []

    all_event_dates = sorted(set(disaster_dates_2015 + disaster_dates_2021 + disaster_dates_2023 + baseline_dates))

    for date_str in all_event_dates:
        if date_str not in weather_series:
            continue
        w = weather_series[date_str]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year = dt.year
        month = dt.month

        is_major_disaster = (
            (date_str in disaster_dates_2015 and w["rainfall_3d_accum_mm"] > 40.0)
            or (date_str in disaster_dates_2021 and w["rainfall_3d_accum_mm"] > 50.0)
            or (date_str in disaster_dates_2023 and w["rainfall_3d_accum_mm"] > 60.0)
        )

        for s in sectors:
            gid = s["grid_id"]
            prof = sector_flood_profiles[gid]

            # Determine ground truth flood outcome based on physical events
            if is_major_disaster and prof["is_vulnerable"]:
                flood_occurred = 1
                depth = prof["max_surveyed_depth_inches"] if prof["max_surveyed_depth_inches"] > 0 else 6.0
                severity = classify_severity(depth, 1)
            elif is_major_disaster and (s["elevation_m"] <= 4.0 or s["distance_to_water_m"] <= 500.0):
                flood_occurred = 1
                severity = "Moderate"
            elif w["rainfall_current_mm"] > 70.0 and s["elevation_m"] <= 3.0:
                flood_occurred = 1
                severity = "Moderate"
            else:
                flood_occurred = 0
                severity = "Low"

            # Anti-leakage chronological split assignment:
            # 2015-2020 -> TRAIN (~70%)
            # 2021 -> VALIDATION (~15%)
            # 2022-2023 -> TEST (~15%)
            if year <= 2020:
                split = "train"
            elif year == 2021:
                split = "validation"
            else:
                split = "test"

            rows.append({
                "date": date_str,
                "grid_id": gid,
                "place_name": s["place_name"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "elevation_m": s["elevation_m"],
                "distance_to_water_m": s["distance_to_water_m"],
                "rainfall_current_mm": w["rainfall_current_mm"],
                "rainfall_3d_accum_mm": w["rainfall_3d_accum_mm"],
                "rainfall_7d_accum_mm": w["rainfall_7d_accum_mm"],
                "wind_speed_max_kmh": w["wind_speed_max_kmh"],
                "month": month,
                "flood_occurred": flood_occurred,
                "flood_severity": severity,
                "split": split,
            })

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "date", "grid_id", "place_name", "latitude", "longitude",
        "elevation_m", "distance_to_water_m", "rainfall_current_mm",
        "rainfall_3d_accum_mm", "rainfall_7d_accum_mm", "wind_speed_max_kmh",
        "month", "flood_occurred", "flood_severity", "split",
    ]

    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Generated training dataset -> {OUTPUT_CSV.name}")
    print(f"     Total records: {len(rows):,}")
    print(f"     Train records: {sum(1 for r in rows if r['split'] == 'train'):,}")
    print(f"     Validation records: {sum(1 for r in rows if r['split'] == 'validation'):,}")
    print(f"     Test records: {sum(1 for r in rows if r['split'] == 'test'):,}")
    print(f"     Positive flood instances: {sum(1 for r in rows if r['flood_occurred'] == 1):,}")
    print(f"     Negative flood instances: {sum(1 for r in rows if r['flood_occurred'] == 0):,}")
    return OUTPUT_CSV


def main() -> int:
    print("=" * 65)
    print("   GeoGuard V3 — Training Dataset Assembly & Alignment")
    print("=" * 65)
    out_path = build_dataset()
    print(f"[SUCCESS] Dataset successfully written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
