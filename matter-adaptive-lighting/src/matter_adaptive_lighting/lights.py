"""Discover CCT-capable lights from a Matter Server node dump.

Node dicts carry an ``attributes`` map keyed ``"endpoint/cluster/attribute"``
(all decimal). A light endpoint qualifies if its Color Control cluster (0x0300)
reports the ColorTemperature capability bit and exposes ColorTemperatureMireds.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

CLUSTER_ON_OFF = 6  # 0x0006
CLUSTER_COLOR_CONTROL = 768  # 0x0300

ATTR_ON_OFF = 0
ATTR_CURRENT_MIREDS = 7  # ColorTemperatureMireds
ATTR_COLOR_CAPABILITIES = 16394  # 0x400A
ATTR_MIN_MIREDS = 16395  # ColorTempPhysicalMinMireds (coolest)
ATTR_MAX_MIREDS = 16396  # ColorTempPhysicalMaxMireds (warmest)

CAP_COLOR_TEMPERATURE = 0x10

# BasicInformation on the root endpoint
_VENDOR_NAME = "0/40/1"
_PRODUCT_NAME = "0/40/3"
_NODE_LABEL = "0/40/5"


@dataclass
class CtLight:
    node_id: int
    endpoint_id: int
    name: str
    vendor_name: str
    product_name: str
    min_mireds: int
    max_mireds: int
    current_mireds: int | None
    is_on: bool | None
    available: bool


def _attr(attributes: dict[str, Any], endpoint: int, cluster: int, attribute: int) -> Any:
    return attributes.get(f"{endpoint}/{cluster}/{attribute}")


def _endpoints_with_cluster(attributes: dict[str, Any], cluster_id: int) -> set[int]:
    endpoints = set()
    for path in attributes:
        endpoint, cluster, _ = path.split("/")
        if int(cluster) == cluster_id:
            endpoints.add(int(endpoint))
    return endpoints


def ct_lights_from_nodes(nodes: list[dict[str, Any]]) -> list[CtLight]:
    lights: list[CtLight] = []
    for node in nodes:
        attributes: dict[str, Any] = node.get("attributes") or {}
        for endpoint in sorted(_endpoints_with_cluster(attributes, CLUSTER_COLOR_CONTROL)):
            attr = partial(_attr, attributes, endpoint)
            capabilities = attr(CLUSTER_COLOR_CONTROL, ATTR_COLOR_CAPABILITIES)
            current = attr(CLUSTER_COLOR_CONTROL, ATTR_CURRENT_MIREDS)
            if capabilities is None or not capabilities & CAP_COLOR_TEMPERATURE:
                continue
            if current is None:
                continue
            lights.append(
                CtLight(
                    node_id=node["node_id"],
                    endpoint_id=endpoint,
                    name=attributes.get(_NODE_LABEL) or attributes.get(_PRODUCT_NAME) or f"node {node['node_id']}",
                    vendor_name=attributes.get(_VENDOR_NAME) or "?",
                    product_name=attributes.get(_PRODUCT_NAME) or "?",
                    min_mireds=attr(CLUSTER_COLOR_CONTROL, ATTR_MIN_MIREDS) or 0,
                    max_mireds=attr(CLUSTER_COLOR_CONTROL, ATTR_MAX_MIREDS) or 65279,
                    current_mireds=current,
                    is_on=attr(CLUSTER_ON_OFF, ATTR_ON_OFF),
                    available=node.get("available", False),
                )
            )
    return lights
