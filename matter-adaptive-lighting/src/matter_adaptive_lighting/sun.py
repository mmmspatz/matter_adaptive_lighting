"""Solar elevation via astral."""

from __future__ import annotations

from datetime import datetime

from astral import Observer
from astral.sun import elevation


def elevation_degrees(when: datetime, latitude: float, longitude: float) -> float:
    return elevation(Observer(latitude=latitude, longitude=longitude), when)
