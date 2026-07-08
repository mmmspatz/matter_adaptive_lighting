# Matter Adaptive Lighting

Keeps Matter CCT lights at a sun-appropriate color temperature — warm below the
horizon, cool at midday — while **never touching on/off or brightness**. Turn
your lights on and off however you like (wall switch, Home Assistant, Alexa,
Google); whenever they're on, they're the right temperature. Color temperature
is even maintained while a light is off (Matter `ExecuteIfOff`), so it comes on
correct.

It works by speaking the [Home Assistant Matter Server](https://github.com/matter-js/matterjs-server)
WebSocket API and sending raw `moveToColorTemperature` cluster commands through
the fabric HA already owns: no extra fabric on your devices, no commissioning,
no persistent state, and HA's entity/automation layer is bypassed entirely.

The target curve is a pure function of solar elevation at your lat/lon
(smoothstep between a warm floor and cool ceiling, interpolated in mired
space), so mornings and evenings are symmetric and there is no timezone or
schedule logic anywhere.

## Running

As a **local Home Assistant add-on** (the intended deployment): copy
`matter-adaptive-lighting/` into `/addons` and install "Matter Adaptive
Lighting" from Local add-ons. Configure lights and curve in the add-on options
UI. See AGENTS.md for the exact deploy runbook.

For development, bare-metal with pyenv:

```sh
pyenv exec python -m venv .venv
.venv/bin/pip install -e "./matter-adaptive-lighting[dev]"
cp matter-adaptive-lighting/config.example.yaml config.yaml   # edit
.venv/bin/python -m matter_adaptive_lighting list   # find your node ids
.venv/bin/python -m matter_adaptive_lighting set 2700 --node 59
.venv/bin/python -m matter_adaptive_lighting run
```
