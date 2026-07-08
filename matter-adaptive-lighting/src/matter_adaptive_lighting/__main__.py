"""CLI: list / set / run."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from .config import Config, ConfigError, load_config
from .curve import kelvin_to_mireds
from .daemon import run_daemon, send_color_temperature
from .lights import ct_lights_from_nodes
from .ws import MatterClient

log = logging.getLogger("matter_adaptive_lighting")


async def cmd_list(config: Config) -> None:
    async with MatterClient(config.matter_server) as client:
        lights = ct_lights_from_nodes(await client.get_nodes())
    if not lights:
        print("no CT-capable lights found on the fabric")
        return
    configured = {entry.node_id for entry in config.lights}
    print(f"{'node':>6}  {'ep':>3}  {'mireds':>9}  {'now':>11}  {'state':>5}  name")
    for light in lights:
        now = f"{light.current_mireds} ({1_000_000 // light.current_mireds} K)" if light.current_mireds else "?"
        state = ("on" if light.is_on else "off") if light.is_on is not None else "?"
        if not light.available:
            state = "unavail"
        marker = "*" if light.node_id in configured else " "
        print(
            f"{light.node_id:>6}{marker} {light.endpoint_id:>3}  "
            f"{light.min_mireds:>4}-{light.max_mireds:<4} {now:>11}  {state:>5}  "
            f"{light.name} ({light.vendor_name} {light.product_name})"
        )
    if configured:
        print("* = in config")


async def cmd_set(config: Config, value: int, is_mireds: bool, node: int | None, transition: float) -> None:
    mireds = value if is_mireds else round(kelvin_to_mireds(value))
    async with MatterClient(config.matter_server) as client:
        lights = ct_lights_from_nodes(await client.get_nodes())
        configured = {entry.node_id for entry in config.lights}
        if node is not None:
            targets = [light for light in lights if light.node_id == node]
        elif configured:
            targets = [light for light in lights if light.node_id in configured]
        else:
            targets = lights
        if not targets:
            sys.exit(f"no matching CT light (asked for node {node})")
        for light in targets:
            clamped = max(light.min_mireds, min(light.max_mireds, mireds))
            await send_color_temperature(client, light, clamped, transition)
            print(f"node {light.node_id} ({light.name}): → {clamped} mireds ({1_000_000 // clamped} K)")


async def cmd_run(config: Config) -> None:
    task = asyncio.ensure_future(run_daemon(config))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        log.info("shutting down")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="matter_adaptive_lighting",
        description="Sun-tracking color temperature for Matter CCT lights",
    )
    parser.add_argument("--config", help="config file path (default: $MAL_CONFIG, /data/options.json, ./config.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show CT-capable lights on the fabric")
    set_parser = sub.add_parser("set", help="manually set color temperature (verification tool)")
    set_parser.add_argument("value", type=int, help="kelvin (or mireds with --mireds)")
    set_parser.add_argument("--mireds", action="store_true")
    set_parser.add_argument("--node", type=int, help="single node id (default: configured lights)")
    set_parser.add_argument("--transition", type=float, default=2.0, help="seconds")
    sub.add_parser("run", help="run the adaptive daemon")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not args.verbose:
        logging.getLogger("websockets").setLevel(logging.WARNING)

    try:
        config = load_config(args.config)
    except ConfigError as err:
        sys.exit(str(err))

    if args.command == "list":
        asyncio.run(cmd_list(config))
    elif args.command == "set":
        asyncio.run(cmd_set(config, args.value, args.mireds, args.node, args.transition))
    elif args.command == "run":
        asyncio.run(cmd_run(config))


if __name__ == "__main__":
    main()
