from matter_adaptive_lighting.lights import ct_lights_from_nodes


def make_node(node_id, attributes, available=True):
    return {"node_id": node_id, "available": available, "attributes": attributes}


CCT_LIGHT_ATTRS = {
    "0/40/1": "LeafLabs",
    "0/40/3": "BTF WLED CCT",
    "0/40/5": "Under Cabinet",
    "1/6/0": True,
    "1/768/7": 250,
    "1/768/16394": 16,  # ColorTemperature capability only
    "1/768/16395": 154,
    "1/768/16396": 370,
}

HUE_ONLY_LIGHT_ATTRS = {
    "0/40/3": "RGB Bulb",
    "1/6/0": False,
    "1/768/16394": 9,  # HueSaturation + XY, no CT bit
    "1/768/1": 0,
}

NO_COLOR_ATTRS = {
    "0/40/3": "Smart Plug",
    "1/6/0": True,
}


def test_discovers_cct_light_with_range_and_state():
    lights = ct_lights_from_nodes([make_node(5, CCT_LIGHT_ATTRS)])
    assert len(lights) == 1
    light = lights[0]
    assert (light.node_id, light.endpoint_id) == (5, 1)
    assert (light.min_mireds, light.max_mireds) == (154, 370)
    assert light.current_mireds == 250
    assert light.is_on is True
    assert light.name == "Under Cabinet"
    assert light.available


def test_skips_lights_without_ct_capability():
    nodes = [make_node(1, HUE_ONLY_LIGHT_ATTRS), make_node(2, NO_COLOR_ATTRS)]
    assert ct_lights_from_nodes(nodes) == []


def test_multiple_nodes_mixed():
    nodes = [
        make_node(1, HUE_ONLY_LIGHT_ATTRS),
        make_node(2, CCT_LIGHT_ATTRS),
        make_node(3, CCT_LIGHT_ATTRS, available=False),
    ]
    lights = ct_lights_from_nodes(nodes)
    assert [light.node_id for light in lights] == [2, 3]
    assert lights[1].available is False
