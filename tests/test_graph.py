"""Tests for engine/graph.py — graph mutation, queries and the dependency solver."""

from __future__ import annotations

import pytest

from astrostudio.engine.graph import Graph, GraphCycleError
from astrostudio.engine.node import Connection, NodeInstance


@pytest.fixture
def chain(add_spec, double_spec):
    """A --> B chain: add -> double, connected on the `value` port."""
    graph = Graph()
    first = NodeInstance.create(add_spec)
    second = NodeInstance.create(double_spec)
    graph.add_node(first)
    graph.add_node(second)
    conn = graph.connect(first.id, "result", second.id, "value")
    return graph, first, second, conn


def test_empty_graph():
    graph = Graph()
    assert graph.nodes == {}
    assert graph.connections == {}
    assert graph.execution_order() == []


def test_add_node_indexes_by_id(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    graph.add_node(node)
    assert graph.nodes == {node.id: node}


def test_remove_node_also_removes_its_connections(chain):
    graph, first, second, _ = chain
    graph.remove_node(first.id)
    assert first.id not in graph.nodes
    assert graph.connections == {}
    assert second.id in graph.nodes


def test_remove_unknown_node_is_a_noop(add_spec):
    graph = Graph()
    graph.remove_node("does_not_exist")
    assert graph.nodes == {}


def test_connect_requires_both_nodes_present(add_spec, double_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    graph.add_node(node)
    with pytest.raises(KeyError):
        graph.connect(node.id, "result", "missing", "value")
    with pytest.raises(KeyError):
        graph.connect("missing", "result", node.id, "a")
    assert graph.connections == {}


def test_connect_registers_connection(chain):
    graph, first, second, conn = chain
    assert graph.connections[conn.id] is conn
    assert isinstance(conn, Connection)
    assert (conn.source_node_id, conn.target_port) == (first.id, "value")


def test_disconnect_removes_connection(chain):
    graph, _, _, conn = chain
    graph.disconnect(conn.id)
    assert graph.connections == {}


def test_disconnect_unknown_connection_is_a_noop(chain):
    graph, _, _, _ = chain
    graph.disconnect("conn_missing")
    assert len(graph.connections) == 1


def test_incoming_and_outgoing_connections(chain):
    graph, first, second, conn = chain
    assert graph.outgoing_connections(first.id) == [conn]
    assert graph.incoming_connections(first.id) == []
    assert graph.incoming_connections(second.id) == [conn]
    assert graph.outgoing_connections(second.id) == []


def test_execution_order_respects_dependencies(chain):
    graph, first, second, _ = chain
    assert [n.id for n in graph.execution_order()] == [first.id, second.id]


def test_execution_order_handles_diamond(add_spec, double_spec):
    graph = Graph()
    source = NodeInstance.create(double_spec)
    left = NodeInstance.create(double_spec)
    right = NodeInstance.create(double_spec)
    sink = NodeInstance.create(add_spec)
    for node in (source, left, right, sink):
        graph.add_node(node)
    graph.connect(source.id, "result", left.id, "value")
    graph.connect(source.id, "result", right.id, "value")
    graph.connect(left.id, "result", sink.id, "a")
    graph.connect(right.id, "result", sink.id, "b")

    order = [n.id for n in graph.execution_order()]
    assert order[0] == source.id
    assert order[-1] == sink.id
    assert set(order[1:3]) == {left.id, right.id}


def test_execution_order_is_deterministic(add_spec, double_spec):
    def build():
        graph = Graph()
        nodes = [NodeInstance.create(double_spec) for _ in range(3)]
        for node in nodes:
            graph.add_node(node)
        graph.connect(nodes[0].id, "result", nodes[1].id, "value")
        return graph

    first_order = [n.id for n in build().execution_order()]
    assert first_order == sorted(first_order, key=first_order.index)
    graph = build()
    assert [n.id for n in graph.execution_order()] == [
        n.id for n in graph.execution_order()]


def test_execution_order_detects_cycle(double_spec):
    graph = Graph()
    a = NodeInstance.create(double_spec)
    b = NodeInstance.create(double_spec)
    graph.add_node(a)
    graph.add_node(b)
    graph.connect(a.id, "result", b.id, "value")
    graph.connect(b.id, "result", a.id, "value")
    with pytest.raises(GraphCycleError):
        graph.execution_order()


def test_execution_order_detects_self_loop(double_spec):
    graph = Graph()
    node = NodeInstance.create(double_spec)
    graph.add_node(node)
    graph.connect(node.id, "result", node.id, "value")
    with pytest.raises(GraphCycleError):
        graph.execution_order()


def test_to_dict_serializes_nodes_and_connections(chain):
    graph, first, second, conn = chain
    first.param_values["a"] = 5
    first.position = (12.0, 34.0)

    data = graph.to_dict()
    assert set(data) == {"nodes", "connections"}
    assert data["nodes"][first.id] == {
        "spec_id": first.spec.id,
        "param_values": first.param_values,
        "position": (12.0, 34.0),
        "label": first.label,
    }
    assert data["connections"][conn.id] == {
        "source_node_id": first.id,
        "source_port": "result",
        "target_node_id": second.id,
        "target_port": "value",
    }


def test_to_dict_on_empty_graph():
    assert Graph().to_dict() == {"nodes": {}, "connections": {}}
