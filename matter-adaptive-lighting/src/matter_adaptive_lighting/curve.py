"""Solar elevation → target color temperature. Pure math, no I/O.

The curve depends only on the sun's elevation angle, so morning and evening are
symmetric and there is no timezone or DST logic anywhere. Interpolation happens
in mired space, which is closer to perceptually uniform than kelvin.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurveParams:
    min_kelvin: int = 2700  # warm floor, at/below low_elevation_deg
    max_kelvin: int = 5500  # cool ceiling, at/above high_elevation_deg
    low_elevation_deg: float = 0.0
    high_elevation_deg: float = 15.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def kelvin_to_mireds(kelvin: float) -> float:
    return 1_000_000.0 / kelvin


def mireds_to_kelvin(mireds: float) -> float:
    return 1_000_000.0 / mireds


def target_mireds(
    elevation_deg: float,
    params: CurveParams,
    device_min_mireds: int,
    device_max_mireds: int,
) -> int:
    t = clamp(
        (elevation_deg - params.low_elevation_deg) / (params.high_elevation_deg - params.low_elevation_deg),
        0.0,
        1.0,
    )
    s = t * t * (3.0 - 2.0 * t)  # smoothstep
    warm = kelvin_to_mireds(params.min_kelvin)
    cool = kelvin_to_mireds(params.max_kelvin)
    mireds = warm + s * (cool - warm)
    return round(clamp(mireds, device_min_mireds, device_max_mireds))
