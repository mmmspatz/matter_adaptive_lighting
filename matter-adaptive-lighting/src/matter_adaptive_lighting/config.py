"""Configuration loading.

Precedence: explicit --config path → $MAL_CONFIG → /data/options.json (present
when running as a Home Assistant add-on; JSON with the same keys) → ./config.yaml.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .curve import CurveParams

ADDON_OPTIONS_PATH = "/data/options.json"


@dataclass(frozen=True)
class LightConfig:
    node_id: int
    curve_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    matter_server: str
    latitude: float
    longitude: float
    update_interval_seconds: int = 300
    transition_seconds: float = 2.0
    curve: CurveParams = CurveParams()
    lights: list[LightConfig] = field(default_factory=list)

    def curve_for(self, node_id: int) -> CurveParams:
        for light in self.lights:
            if light.node_id == node_id and light.curve_overrides:
                return replace(self.curve, **light.curve_overrides)
        return self.curve


class ConfigError(Exception):
    pass


def _find_config_path(explicit: str | None) -> Path:
    candidates = [explicit, os.environ.get("MAL_CONFIG"), ADDON_OPTIONS_PATH, "config.yaml"]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    raise ConfigError(
        "no config found: pass --config, set $MAL_CONFIG, or create ./config.yaml (see config.example.yaml)"
    )


def load_config(explicit_path: str | None = None) -> Config:
    path = _find_config_path(explicit_path)
    raw = json.loads(path.read_text()) if path.suffix == ".json" else yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping")
    try:
        curve = CurveParams(**(raw.get("curve") or {}))
        # Per-light curve overrides are flat optional keys on the light entry
        # (the HA add-on schema can't express an optional nested mapping in a list).
        override_keys = ("min_kelvin", "max_kelvin", "low_elevation_deg", "high_elevation_deg")
        lights = [
            LightConfig(
                node_id=int(entry["node_id"]),
                curve_overrides={key: entry[key] for key in override_keys if entry.get(key) is not None},
            )
            for entry in raw.get("lights") or []
        ]
        config = Config(
            matter_server=raw["matter_server"],
            latitude=float(raw["latitude"]),
            longitude=float(raw["longitude"]),
            update_interval_seconds=int(raw.get("update_interval_seconds", 300)),
            transition_seconds=float(raw.get("transition_seconds", 2.0)),
            curve=curve,
            lights=lights,
        )
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigError(f"{path}: {err}") from err
    _validate(config, path)
    return config


def _validate(config: Config, path: Path) -> None:
    problems = []
    if not -90 <= config.latitude <= 90:
        problems.append("latitude out of range")
    if not -180 <= config.longitude <= 180:
        problems.append("longitude out of range")
    if config.update_interval_seconds < 10:
        problems.append("update_interval_seconds must be >= 10")
    if config.transition_seconds < 0:
        problems.append("transition_seconds must be >= 0")
    for curve in [config.curve] + [config.curve_for(light.node_id) for light in config.lights]:
        if not 1000 <= curve.min_kelvin < curve.max_kelvin <= 20000:
            problems.append(f"kelvin range invalid: {curve.min_kelvin}..{curve.max_kelvin}")
        if curve.high_elevation_deg <= curve.low_elevation_deg:
            problems.append("high_elevation_deg must exceed low_elevation_deg")
    if problems:
        raise ConfigError(f"{path}: " + "; ".join(sorted(set(problems))))
