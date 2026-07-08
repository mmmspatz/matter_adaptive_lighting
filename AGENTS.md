# matter_adaptive_lighting

A single-purpose daemon that keeps Matter CCT lights at a sun-appropriate color
temperature. It **never** touches on/off or brightness — lights are controlled
normally by Home Assistant / Alexa / Google / wall switches; whenever they
happen to be on, they're the right temperature.

## Architecture

Stateless WebSocket client of the **Home Assistant Matter Server add-on**
(`core_matter_server`, the matter.js-based v9.x line) on port 5580. It sends raw
Matter `moveToColorTemperature` cluster commands with `ExecuteIfOff` through the
fabric HA already owns — bypassing HA's entity/automation layer entirely (HA
entities can't set CT while a light is off; raw cluster commands can). No fabric
slot consumed, no commissioning, no persistent state.

Ships as a **local HA add-on**: `matter-adaptive-lighting/` is the add-on folder
(manifest `config.yaml` + `Dockerfile`); the repo root is an installable HA
add-on repository (`repository.yaml`).

## Layout

- `matter-adaptive-lighting/src/matter_adaptive_lighting/` — the Python package
  - `ws.py` — all Matter Server WS API touchpoints live here (isolated on purpose)
  - `lights.py` — CT-light discovery from the node dump
  - `curve.py` — pure solar-elevation → mireds math (smoothstep in mired space)
  - `sun.py`, `config.py`, `daemon.py`, `__main__.py`
- `matter-adaptive-lighting/tests/` — pytest (pure code only, no network)

## Dev environment

Host python is quirky — always use pyenv (pinned via `.python-version`, 3.12.x):

```sh
pyenv exec python -m venv .venv
.venv/bin/pip install -e "./matter-adaptive-lighting[dev]"
.venv/bin/pytest matter-adaptive-lighting/tests
.venv/bin/ruff check matter-adaptive-lighting        # lint
.venv/bin/ruff format matter-adaptive-lighting       # format (line-length 120)
.venv/bin/ty check matter-adaptive-lighting          # type check
```

Build backend is `uv_build`; `ty` is Astral's (still 0.0.x, pre-1.0) type
checker. Config for all three lives in `pyproject.toml`.

Dev config: copy `matter-adaptive-lighting/config.example.yaml` to
`./config.yaml` (gitignored). CLI:

```sh
.venv/bin/python -m matter_adaptive_lighting list        # discover CT lights + node ids
.venv/bin/python -m matter_adaptive_lighting set 2700 --node 5
.venv/bin/python -m matter_adaptive_lighting run         # the daemon
```

## Home network facts

- HA: `homeassistant.local` (HAOS on Pi 4, aarch64). SSH: `root@…:22`
  (has `ha` CLI, `/addons`, `/config`). Matter Server WS API:
  `ws://homeassistant.local:5580/ws` from the LAN,
  `ws://core-matter-server:5580/ws` from inside an add-on.
- Location for the sun math comes from HA core config (your configured lat/lon).
- First target lights: ESP32 under-cabinet CCT strips running
  `~/code/esp32_matter_led_controller` (Zephyr + connectedhomeip):
  - mired range **154–370** (~6500–2700 K); out-of-range writes clamp silently
  - CT written while OFF is stored and applied at next power-on;
    `colorTemperatureMireds` persists across power cycles
  - max 4 fabrics (HA + Alexa + Google occupy 3) — another reason this project
    deliberately does NOT commission its own fabric
  - test VID/PID `0xFFF1`/`0x8005`

## Matter Server WS API notes

Docs: `matter-js/matterjs-server` → `docs/websockets_api.md`. Requests are
`{"message_id", "command", "args"}`; responses echo `message_id` with `result`
or `error_code`. `get_nodes` returns node dicts whose `attributes` map is keyed
`"endpoint/cluster/attribute"` (decimal), e.g. `"1/768/7"` =
ColorTemperatureMireds. Multiple concurrent WS clients are fine (HA is one).
The API aims to stay python-matter-server-compatible but the add-on is beta —
if something breaks after an add-on update, look at `ws.py` first.

## Deploying the add-on

The HAOS SSH add-on has no rsync — use tar. Ship only runtime files: the
supervisor tries to parse every yaml in the folder, so `config.example.yaml`
must NOT be copied (and tests are dead weight). Supervisor 2026 renamed the CLI
`addons` → `apps`, and the store rescan is `ha store reload` (NOT `ha apps
reload`, which just lists).

```sh
tar -C matter-adaptive-lighting --exclude='*.egg-info' --exclude=__pycache__ \
    --exclude=tests --exclude=config.example.yaml -czf - . \
  | ssh root@homeassistant.local \
    'rm -rf /addons/matter-adaptive-lighting && mkdir -p /addons/matter-adaptive-lighting \
     && tar -C /addons/matter-adaptive-lighting -xzf - \
     && ha store reload && sleep 4 \
     && ha apps rebuild local_matter_adaptive_lighting \
     && ha apps start local_matter_adaptive_lighting'
ssh root@homeassistant.local 'ha apps logs local_matter_adaptive_lighting'
```

Add-on options (HA UI) mirror `config.example.yaml` except per-light curve
overrides are FLAT optional keys on each light entry (`max_kelvin: 5000`, not a
nested `curve:` mapping) — the supervisor schema can't express an optional
nested mapping inside a list. Options arrive in the container as
`/data/options.json`.
