import math

from matter_adaptive_lighting.curve import CurveParams, target_mireds

DEVICE_MIN = 154  # coolest (~6500 K)
DEVICE_MAX = 370  # warmest (~2700 K)
DEFAULT = CurveParams()


def test_fully_warm_at_and_below_low_elevation():
    warmest = round(1_000_000 / DEFAULT.min_kelvin)
    for elevation in (-90, -10, -0.001, 0):
        assert target_mireds(elevation, DEFAULT, DEVICE_MIN, DEVICE_MAX) == warmest


def test_fully_cool_at_and_above_high_elevation():
    coolest = round(1_000_000 / DEFAULT.max_kelvin)
    for elevation in (15, 15.001, 45, 90):
        assert target_mireds(elevation, DEFAULT, DEVICE_MIN, DEVICE_MAX) == coolest


def test_monotonic_non_increasing_with_elevation():
    previous = math.inf
    for tenth_deg in range(-300, 400):
        mireds = target_mireds(tenth_deg / 10, DEFAULT, DEVICE_MIN, DEVICE_MAX)
        assert mireds <= previous
        previous = mireds


def test_always_within_device_range():
    tight_min, tight_max = 200, 300  # device tighter than the curve wants
    for tenth_deg in range(-900, 901, 5):
        mireds = target_mireds(tenth_deg / 10, DEFAULT, tight_min, tight_max)
        assert tight_min <= mireds <= tight_max


def test_no_nan_at_extreme_elevations():
    for elevation in (-90.0, 90.0, 0.0):
        assert isinstance(target_mireds(elevation, DEFAULT, DEVICE_MIN, DEVICE_MAX), int)


def test_custom_params_midpoint_is_between_endpoints():
    params = CurveParams(min_kelvin=3000, max_kelvin=5000, low_elevation_deg=5, high_elevation_deg=25)
    mid = target_mireds(15, params, DEVICE_MIN, DEVICE_MAX)
    assert round(1_000_000 / 5000) < mid < round(1_000_000 / 3000)
