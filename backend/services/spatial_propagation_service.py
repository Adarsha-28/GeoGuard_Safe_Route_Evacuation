"""Spatial Risk Propagation Service for GeoGuard V6.

Analyzes sector-to-sector spatial adjacency and risk propagation using PostGIS geometry:
- Identifies directly affected sectors (risk elevated or high/severe under simulation).
- Identifies neighboring sectors sharing topological boundaries (ST_Touches / ST_DWithin).
- Computes geographic concentration and spatial clustering metrics.
- Adheres strictly to advisory terminology: 'Spatial Risk Propagation', NOT hydraulic flood modeling.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid


class SpatialPropagationResult:
    """Encapsulates spatial propagation analysis across monitored sectors."""

    def __init__(
        self,
        direct_sector_ids: list[int],
        neighbor_sector_ids: list[int],
        spatial_types_by_grid: dict[int, str],  # "DIRECT", "NEIGHBOR", "UNAFFECTED"
        total_transitioned: int,
        critical_count: int,
        high_risk_count: int,
        geographic_concentration: float,  # 0.0 to 1.0 (clustering density)
    ) -> None:
        self.direct_sector_ids = direct_sector_ids
        self.neighbor_sector_ids = neighbor_sector_ids
        self.spatial_types_by_grid = spatial_types_by_grid
        self.total_transitioned = total_transitioned
        self.critical_count = critical_count
        self.high_risk_count = high_risk_count
        self.geographic_concentration = round(geographic_concentration, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direct_sector_ids": self.direct_sector_ids,
            "neighbor_sector_ids": self.neighbor_sector_ids,
            "total_transitioned": self.total_transitioned,
            "critical_count": self.critical_count,
            "high_risk_count": self.high_risk_count,
            "geographic_concentration": self.geographic_concentration,
        }


class SpatialPropagationService:
    """Analyzes spatial adjacency and topological propagation across Chennai grid sectors."""

    def __init__(self) -> None:
        self._adjacency_cache: dict[int, list[int]] | None = None

    def get_adjacent_grids(self, db: Session, grid_id: int) -> list[int]:
        """Fetch IDs of all sectors that touch or border the given sector in PostGIS."""
        query = text("""
            SELECT g2.id
            FROM grids g1
            JOIN grids g2 ON g1.id != g2.id
            WHERE g1.id = :grid_id
              AND (
                  ST_Touches(g1.geom, g2.geom)
                  OR ST_DWithin(g1.geom::geography, g2.geom::geography, 100.0)
              );
        """)
        try:
            result = db.execute(query, {"grid_id": grid_id}).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            logger.warning(f"PostGIS spatial adjacency query fallback for grid {grid_id}: {e}")
            # Coordinate bounding distance fallback
            target = db.query(Grid).filter(Grid.id == grid_id).first()
            if not target:
                return []
            neighbors = []
            all_grids = db.query(Grid).filter(Grid.id != grid_id).all()
            for g in all_grids:
                dist = ((g.latitude - target.latitude) ** 2 + (g.longitude - target.longitude) ** 2) ** 0.5
                if dist <= 0.035:  # ~3.5 km proximity threshold
                    neighbors.append(g.id)
            return neighbors

    def analyze_propagation(
        self,
        db: Session,
        sector_results: list[dict[str, Any]],
    ) -> SpatialPropagationResult:
        """Evaluate spatial risk propagation across simulated sector outcomes."""
        direct_sector_ids: list[int] = []
        critical_count = 0
        high_risk_count = 0
        total_transitioned = 0

        # 1. Identify directly affected sectors
        for res in sector_results:
            gid = res["grid_id"]
            sim_risk = res["simulated_risk"]
            base_risk = res["baseline_risk"]
            is_trans = res.get("is_transitioned", False) or (sim_risk != base_risk)

            if is_trans:
                total_transitioned += 1

            if sim_risk == "Severe":
                critical_count += 1
                direct_sector_ids.append(gid)
            elif sim_risk == "High":
                high_risk_count += 1
                direct_sector_ids.append(gid)
            elif is_trans and res.get("probability_delta", 0.0) >= 0.15:
                direct_sector_ids.append(gid)

        direct_set = set(direct_sector_ids)
        neighbor_set: set[int] = set()

        # 2. Identify neighbors of directly affected sectors
        for gid in direct_set:
            adjacent = self.get_adjacent_grids(db, gid)
            for adj_id in adjacent:
                if adj_id not in direct_set:
                    neighbor_set.add(adj_id)

        # 3. Classify each sector
        spatial_types: dict[int, str] = {}
        for res in sector_results:
            gid = res["grid_id"]
            if gid in direct_set:
                spatial_types[gid] = "DIRECT"
            elif gid in neighbor_set:
                spatial_types[gid] = "NEIGHBOR"
            else:
                spatial_types[gid] = "UNAFFECTED"

        # 4. Compute geographic concentration (spatial clustering index)
        # Ratio of adjacent directly-affected pairs to total possible connections
        concentration = 0.0
        if len(direct_set) > 1:
            adjacent_direct_pairs = 0
            for gid in direct_set:
                adj = set(self.get_adjacent_grids(db, gid))
                adjacent_direct_pairs += len(adj.intersection(direct_set))
            # Average adjacency connection density normalized by number of direct sectors
            concentration = min(1.0, (adjacent_direct_pairs / 2.0) / max(1, len(direct_set)))
        elif len(direct_set) == 1:
            concentration = 0.25

        return SpatialPropagationResult(
            direct_sector_ids=list(direct_set),
            neighbor_sector_ids=list(neighbor_set),
            spatial_types_by_grid=spatial_types,
            total_transitioned=total_transitioned,
            critical_count=critical_count,
            high_risk_count=high_risk_count,
            geographic_concentration=concentration,
        )


_spatial_service_instance: SpatialPropagationService | None = None


def get_spatial_propagation_service() -> SpatialPropagationService:
    global _spatial_service_instance
    if _spatial_service_instance is None:
        _spatial_service_instance = SpatialPropagationService()
    return _spatial_service_instance
