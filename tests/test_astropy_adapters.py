"""Tests for libraries/astropy_adapters.py — thin adapters over astropy APIs."""

from __future__ import annotations

import pytest
from astropy.coordinates import SkyCoord

from astrostudio.engine.reflection import reflect
from astrostudio.libraries.astropy_adapters import separation_deg, to_galactic


@pytest.fixture
def m31() -> SkyCoord:
    return SkyCoord(ra=10.68, dec=41.27, unit="deg", frame="icrs")


def test_to_galactic_changes_frame(m31):
    galactic = to_galactic(m31)
    assert galactic.frame.name == "galactic"
    assert round(float(galactic.l.deg), 2) == 121.17
    assert round(float(galactic.b.deg), 2) == -21.57


def test_to_galactic_is_idempotent_on_galactic_input(m31):
    once = to_galactic(m31)
    twice = to_galactic(once)
    assert twice.frame.name == "galactic"
    assert float(twice.l.deg) == pytest.approx(float(once.l.deg))


def test_separation_deg_between_distinct_points(m31):
    other = SkyCoord(ra=15.0, dec=41.0, unit="deg", frame="icrs")
    assert separation_deg(m31, other) == pytest.approx(3.26, abs=0.01)


def test_separation_deg_is_zero_for_same_point(m31):
    assert separation_deg(m31, m31) == pytest.approx(0.0)


def test_separation_deg_is_symmetric(m31):
    other = SkyCoord(ra=200.0, dec=-20.0, unit="deg", frame="icrs")
    assert separation_deg(m31, other) == pytest.approx(separation_deg(other, m31))


def test_separation_deg_returns_plain_float(m31):
    other = SkyCoord(ra=11.0, dec=41.0, unit="deg", frame="icrs")
    assert isinstance(separation_deg(m31, other), float)


@pytest.mark.parametrize("func, expected_params", [
    (to_galactic, ["coord"]),
    (separation_deg, ["coord1", "coord2"]),
])
def test_adapters_are_reflectable_into_nodes(func, expected_params):
    spec = reflect(func, category="astropy.coordinates")
    assert [p.name for p in spec.params] == expected_params
    assert all(p.annotation == "SkyCoord" for p in spec.params)
    assert all(p.description for p in spec.params)
    assert spec.description
    assert spec.import_path == (
        "from astrostudio.libraries.astropy_adapters import " + func.__name__)
