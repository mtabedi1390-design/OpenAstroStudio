"""Tests for engine/codegen.py — graph -> executable Python source."""

from __future__ import annotations

import pytest

from astrostudio.engine.codegen import _build_call_arguments, _format_value, generate_code
from astrostudio.engine.graph import Graph, GraphCycleError
from astrostudio.engine.node import NodeInstance


@pytest.mark.parametrize("value, expected", [
    ("deg", "'deg'"),
    (10.68, "10.68"),
    (3, "3"),
    (True, "True"),
    (None, "None"),
    ([1, 2], "[1, 2]"),
])
def test_format_value(value, expected):
    assert _format_value(value) == expected


def test_generate_code_for_empty_graph():
    assert generate_code(Graph()) == ""


def test_generate_code_single_node_with_defaults(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.param_values["a"] = 1
    graph.add_node(node)

    code = generate_code(graph)
    assert code.splitlines() == [
        "from tests.conftest import add",
        "",
        f"n_{node.id} = add(a=1, b=2)  # add",
    ]


def test_generate_code_marks_unset_required_params(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    graph.add_node(node)
    code = generate_code(graph)
    assert "a=None" in code
    assert "TODO" in code
    assert "b=2" in code


def test_generate_code_wires_connections_to_variables(add_spec, double_spec):
    graph = Graph()
    producer = NodeInstance.create(add_spec)
    producer.param_values["a"] = 4
    consumer = NodeInstance.create(double_spec)
    graph.add_node(producer)
    graph.add_node(consumer)
    graph.connect(producer.id, "result", consumer.id, "value")

    code = generate_code(graph)
    assert f"n_{consumer.id} = double(value=n_{producer.id})" in code
    assert code.index(f"n_{producer.id} = add") < code.index(f"n_{consumer.id} = double")


def test_generate_code_deduplicates_imports(add_spec):
    graph = Graph()
    for _ in range(3):
        node = NodeInstance.create(add_spec)
        node.param_values["a"] = 1
        graph.add_node(node)
    code = generate_code(graph)
    assert code.count("from tests.conftest import add") == 1


def test_generate_code_keeps_distinct_imports(add_spec, double_spec):
    graph = Graph()
    graph.add_node(NodeInstance.create(add_spec))
    graph.add_node(NodeInstance.create(double_spec))
    header = generate_code(graph).split("\n\n")[0].splitlines()
    assert sorted(header) == sorted(
        ["from tests.conftest import add", "from tests.conftest import double"])


def test_generate_code_uses_node_label_as_comment(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.label = "My Adder"
    graph.add_node(node)
    assert generate_code(graph).endswith("# My Adder")


def test_generate_code_propagates_cycle_error(double_spec):
    graph = Graph()
    node = NodeInstance.create(double_spec)
    graph.add_node(node)
    graph.connect(node.id, "result", node.id, "value")
    with pytest.raises(GraphCycleError):
        generate_code(graph)


def test_generated_code_is_executable(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.param_values["a"] = 10
    graph.add_node(node)

    namespace: dict = {}
    exec(generate_code(graph), namespace)
    assert namespace[node.var_name()] == 12


def test_build_call_arguments_prefers_connection_over_stored_value(add_spec, double_spec):
    graph = Graph()
    producer = NodeInstance.create(double_spec)
    consumer = NodeInstance.create(add_spec)
    consumer.param_values["b"] = 99
    graph.add_node(producer)
    graph.add_node(consumer)
    graph.connect(producer.id, "result", consumer.id, "b")

    args = _build_call_arguments(graph, consumer)
    assert f"b=n_{producer.id}" in args
    assert "b=99" not in args


def test_build_call_arguments_omits_unset_optional_params(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.param_values.clear()
    graph.add_node(node)
    args = _build_call_arguments(graph, node)
    assert args.startswith("a=None")
    assert "b=" not in args
