"""Tests for engine/library_scanner.py — module scanning and filtering."""

from __future__ import annotations

import sys
import types

import pytest

from astrostudio.engine.library_scanner import scan_callable_list, scan_module


def _sample_module(name="sample_lib_for_tests") -> types.ModuleType:
    module = types.ModuleType(name)

    def alpha(x: int) -> int:
        """Alpha function."""
        return x

    def beta(y: str = "b") -> str:
        """Beta function."""
        return y

    def _private(x):
        return x

    class Gamma:
        """Gamma class."""

        def __init__(self, z: float = 1.0):
            self.z = z

    for obj in (alpha, beta, _private, Gamma):
        obj.__module__ = name
    module.alpha = alpha
    module.beta = beta
    module._private = _private
    module.Gamma = Gamma
    module.CONSTANT = 42
    module.imported_helper = types.SimpleNamespace
    return module


@pytest.fixture
def sample_module():
    module = _sample_module()
    sys.modules[module.__name__] = module
    yield module
    del sys.modules[module.__name__]


def test_scan_module_returns_specs_for_public_callables(sample_module):
    names = {spec.display_name for spec in scan_module(sample_module)}
    assert names == {"alpha", "beta", "Gamma"}


def test_scan_module_skips_private_members_constants_and_foreign_imports(sample_module):
    names = {spec.display_name for spec in scan_module(sample_module)}
    assert "_private" not in names
    assert "CONSTANT" not in names
    assert "SimpleNamespace" not in names


def test_scan_module_sets_category_to_module_name(sample_module):
    assert all(spec.category == sample_module.__name__
               for spec in scan_module(sample_module))


def test_scan_module_accepts_dotted_module_name(sample_module):
    specs = scan_module(sample_module.__name__)
    assert {spec.display_name for spec in specs} == {"alpha", "beta", "Gamma"}


def test_scan_module_include_filter(sample_module):
    specs = scan_module(sample_module, include=["alpha"])
    assert [spec.display_name for spec in specs] == ["alpha"]


def test_scan_module_exclude_filter(sample_module):
    names = {spec.display_name for spec in scan_module(sample_module, exclude=["Gamma"])}
    assert names == {"alpha", "beta"}


def test_scan_module_include_and_exclude_together(sample_module):
    specs = scan_module(sample_module, include=["alpha", "beta"], exclude=["beta"])
    assert [spec.display_name for spec in specs] == ["alpha"]


def test_scan_module_max_items_caps_results(sample_module):
    assert len(scan_module(sample_module, max_items=2)) == 2


def test_scan_module_skips_members_that_cannot_be_reflected(sample_module, monkeypatch):
    from astrostudio.engine import library_scanner

    real_reflect = library_scanner.reflect

    def flaky_reflect(member, **kwargs):
        if getattr(member, "__name__", "") == "beta":
            raise RuntimeError("cannot reflect")
        return real_reflect(member, **kwargs)

    monkeypatch.setattr(library_scanner, "reflect", flaky_reflect)

    names = {spec.display_name for spec in scan_module(sample_module)}
    assert names == {"alpha", "Gamma"}


def test_scan_module_on_real_stdlib_module():
    specs = scan_module("json", max_items=3)
    assert 0 < len(specs) <= 3
    assert all(spec.category == "json" for spec in specs)


def test_scan_callable_list_reflects_each_callable():
    def one(a: int) -> int:
        return a

    def two(b: int) -> int:
        return b

    specs = scan_callable_list([one, two], category="custom")
    assert [spec.display_name for spec in specs] == ["one", "two"]
    assert all(spec.category == "custom" for spec in specs)


def test_scan_callable_list_skips_unreflectable_entries(monkeypatch):
    from astrostudio.engine import library_scanner

    real_reflect = library_scanner.reflect

    def flaky_reflect(member, **kwargs):
        if member is dict:
            raise RuntimeError("nope")
        return real_reflect(member, **kwargs)

    monkeypatch.setattr(library_scanner, "reflect", flaky_reflect)

    def keeper(a: int) -> int:
        return a

    specs = scan_callable_list([dict, keeper])
    assert [spec.display_name for spec in specs] == ["keeper"]


def test_scan_callable_list_empty_input():
    assert scan_callable_list([]) == []
