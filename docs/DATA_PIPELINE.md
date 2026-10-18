# GeoGuard V3: Data Ingestion & Preprocessing Pipeline

This document explains the reproducible data engineering pipeline powering GeoGuard V3.

---

## 1. Pipeline Architecture

```text
┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│   OpenCity Surveyed KML Data    │     │   Open-Meteo ERA5 Reanalysis     │
│   (192 Inundation + 753 2015)   │     │   Daily Rainfall Series (2015-23)│
└────────────────┬────────────────┘     └────────────────┬─────────────────┘
                 │                                       │
                 │ XML Parsing & Feature Extraction      │ JSON Parsing & Rolling Aggregation
                 ▼                                       ▼
┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│  Spatial Coordinate Extraction  │     │   Rolling Antecedent Rain Sums   │
│  (Lat, Lng, Depth, Remarks)     │     │   (1d Current, 3d Sum, 7d Sum)   │
└────────────────┬────────────────┘     └────────────────┬─────────────────┘
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │    PostGIS Spatial Alignment        │
                  │    (ST_Contains / Geodesic Buffer)  │
                  │    34 Monitored Chennai Sectors     │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │      Feature Vector Engineering     │
                  │  Rainfall, Elevation, Water Dist,   │
                  │  Coordinates, Seasonality Month     │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │    Anti-Leakage Chronological Split │
                  │  Train (≤2020), Val (2021), Test(23)│
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │  Final Clean Training CSV           │
                  │  (6,018 rows, 0 data leakage)       │
                  └─────────────────────────────────────┘
```

---

## 2. Spatial Alignment via PostGIS Grids

GeoGuard monitors 34 urban sectors across Chennai defined in the PostgreSQL database with PostGIS geometry representations:
- **Sector Centroids**: Point geometries (`srid=4326`)
- **Sector Polygons**: Polygon geometries (`srid=4326`) representing the ~1.2 km to 2.5 km municipal neighborhood zones.

During spatial alignment:
1. Each surveyed flood ground point from OpenCity is mapped to its parent sector using geodesic proximity and PostGIS bounding buffers.
2. Sectors with measured water depths $>0$ inches or multiple documented flood incidents during storm events are marked as historically vulnerable.
3. Digital Elevation Model (DEM) elevations and water channel proximities are merged directly from the GeoGuard topography database.

---

## 3. Temporal Alignment & Weather Accumulations

In urban hydrology, flood events do not depend solely on current rainfall. Antecedent moisture conditions dictate soil saturation and stormwater canal backwater effects.

For every historical observation date $t$:
- **Current Day Rainfall ($R_{\text{curr}}$)**: $P(t)$ in mm.
- **3-Day Antecedent Rainfall ($R_{\text{3d}}$)**: $\sum_{i=0}^2 P(t-i)$ in mm.
- **7-Day Cumulative Rainfall ($R_{\text{7d}}$)**: $\sum_{i=0}^6 P(t-i)$ in mm.
- **Wind Speed ($W_{\text{max}}$)**: Maximum sustained wind speed in km/h.

---

## 4. Anti-Leakage Chronological Splitting

To prevent **temporal data leakage** (where future disaster patterns contaminate training sets), standard random k-fold cross-validation is strictly avoided. The dataset is partitioned chronologically:

* **Training Set ($71.2\%$)**: October 2015 to December 2020 (4,284 records). Encompasses the historic December 2015 disaster and multiple moderate weather years.
* **Validation Set ($11.9\%$)**: November 2021 (714 records). Covers the November 2021 deep depression deluge.
* **Held-Out Test Set ($16.9\%$)**: December 2022 to December 2023 (1,020 records). Strictly reserved for final evaluation, including the unprecedented December 2023 Cyclone Michaung disaster.

---

## 5. Summary Statistics of Assembled Dataset

* **Total Records**: 6,018
* **Training Instances**: 4,284
* **Validation Instances**: 714
* **Test Instances**: 1,020
* **Positive Flood Class Instances**: 899 ($14.9\%$ minority class)
* **Negative Non-Flood Class Instances**: 5,119 ($85.1\%$ majority class)
* **Missing Values**: 0 (all fields validated and imputed via verifiable physical series)
