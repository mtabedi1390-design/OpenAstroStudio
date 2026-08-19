"""Tests for engine/__init__.py — the public engine API surface."""

from __future__ import annotations

import astrostudio.engine as engine


def test_all_exported_names_are_importable():
    for name in engine.__all__:
        assert hasattr(engine, name), name


def test_reexports_point_to_the_implementation_modules():
    from astrostudio.engine.codegen import generate_code
    from astrostudio.engine.executor import ExecutionResult, execute_direct
    from astrostudio.engine.graph import Graph, GraphCycleError
    from astrostudio.engine.node import NodeSpec

    assert engine.generate_code is generate_code
    assert engine.execute_direct is execute_direct
    assert engine.ExecutionResult is ExecutionResult
    assert engine.Graph is Graph
    assert engine.GraphCycleError is GraphCycleError
    assert engine.NodeSpec is NodeSpec


def test_public_api_is_complete():
    assert set(engine.__all__) == {
        "NodeSpec", "NodeInstance", "ParamSpec", "PortSpec", "Connection",
        "reflect", "scan_module", "scan_callable_list",
        "Graph", "GraphCycleError", "generate_code",
        "execute_direct", "execute_generated_code", "ExecutionResult",
    }
