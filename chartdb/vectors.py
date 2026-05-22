"""
Vector schema definition and extraction.

The schema defines which features are pulled from a calculated chart
and how they map into a fixed-length float vector. To change what's
in the vector, edit the schema spec and call db.rebuild_vectors().

All angular values use sin/cos encoding to respect circular topology.
"""

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class VectorSchema:
    name: str
    bodies: list[str] = field(default_factory=list)
    longitudes: bool = True
    house_cusps: int = 12
    house_placements: bool = True
    nakshatras: bool = True
    retrogrades: bool = True

    def dims(self) -> int:
        n = len(self.bodies)
        d = 0
        if self.longitudes:
            d += n * 2
        if self.house_cusps:
            d += self.house_cusps * 2
        if self.house_placements:
            d += n * 2
        if self.nakshatras:
            d += n * 2
        if self.retrogrades:
            d += n
        return d

    def content_hash(self) -> str:
        spec = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(spec.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "bodies": self.bodies,
            "features": {
                "longitudes": self.longitudes,
                "house_cusps": self.house_cusps,
                "house_placements": self.house_placements,
                "nakshatras": self.nakshatras,
                "retrogrades": self.retrogrades,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VectorSchema":
        feat = d["features"]
        return cls(
            name=d["name"],
            bodies=d["bodies"],
            longitudes=feat.get("longitudes", True),
            house_cusps=feat.get("house_cusps", 12),
            house_placements=feat.get("house_placements", True),
            nakshatras=feat.get("nakshatras", True),
            retrogrades=feat.get("retrogrades", True),
        )


DEFAULT_SCHEMA = VectorSchema(
    name="vedic-9",
    bodies=["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"],
)


def _sincos(degrees: float) -> tuple[float, float]:
    rad = math.radians(degrees)
    return math.sin(rad), math.cos(rad)


def _nakshatra_to_degrees(nak_index: int) -> float:
    """Convert nakshatra index (0-26) to angular position for sin/cos encoding."""
    return nak_index * (360.0 / 27.0)


def extract_vector(chart, schema: VectorSchema) -> np.ndarray:
    """Extract a feature vector from a calculated libaditya Chart per the schema spec."""
    rashi = chart.rashi()
    planets_obj = rashi.planets()
    grahas = planets_obj.grahas()
    cusps = rashi.cusps().cusps

    dims = []

    if schema.longitudes:
        for body_name in schema.bodies:
            planet = grahas[body_name]
            s, c = _sincos(planet.long)
            dims.extend([s, c])

    if schema.house_cusps:
        for i in range(schema.house_cusps):
            cusp = cusps[i]
            s, c = _sincos(cusp.raw_longitude())
            dims.extend([s, c])

    if schema.house_placements:
        for body_name in schema.bodies:
            hp = rashi.house_position(body_name)
            s, c = _sincos(hp * 30.0)
            dims.extend([s, c])

    if schema.nakshatras:
        for body_name in schema.bodies:
            planet = grahas[body_name]
            nak_idx = planet.nakshatra().index()
            s, c = _sincos(_nakshatra_to_degrees(nak_idx))
            dims.extend([s, c])

    if schema.retrogrades:
        for body_name in schema.bodies:
            planet = grahas[body_name]
            dims.append(1.0 if planet.long_speed < 0 else 0.0)

    return np.array(dims, dtype=np.float64)
