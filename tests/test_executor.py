"""Tests for engine/executor.py — direct execution and generated-code execution."""

from __future__ import annotations

import pytest

from astrostudio.engine.executor import (
    ExecutionResult,
    _resolve_kwargs,
    execute_direct,
    execute_generated_code,
)
from astrostudio.engine.graph import Graph, GraphCycleError
from astrostudio.engine.node import NodeInstance

from .conftest import make_spec


def boom(value: int) -> int:
    raise ValueError("kaboom")


@pytest.fixture
def boom_spec():
    return make_spec(boom, params=[("value", False, None)],
                     import_path="from tests.test_executor import boom")


def _add_graph(add_spec, a=1):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.param_values["a"] = a
    graph.add_node(node)
    return graph, node


def test_execution_result_defaults():
    result = ExecutionResult(success=True)
    assert result.results == {}
    assert result.generated_code == ""
    assert result.error is None


def test_execute_direct_single_node(add_spec):
    graph, node = _add_graph(add_spec, a=5)
    result = execute_direct(graph)
    assert result.success is True
    assert result.error is None
    assert result.results == {node.id: 7}
    assert "add(a=5, b=2)" in result.generated_code


def test_execute_direct_passes_results_through_connections(add_spec, double_spec):
    graph = Graph()
    producer = NodeInstance.create(add_spec)
    producer.param_values["a"] = 3
    consumer = NodeInstance.create(double_spec)
    graph.add_node(producer)
    graph.add_node(consumer)
    graph.connect(producer.id, "result", consumer.id, "value")

    result = execute_direct(graph)
    assert result.results[producer.id] == 5
    assert result.results[consumer.id] == 10


def test_execute_direct_reports_failure_and_partial_results(add_spec, boom_spec):
    graph = Graph()
    ok = NodeInstance.create(add_spec)
    ok.param_values["a"] = 1
    failing = NodeInstance.create(boom_spec)
    graph.add_node(ok)
    graph.add_node(failing)
    graph.connect(ok.id, "result", failing.id, "value")

    result = execute_direct(graph)
    assert result.success is False
    assert result.error == "ValueError: kaboom"
    assert result.results == {ok.id: 3}
    assert result.generated_code


def test_execute_direct_missing_required_param_is_reported_as_error(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.param_values.clear()
    graph.add_node(node)

    result = execute_direct(graph)
    assert result.success is False
    assert "TypeError" in result.error


def test_execute_direct_on_empty_graph_succeeds():
    result = execute_direct(Graph())
    assert result.success is True
    assert result.results == {}


def test_execute_direct_propagates_cycle_error(double_spec):
    graph = Graph()
    node = NodeInstance.create(double_spec)
    graph.add_node(node)
    graph.connect(node.id, "result", node.id, "value")
    with pytest.raises(GraphCycleError):
        execute_direct(graph)


def test_resolve_kwargs_uses_connection_result_over_param_value(add_spec, double_spec):
    graph = Graph()
    producer = NodeInstance.create(double_spec)
    consumer = NodeInstance.create(add_spec)
    consumer.param_values.update({"a": 1, "b": 2})
    graph.add_node(producer)
    graph.add_node(consumer)
    graph.connect(producer.id, "result", consumer.id, "b")

    kwargs = _resolve_kwargs(graph, consumer, {producer.id: 42})
    assert kwargs == {"a": 1, "b": 42}


def test_resolve_kwargs_skips_params_without_value(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    graph.add_node(node)
    assert _resolve_kwargs(graph, node, {}) == {"b": 2}


def test_execute_generated_code_matches_direct_execution(add_spec, double_spec):
    graph = Graph()
    producer = NodeInstance.create(add_spec)
    producer.param_values["a"] = 4
    consumer = NodeInstance.create(double_spec)
    graph.add_node(producer)
    graph.add_node(consumer)
    graph.connect(producer.id, "result", consumer.id, "value")

    generated = execute_generated_code(graph)
    direct = execute_direct(graph)
    assert generated.success is True
    assert generated.results == direct.results
    assert generated.generated_code == direct.generated_code


def test_execute_generated_code_reports_runtime_error(boom_spec):
    graph = Graph()
    node = NodeInstance.create(boom_spec)
    node.param_values["value"] = 1
    graph.add_node(node)

    result = execute_generated_code(graph)
    assert result.success is False
    assert result.error == "ValueError: kaboom"
    assert result.results == {}
    assert "boom(value=1)" in result.generated_code


def test_execute_generated_code_reports_syntax_error(add_spec):
    graph = Graph()
    node = NodeInstance.create(add_spec)
    node.param_values["a"] = 1
    broken_spec = make_spec(add_spec.callable_ref,
                            params=[("a", False, None)],
                            import_path="this is not valid python")
    node.spec = broken_spec
    graph.add_node(node)

    result = execute_generated_code(graph)
    assert result.success is False
    assert "SyntaxError" in result.error
