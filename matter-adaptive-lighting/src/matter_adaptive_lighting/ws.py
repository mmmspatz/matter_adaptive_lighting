"""Minimal client for the Home Assistant Matter Server WebSocket API.

The API (matterjs-server, formerly python-matter-server) is JSON over a single
WebSocket: requests carry a client-chosen ``message_id`` and the response echoes
it back with either a ``result`` or an ``error_code``. Unsolicited event
messages (attribute updates after ``start_listening``) carry no matching
``message_id`` and are skipped while waiting for a response.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 60
# start_listening dumps every attribute of every node on the fabric
MAX_MESSAGE_BYTES = 32 * 1024 * 1024


class MatterServerError(Exception):
    def __init__(self, error_code: Any, details: Any):
        super().__init__(f"matter server error {error_code}: {details}")
        self.error_code = error_code
        self.details = details


class MatterClient:
    """One connection, sequential request/response."""

    def __init__(self, url: str):
        self.url = url
        self.server_info: dict[str, Any] | None = None
        self._ws: Any = None
        self._next_id = 0

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.url, max_size=MAX_MESSAGE_BYTES)
        # The server announces itself unprompted on connect.
        self.server_info = json.loads(await self._ws.recv())
        log.debug("connected to %s: %s", self.url, self.server_info)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> MatterClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def request(self, command: str, args: dict[str, Any] | None = None) -> Any:
        if self._ws is None:
            raise RuntimeError("not connected")
        self._next_id += 1
        message_id = str(self._next_id)
        message: dict[str, Any] = {"message_id": message_id, "command": command}
        if args is not None:
            message["args"] = args
        await self._ws.send(json.dumps(message))
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            while True:
                data = json.loads(await self._ws.recv())
                if data.get("message_id") != message_id:
                    continue  # event or unrelated message
                if data.get("error_code") is not None:
                    raise MatterServerError(data["error_code"], data.get("details"))
                return data.get("result")

    async def get_nodes(self) -> list[dict[str, Any]]:
        return await self.request("get_nodes")

    async def start_listening(self) -> list[dict[str, Any]]:
        return await self.request("start_listening")

    async def device_command(
        self,
        node_id: int,
        endpoint_id: int,
        cluster_id: int,
        command_name: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self.request(
            "device_command",
            {
                "node_id": node_id,
                "endpoint_id": endpoint_id,
                "cluster_id": cluster_id,
                "command_name": command_name,
                "payload": payload or {},
            },
        )

    async def read_attribute(self, node_id: int, attribute_path: str) -> Any:
        return await self.request(
            "read_attribute",
            {"node_id": node_id, "attribute_path": attribute_path},
        )
