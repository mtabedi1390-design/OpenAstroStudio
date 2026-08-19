"""Tests for engine/node.py — dataclass defaults, id generation and helpers."""

from __future__ import annotations

from astrostudio.engine.node import (
    Connection,
    NodeInstance,
    ParamSpec,
    PortSpec,
    _next_id,
)


def test_param_spec_defaults():
    param = ParamSpec(name="ra")
    assert param.annotation == "Any"
    assert param.default is None
    assert param.has_default is False
    assert param.required is True
    assert param.description == ""
    assert param.kind == "POSITIONAL_OR_KEYWORD"


def test_port_spec_defaults():
    port = PortSpec(name="result")
    assert port.annotation == "Any"
    assert port.direction == "in"


def test_next_id_uses_prefix_and_increments():
    first = _next_id("thing")
    second = _next_id("thing")
    assert first.startswith("thing_")
    assert first != second
    assert int(second.split("_")[1]) > int(first.split("_")[1])


def test_connection_create_fills_ids_and_ports():
    conn = Connection.create("src", "result", "dst", "value")
    assert conn.id.startswith("conn_")
    assert (conn.source_node_id, conn.source_port) == ("src", "result")
    assert (conn.target_node_id, conn.target_port) == ("dst", "value")


def test_connection_create_generates_unique_ids():
    ids = {Connection.create("a", "result", "b", "value").id for _ in range(5)}
    assert len(ids) == 5


def test_node_instance_create_seeds_only_defaulted_params(add_spec):
    node = NodeInstance.create(add_spec, position=(10.0, 20.0))
    assert node.id.startswith("node_")
    assert node.param_values == {"b": 2}
    assert node.position == (10.0, 20.0)
    assert node.label == add_spec.display_name
    assert node.spec is add_spec


def test_node_instance_create_defaults_to_origin(add_spec):
    assert NodeInstance.create(add_spec).position == (0.0, 0.0)


def test_node_instance_create_returns_independent_param_values(add_spec):
    first = NodeInstance.create(add_spec)
    second = NodeInstance.create(add_spec)
    first.param_values["b"] = 99
    assert second.param_values["b"] == 2


def test_var_name_derives_from_id(add_spec):
    node = NodeInstance.create(add_spec)
    assert node.var_name() == f"n_{node.id}"
    assert node.var_name().isidentifier()
