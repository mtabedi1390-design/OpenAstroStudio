"""Shared fixtures for the AstroStudio test suite."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from astrostudio.engine.node import NodeInstance, NodeSpec, ParamSpec, PortSpec
from astrostudio.engine.reflection import reflect


def add(a: int, b: int = 2) -> int:
    """Adds two numbers.

    Parameters
    ----------
    a : int
        First operand.
    b : int
        Second operand.

    Returns
    -------
    int
        The sum.
    """
    return a + b


def double(value: int) -> int:
    """Doubles a number."""
    return value * 2


def make_spec(callable_ref, *, params, spec_id=None, import_path="",
              display_name=None) -> NodeSpec:
    """Builds a NodeSpec by hand so engine tests stay free of reflection details."""
    param_specs = [
        ParamSpec(name=name, has_default=has_default, required=not has_default,
                  default=default)
        for name, has_default, default in params
    ]
    return NodeSpec(
        id=spec_id or getattr(callable_ref, "__name__", "spec"),
        display_name=display_name or getattr(callable_ref, "__name__", "spec"),
        category="tests",
        description="",
        doc_full="",
        params=param_specs,
        inputs=[PortSpec(name=p.name) for p in param_specs],
        outputs=[PortSpec(name="result", direction="out")],
        callable_ref=callable_ref,
        import_path=import_path,
    )


@pytest.fixture
def add_spec() -> NodeSpec:
    return make_spec(add, params=[("a", False, None), ("b", True, 2)],
                     import_path="from tests.conftest import add")


@pytest.fixture
def double_spec() -> NodeSpec:
    return make_spec(double, params=[("value", False, None)],
                     import_path="from tests.conftest import double")


@pytest.fixture
def add_node(add_spec) -> NodeInstance:
    return NodeInstance.create(add_spec)


@pytest.fixture
def reflected_add_spec() -> NodeSpec:
    return reflect(add, category="tests")


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the whole session (Qt allows only one)."""
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication
    app = QApplication.instance() or QApplication([])
    yield app
