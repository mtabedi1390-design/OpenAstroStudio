"""Tests for engine/overrides.py — the manual NodeSpec registry."""

from __future__ import annotations

from astropy.coordinates import SkyCoord

from astrostudio.engine.overrides import MANUAL_OVERRIDES, skycoord_node_spec


def test_skycoord_node_spec_metadata():
    spec = skycoord_node_spec()
    assert spec.id == "astropy.coordinates.SkyCoord.manual"
    assert spec.display_name == "Coordinate (ICRS)"
    assert spec.category == "astropy.coordinates"
    assert spec.kind == "class"
    assert spec.callable_ref is SkyCoord
    assert spec.import_path == "from astropy.coordinates import SkyCoord"
    assert spec.doc_full


def test_skycoord_node_spec_exposes_real_constructor_params():
    spec = skycoord_node_spec()
    assert [p.name for p in spec.params] == ["ra", "dec", "unit", "frame"]
    assert all(p.has_default and not p.required for p in spec.params)
    assert [p.default for p in spec.params] == [0.0, 0.0, "deg", "icrs"]
    assert all(p.description for p in spec.params)


def test_skycoord_node_spec_ports_mirror_params():
    spec = skycoord_node_spec()
    assert [i.name for i in spec.inputs] == [p.name for p in spec.params]
    assert all(i.direction == "in" for i in spec.inputs)
    assert [(o.name, o.annotation, o.direction) for o in spec.outputs] == [
        ("result", "SkyCoord", "out")]


def test_skycoord_node_spec_returns_fresh_instances():
    first, second = skycoord_node_spec(), skycoord_node_spec()
    assert first is not second
    assert first.params is not second.params
    assert first == second


def test_skycoord_spec_params_can_actually_build_a_skycoord():
    spec = skycoord_node_spec()
    kwargs = {p.name: p.default for p in spec.params}
    kwargs.update({"ra": 10.68, "dec": 41.27})
    coord = spec.callable_ref(**kwargs)
    assert coord.frame.name == "icrs"
    assert round(float(coord.ra.deg), 2) == 10.68


def test_manual_overrides_registry_maps_path_to_factory():
    assert MANUAL_OVERRIDES["astropy.coordinates.SkyCoord"] is skycoord_node_spec
    assert MANUAL_OVERRIDES["astropy.coordinates.SkyCoord"]().params
