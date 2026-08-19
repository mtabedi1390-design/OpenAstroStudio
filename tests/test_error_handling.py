"""
tests/test_error_handling.py
-----------------------------
تست‌های مربوط به گزارش خطا: هدف این است که هیچ خطایی در سکوت دور ریخته نشود.

اجرا:
    python -m pytest tests
"""

from __future__ import annotations

import math

import pytest

from astrostudio.engine.codegen import generate_code
from astrostudio.engine.errors import (
    GraphCycleError,
    InvalidConnectionError,
    MissingParameterError,
    NodeExecutionError,
    ReflectionError,
)
from astrostudio.engine.executor import execute_direct, execute_generated_code
from astrostudio.engine.graph import Graph
from astrostudio.engine.library_scanner import scan_callable_list
from astrostudio.engine.node import Connection, NodeInstance
from astrostudio.engine.reflection import reflect


def add(a: int, b: int = 1) -> int:
    """جمع دو عدد.

    Parameters
    ----------
    a : int
        عدد اول.
    b : int
        عدد دوم.
    """
    return a + b


def boom(a: int) -> int:
    """همیشه خطا می‌دهد."""
    raise RuntimeError("منفجر شد")


def graph_with(*callables) -> tuple[Graph, list[NodeInstance]]:
    graph = Graph()
    nodes = []
    for c in callables:
        node = NodeInstance.create(reflect(c, category="tests"))
        graph.add_node(node)
        nodes.append(node)
    return graph, nodes


# ---------- reflection ----------


def test_reflect_unreadable_signature_raises():
    with pytest.raises(ReflectionError):
        reflect(math.log)


def test_scan_collects_errors_instead_of_dropping_them():
    errors: list[tuple[str, Exception]] = []
    specs = scan_callable_list([add, math.log], category="tests", errors=errors)
    assert [s.callable_ref for s in specs] == [add]
    assert len(errors) == 1
    assert isinstance(errors[0][1], ReflectionError)


def test_scan_strict_propagates():
    with pytest.raises(ReflectionError):
        scan_callable_list([math.log], category="tests", strict=True)


# ---------- graph ----------


def test_connect_unknown_node_raises():
    graph, (node,) = graph_with(add)
    with pytest.raises(InvalidConnectionError):
        graph.connect(node.id, "result", "node_missing", "a")


def test_connect_unknown_port_raises():
    graph, (src, dst) = graph_with(add, add)
    with pytest.raises(InvalidConnectionError):
        graph.connect(src.id, "no_such_output", dst.id, "a")
    with pytest.raises(InvalidConnectionError):
        graph.connect(src.id, "result", dst.id, "no_such_input")


def test_connect_to_self_raises():
    graph, (node,) = graph_with(add)
    with pytest.raises(InvalidConnectionError):
        graph.connect(node.id, "result", node.id, "a")


def test_dangling_connection_detected_by_validate():
    graph, (src, dst) = graph_with(add, add)
    graph.connect(src.id, "result", dst.id, "a")
    graph.nodes.pop(src.id)  # شبیه‌سازی یک وضعیت ناسازگار
    with pytest.raises(InvalidConnectionError):
        graph.validate()


def test_cycle_reports_involved_nodes():
    graph, (first, second) = graph_with(add, add)
    graph.connect(first.id, "result", second.id, "a")
    conn = Connection.create(second.id, "result", first.id, "a")
    graph.connections[conn.id] = conn
    with pytest.raises(GraphCycleError) as excinfo:
        graph.execution_order()
    assert first.label in str(excinfo.value)


# ---------- execution ----------


def test_missing_required_param_is_reported():
    graph, (node,) = graph_with(add)
    result = execute_direct(graph)
    assert not result.success
    assert isinstance(result.exception, MissingParameterError)
    assert result.error_node_id == node.id
    assert "a" in result.error


def test_explicit_none_for_required_param_counts_as_missing():
    graph, (node,) = graph_with(add)
    node.param_values["a"] = None
    result = execute_direct(graph)
    assert isinstance(result.exception, MissingParameterError)


def test_node_failure_keeps_context_and_partial_results():
    graph, (first, second) = graph_with(add, boom)
    first.param_values["a"] = 1
    graph.connect(first.id, "result", second.id, "a")

    result = execute_direct(graph)
    assert not result.success
    assert result.error_node_id == second.id
    assert isinstance(result.exception, NodeExecutionError)
    assert isinstance(result.exception.original, RuntimeError)
    assert result.results == {first.id: 2}
    assert "منفجر شد" in result.traceback_text


def test_cycle_is_reported_as_result_not_raised():
    graph, (first, second) = graph_with(add, add)
    graph.connect(first.id, "result", second.id, "a")
    conn = Connection.create(second.id, "result", first.id, "a")
    graph.connections[conn.id] = conn

    result = execute_direct(graph)
    assert not result.success
    assert isinstance(result.exception, GraphCycleError)


def test_raise_if_failed_propagates_original():
    graph, (node,) = graph_with(boom)
    node.param_values["a"] = 1
    with pytest.raises(NodeExecutionError):
        execute_direct(graph).raise_if_failed()


def test_raise_if_failed_returns_result_on_success():
    graph, (node,) = graph_with(add)
    node.param_values["a"] = 2
    result = execute_direct(graph).raise_if_failed()
    assert result.results[node.id] == 3


# ---------- generated code ----------


def test_generated_code_marks_missing_params_without_breaking_syntax():
    graph, _ = graph_with(add)
    code = generate_code(graph)
    compile(code, "<generated>", "exec")
    assert "TODO" in code


def test_execute_generated_code_reports_failure():
    graph, (node,) = graph_with(boom)
    node.param_values["a"] = 1
    result = execute_generated_code(graph)
    assert not result.success
    assert "منفجر شد" in result.error
    assert result.results == {}


def test_execute_generated_code_success():
    graph, (node,) = graph_with(add)
    node.param_values["a"] = 5
    result = execute_generated_code(graph)
    assert result.success
    assert result.results[node.id] == 6
