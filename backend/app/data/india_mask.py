"""Point-in-India test. A lon/lat rectangle over 68–97.5°E includes Tibet and Yunnan.

Two rings (mainland, northeast) plus island boxes. Bangladesh, Nepal, Tibet,
Myanmar and the open Bay stay out because they are not inside either ring.
"""

from __future__ import annotations

# (lat, lon), closed. Clockwise from Kutch.
_MAINLAND: tuple[tuple[float, float], ...] = (
    (23.70, 68.16),
    (24.55, 68.85),
    (25.70, 70.15),
    (26.85, 70.55),
    (27.95, 71.85),
    (28.85, 72.65),
    (30.25, 73.75),
    (32.55, 74.45),
    (34.15, 73.88),
    (35.12, 74.55),
    (35.60, 76.15),
    (35.50, 77.85),
    (34.85, 78.75),
    (32.85, 78.95),
    (31.35, 79.15),
    (30.38, 80.15),
    (30.18, 81.05),
    (30.12, 81.75),
    (28.35, 82.55),
    (27.40, 83.95),
    (26.72, 85.25),
    (26.42, 86.85),
    (26.32, 88.12),
    (25.70, 88.20),
    (25.22, 88.90),
    (24.80, 88.45),
    (24.35, 88.42),
    (23.35, 88.72),
    (22.75, 88.95),
    (22.05, 89.08),
    (21.52, 89.12),
    (21.42, 87.35),
    (20.65, 86.92),
    (19.75, 85.82),
    (18.15, 84.18),
    (16.95, 82.38),
    (15.80, 80.55),
    (13.50, 80.42),
    (13.05, 80.40),
    (11.80, 80.05),
    (10.20, 79.55),
    (9.20, 79.20),
    (8.07, 77.54),
    (8.18, 76.78),
    (9.55, 76.28),
    (11.15, 75.78),
    (12.75, 74.82),
    (14.45, 74.38),
    (15.75, 73.68),
    (16.95, 73.18),
    (18.85, 72.78),
    (20.15, 72.68),
    (21.48, 72.58),
    (22.15, 69.75),
    (22.75, 68.95),
    (23.70, 68.16),
)

# Sikkim + Assam + Arunachal + Meghalaya + Nagaland + Manipur + Mizoram + Tripura.
# Cut away from the mainland so Bangladesh is not swallowed.
_NORTHEAST: tuple[tuple[float, float], ...] = (
    (26.85, 88.02),
    (28.12, 88.02),
    (28.14, 88.92),
    (27.08, 88.92),
    (26.72, 89.82),
    (26.88, 91.45),
    (27.62, 92.05),
    (28.42, 92.85),
    (29.42, 94.25),
    (29.48, 95.55),
    (29.22, 96.45),
    (28.12, 97.38),
    (27.48, 96.15),
    (26.95, 95.35),
    (26.15, 95.05),
    (25.15, 94.88),
    (24.35, 94.68),
    (23.85, 94.35),
    (23.15, 93.75),
    (22.35, 93.05),
    (21.95, 92.88),
    (22.15, 92.48),
    (22.88, 92.32),
    (23.42, 92.18),
    (23.52, 91.88),
    (22.98, 91.48),
    (22.98, 91.12),
    (24.05, 91.12),
    (24.52, 91.42),
    (25.12, 91.92),
    (25.18, 91.15),
    (25.88, 90.15),
    (26.18, 89.82),
    (26.58, 89.68),
    (26.18, 89.58),
    (26.18, 88.62),
    (26.45, 88.18),
    (26.85, 88.02),
)

# south, north, west, east
_ANDAMAN = (6.55, 13.85, 92.15, 94.40)
_LAKSHADWEEP = (8.15, 12.55, 71.55, 74.10)


def _inside(lat: float, lon: float, ring: tuple[tuple[float, float], ...]) -> bool:
    """Ray-cast (lat, lon) against a closed or open ring of (lat, lon) vertices."""
    n = len(ring)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > lat) != (yj > lat):
            xint = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-18) + xi
            if lon < xint:
                inside = not inside
        j = i
    return inside


def _in_box(lat: float, lon: float, box: tuple[float, float, float, float]) -> bool:
    south, north, west, east = box
    return south <= lat <= north and west <= lon <= east


def in_india(lat: float, lon: float) -> bool:
    """True only for Indian land (mainland, NE, Andaman, Lakshadweep)."""
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    if not (6.4 <= lat_f <= 35.8 and 68.0 <= lon_f <= 97.45):
        return False
    if _in_box(lat_f, lon_f, _ANDAMAN) or _in_box(lat_f, lon_f, _LAKSHADWEEP):
        return True
    if _inside(lat_f, lon_f, _MAINLAND):
        return True
    if _inside(lat_f, lon_f, _NORTHEAST):
        return True
    return False
