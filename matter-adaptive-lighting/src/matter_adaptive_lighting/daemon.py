"""The adaptive-lighting loop.

Sends moveToColorTemperature to every configured light on a fixed interval,
always with ExecuteIfOff so color temperature is maintained (and stored by the
device) even while the light is off. Never touches on/off or brightness.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from .config import Config
from .curve import target_mireds
from .lights import CLUSTER_COLOR_CONTROL, CtLight, ct_lights_from_nodes
from .sun import elevation_degrees
from .ws import MatterClient

log = logging.getLogger(__name__)

INITIAL_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 300

# ColorControl Options bitmap, bit 0
EXECUTE_IF_OFF = 1


async def send_color_temperature(client: MatterClient, light: CtLight, mireds: int, transition_seconds: float) -> None:
    await client.device_command(
        node_id=light.node_id,
        endpoint_id=light.endpoint_id,
        cluster_id=CLUSTER_COLOR_CONTROL,
        command_name="moveToColorTemperature",
        payload={
            "colorTemperatureMireds": mireds,
            "transitionTime": round(transition_seconds * 10),
            "optionsMask": EXECUTE_IF_OFF,
            "optionsOverride": EXECUTE_IF_OFF,
        },
    )


def resolve_lights(config: Config, nodes: list[dict]) -> list[CtLight]:
    discovered = {light.node_id: light for light in ct_lights_from_nodes(nodes)}
    lights = []
    for entry in config.lights:
        light = discovered.get(entry.node_id)
        if light is None:
            log.warning("configured node %s has no CT light on the fabric; skipping", entry.node_id)
            continue
        lights.append(light)
    return lights


async def _tick(
    client: MatterClient,
    config: Config,
    lights: list[CtLight],
    ok: dict[int, bool],
    last_sent: dict[int, int],
) -> None:
    elevation = elevation_degrees(datetime.now(UTC), config.latitude, config.longitude)
    for light in lights:
        mireds = target_mireds(elevation, config.curve_for(light.node_id), light.min_mireds, light.max_mireds)
        try:
            await send_color_temperature(client, light, mireds, config.transition_seconds)
        except Exception as err:
            if ok.get(light.node_id, True):
                log.warning("node %s (%s): update failed: %s", light.node_id, light.name, err)
            else:
                log.debug("node %s still failing: %s", light.node_id, err)
            ok[light.node_id] = False
            continue
        if not ok.get(light.node_id, True):
            log.info("node %s (%s) recovered", light.node_id, light.name)
        ok[light.node_id] = True
        # INFO only when the target moves, so the log traces the sunrise/sunset
        # ramps and is otherwise silent.
        level = logging.DEBUG if last_sent.get(light.node_id) == mireds else logging.INFO
        last_sent[light.node_id] = mireds
        log.log(
            level,
            "node %s (%s): elevation %.1f° → %d mireds (%.0f K)",
            light.node_id,
            light.name,
            elevation,
            mireds,
            1_000_000 / mireds,
        )


async def run_daemon(config: Config) -> None:
    backoff = INITIAL_BACKOFF_SECONDS
    while True:
        try:
            async with MatterClient(config.matter_server) as client:
                nodes = await client.get_nodes()
                lights = resolve_lights(config, nodes)
                if not lights:
                    raise RuntimeError("no configured lights found on the fabric")
                log.info(
                    "maintaining %d light(s): %s",
                    len(lights),
                    ", ".join(f"{light.node_id} ({light.name})" for light in lights),
                )
                backoff = INITIAL_BACKOFF_SECONDS
                ok: dict[int, bool] = {}
                last_sent: dict[int, int] = {}
                while True:
                    await _tick(client, config, lights, ok, last_sent)
                    await asyncio.sleep(config.update_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            log.warning("matter server connection lost (%s); retrying in %ds", err, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
