# GeoGuard V3: Data Sources Specification

This document provides a transparent, scientifically honest inventory of all real historical datasets utilized in GeoGuard V3 for empirical flood-risk modeling.

---

## 1. Chennai Historical Flood Inundation Survey Data (OpenCity)

* **Dataset Name**: Chennai Inundation Points with Depth of Inundation
* **Provider / Publisher**: OpenCity Open Data Portal (in partnership with citizen research groups and municipal disaster monitoring records)
* **Dataset URL**: [https://data.opencity.in/dataset/chennai-flooding-data](https://data.opencity.in/dataset/chennai-flooding-data)
* **Direct Resource URL**: `https://data.opencity.in/dataset/022dd080-e927-40d7-897d-adf3ee98ad69/resource/ceddf53f-03c0-4866-8ba8-5e84c8007a85/download/814ca028-4c84-4bd0-aa67-6dbaeb9b6ba5.kml`
* **Format**: OGC Keyhole Markup Language (KML / XML)
* **Geographic Coverage**: Greater Chennai Corporation (Bounds: ~12.85°N to 13.20°N, 80.10°E to 80.30°E)
* **Records Count**: 192 field-surveyed inundation ground points
* **Key Fields Used**:
  * `F_LATITUDE`: Ground-truth latitude coordinate
  * `F_LONGITUDE`: Ground-truth longitude coordinate
  * `DEPTH`: Measured flood inundation depth in inches (ranging from 1 to 48+ inches)
  * `F_REMARKS`: Qualitative field observer description ("completely inundated with flood water", "water stagnation 2-3 ft", etc.)
* **License**: Open Data Commons Open Database License (ODbL) / Public Government Open Data
* **Target Mapping**:
  * $0\text{ in} \to \text{Low}$ (Safe / No significant inundation)
  * $1\text{ to }6\text{ in} \to \text{Moderate}$ (Nuisance flooding / water stagnation)
  * $6\text{ to }18\text{ in} \to \text{High}$ (Substantial street and structural inundation)
  * $>18\text{ in} \to \text{Severe}$ (Catastrophic submergence / emergency evacuation required)

---

## 2. Chennai 2015 Flooding Points Survey (OpenCity)

* **Dataset Name**: Chennai Flooding Points in 2015
* **Provider / Publisher**: OpenCity Open Data Portal
* **Dataset URL**: [https://data.opencity.in/dataset/chennai-flooding-data](https://data.opencity.in/dataset/chennai-flooding-data)
* **Direct Resource URL**: `https://data.opencity.in/dataset/022dd080-e927-40d7-897d-adf3ee98ad69/resource/80ed2fa7-1150-4f55-8125-682ab55282ac/download/93d2905a-a580-482d-96b0-4d9ccf5273ef.kml`
* **Format**: KML / XML
* **Geographic Coverage**: Municipal administrative zones across Chennai
* **Records Count**: 753 surveyed flooded points
* **Key Fields Used**: `LAT`, `LONG_`, `ZONE`, `DIVISION`
* **Historical Event**: Historic December 2015 Chennai Floods
* **License**: ODbL / Open Government Data

---

## 3. Open-Meteo Historical Weather Archive API

* **Provider**: Open-Meteo / ECMWF ERA5 & ERA5-Land Reanalysis
* **API Endpoint**: `https://archive-api.open-meteo.com/v1/archive`
* **Geographic Coordinates**: Monitored Chennai coordinates (13.0827°N, 80.2707°E and sector centroids)
* **Temporal Coverage**: 2015-01-01 to 2024-12-31
* **Key Variables**:
  * `precipitation_sum` (mm): Daily cumulative precipitation
  * `rain_sum` (mm): Daily rainfall component
  * `precipitation_hours` (h): Duration of daily precipitation
  * `wind_speed_10m_max` (km/h): Maximum sustained wind speed (cyclonic marker)
* **Sampled Critical Storm Windows**:
  1. **December 2015 Extreme Monsoon Event**: 2015-11-15 to 2015-12-15 (Peak daily rainfall > 115mm reanalysis, record citywide inundation).
  2. **November 2021 Heavy Depression / Flooding**: 2021-11-01 to 2021-11-30 (Continuous prolonged deluge across coastal and central Chennai).
  3. **December 2023 Cyclone Michaung Event**: 2023-11-25 to 2023-12-15 (Severe cyclonic storm causing widespread stagnation and Adyar/Cooum river swelling).
  4. **Baseline Non-Flood Dry / Moderate Weather Windows**: Sampled dry and normal rain periods from 2016 to 2022 to provide negative (non-flood) training instances without synthetic data.
* **License**: Open Data Commons Attribution License (ODC-By) / Copernicus Climate Change Service (C3S)

---

## 4. GeoGuard Spatial Topography Baseline

* **File Path**: `data/chennai_places.csv` & PostGIS `grids` table
* **Records Count**: 34 major monitored urban sectors across North, Central, and South Chennai
* **Attributes**:
  * `place`: Recognized locality name (e.g., T. Nagar, Velachery, Adyar, Anna Nagar)
  * `latitude`, `longitude`: Sector centroid coordinates (SRID 4326)
  * `elevation_m`: Digital Elevation Model (DEM) ground elevation above mean sea level
  * `distance_to_water`: Physical distance in meters to nearest major canal, river, lake, or coastal body
  * `geom`: PostGIS polygon buffer zone representing sector administrative boundary

---

## 5. Summary Table of Variables

| Variable Name | Type | Unit | Origin / Provider | Purpose in V3 |
|---|---|---|---|---|
| `rainfall_current_mm` | Float | mm | Open-Meteo ERA5 | Current day precipitation |
| `rainfall_3d_accum_mm` | Float | mm | Open-Meteo ERA5 | 3-day antecedent precipitation sum (soil saturation) |
| `rainfall_7d_accum_mm` | Float | mm | Open-Meteo ERA5 | 7-day cumulative rainfall volume |
| `elevation_m` | Float | meters | GeoGuard DEM Baseline | Terrain height (inversely correlated with pooling) |
| `distance_to_water_m` | Float | meters | GeoGuard GIS Baseline | Proximity to water body/drainage channel |
| `latitude` | Float | degrees | OpenCity / GeoGuard | Spatial north-south positioning |
| `longitude` | Float | degrees | OpenCity / GeoGuard | Spatial east-west positioning |
| `month` | Integer | [1-12] | Calendar | Monsoon seasonality indicator (Oct-Dec NEM) |
| `flood_occurred` | Binary | 0 or 1 | OpenCity Survey / Ground Truth | Classification Target (0=No Inundation, 1=Inundation) |
| `flood_severity` | Categorical | Low/Mod/High/Sev | OpenCity Survey Depth | Severity Target based on measured depth in inches |
