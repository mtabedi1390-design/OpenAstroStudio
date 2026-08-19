"""Tests for gui/library_panel.py — categorized spec tree and double-click signal."""

from __future__ import annotations

from dataclasses import replace

from astrostudio.gui.library_panel import LibraryPanel

USER_ROLE = 32


def _leaf_names(panel: LibraryPanel, top_index: int) -> list[str]:
    item = panel.tree.topLevelItem(top_index)
    return [item.child(i).text(0) for i in range(item.childCount())]


def test_panel_starts_empty(qapp):
    panel = LibraryPanel()
    assert panel.tree.topLevelItemCount() == 0
    assert panel._specs == {}
    assert panel.tree.isHeaderHidden()


def test_load_specs_groups_by_category(qapp, add_spec, double_spec):
    other = replace(double_spec, category="other")
    panel = LibraryPanel()
    panel.load_specs([add_spec, double_spec, other])

    categories = [panel.tree.topLevelItem(i).text(0)
                  for i in range(panel.tree.topLevelItemCount())]
    assert categories == ["tests", "other"]
    assert _leaf_names(panel, 0) == [add_spec.display_name, double_spec.display_name]
    assert _leaf_names(panel, 1) == [other.display_name]


def test_load_specs_indexes_specs_by_id(qapp, add_spec, double_spec):
    panel = LibraryPanel()
    panel.load_specs([add_spec, double_spec])
    assert panel._specs == {add_spec.id: add_spec, double_spec.id: double_spec}


def test_load_specs_stores_spec_id_on_leaf(qapp, add_spec):
    panel = LibraryPanel()
    panel.load_specs([add_spec])
    leaf = panel.tree.topLevelItem(0).child(0)
    assert leaf.data(0, USER_ROLE) == add_spec.id


def test_load_specs_uses_placeholder_for_missing_category(qapp, add_spec):
    panel = LibraryPanel()
    panel.load_specs([replace(add_spec, category="")])
    assert panel.tree.topLevelItemCount() == 1
    assert panel.tree.topLevelItem(0).text(0) != ""


def test_load_specs_replaces_previous_content(qapp, add_spec, double_spec):
    panel = LibraryPanel()
    panel.load_specs([add_spec])
    panel.load_specs([double_spec])
    assert panel._specs == {double_spec.id: double_spec}
    assert panel.tree.topLevelItemCount() == 1
    assert _leaf_names(panel, 0) == [double_spec.display_name]


def test_double_click_on_leaf_emits_spec(qapp, add_spec):
    panel = LibraryPanel()
    panel.load_specs([add_spec])
    emitted = []
    panel.node_double_clicked.connect(emitted.append)

    panel.tree.itemDoubleClicked.emit(panel.tree.topLevelItem(0).child(0), 0)
    assert emitted == [add_spec]


def test_double_click_on_category_emits_nothing(qapp, add_spec):
    panel = LibraryPanel()
    panel.load_specs([add_spec])
    emitted = []
    panel.node_double_clicked.connect(emitted.append)

    panel.tree.itemDoubleClicked.emit(panel.tree.topLevelItem(0), 0)
    assert emitted == []


def test_double_click_on_unknown_spec_id_emits_nothing(qapp, add_spec):
    panel = LibraryPanel()
    panel.load_specs([add_spec])
    leaf = panel.tree.topLevelItem(0).child(0)
    leaf.setData(0, USER_ROLE, "unknown.spec")
    emitted = []
    panel.node_double_clicked.connect(emitted.append)

    panel.tree.itemDoubleClicked.emit(leaf, 0)
    assert emitted == []
