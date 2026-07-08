import pytest

from matter_adaptive_lighting.config import ConfigError, load_config

VALID = """
matter_server: ws://example:5580/ws
latitude: 42.4
longitude: -71.1
lights:
  - node_id: 5
  - node_id: 7
    max_kelvin: 5000
"""


def test_load_valid_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(VALID)
    config = load_config(str(path))
    assert config.matter_server == "ws://example:5580/ws"
    assert config.update_interval_seconds == 300
    assert [light.node_id for light in config.lights] == [5, 7]
    assert config.curve_for(5).max_kelvin == 5500
    assert config.curve_for(7).max_kelvin == 5000


def test_load_addon_options_json(tmp_path):
    path = tmp_path / "options.json"
    path.write_text(
        '{"matter_server": "ws://core-matter-server:5580/ws", '
        '"latitude": 1, "longitude": 2, "lights": [{"node_id": 3}]}'
    )
    config = load_config(str(path))
    assert config.matter_server == "ws://core-matter-server:5580/ws"


@pytest.mark.parametrize(
    "override",
    [
        "latitude: 91",
        "update_interval_seconds: 1",
        "curve: { min_kelvin: 6000, max_kelvin: 3000 }",
        "curve: { low_elevation_deg: 20, high_elevation_deg: 10 }",
    ],
)
def test_invalid_configs_rejected(tmp_path, override):
    path = tmp_path / "config.yaml"
    path.write_text(VALID + "\n" + override)
    with pytest.raises(ConfigError):
        load_config(str(path))


def test_missing_config_has_helpful_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MAL_CONFIG", raising=False)
    with pytest.raises(ConfigError, match="config.example.yaml"):
        load_config(None)
