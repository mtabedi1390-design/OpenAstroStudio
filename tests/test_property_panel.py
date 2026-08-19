"""Tests for gui/property_panel.py — value coercion and panel rebuilds."""

from __future__ import annotations

import pytest

from PySide6.QtWidgets import QFormLayout

from astrostudio.engine.node import NodeInstance
from astrostudio.gui.property_panel import PropertyPanel, _coerce


@pytest.mark.parametrize("text, expected", [
    ("", None),
    ("true", True),
    ("True", True),
    (" TRUE ", True),
    ("false", False),
    ("3", 3),
    ("-7", -7),
    ("3.5", 3.5),
    ("1e3", 1000.0),
    ("deg", "deg"),
    ("1,2", "1,2"),
    ("hourangle,deg", "hourangle,deg"),
])
def test_coerce(text, expected):
    assert _coerce(text) == expected


def test_coerce_returns_int_type_for_integers():
    assert isinstance(_coerce("4"), int)
    assert isinstance(_coerce("4.0"), float)


def test_panel_starts_empty(qapp):
    panel = PropertyPanel()
    assert panel.current_node is None
    assert panel._editors == {}
    assert panel.params_form.rowCount() == 0


def test_show_node_creates_one_editor_per_param(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    assert set(panel._editors) == {"a", "b"}
    assert panel.params_form.rowCount() == 2
    assert panel.current_node is add_node


def test_show_node_prefills_values_and_placeholders(qapp, add_node):
    add_node.param_values["a"] = 7
    panel = PropertyPanel()
    panel.show_node(add_node)
    assert panel._editors["a"].text() == "7"
    assert panel._editors["b"].text() == "2"
    assert panel._editors["a"].placeholderText() == "Any"


def test_show_node_leaves_unset_required_param_blank(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    assert panel._editors["a"].text() == ""


def test_show_node_sets_title_and_documentation(qapp, reflected_add_spec):
    node = NodeInstance.create(reflected_add_spec)
    panel = PropertyPanel()
    panel.show_node(node)
    assert node.label in panel.title_label.text()
    assert "function" in panel.title_label.text()
    assert "Adds two numbers." in panel.doc_view.toPlainText()


def test_show_node_falls_back_to_description_when_no_full_doc(qapp, add_node):
    add_node.spec.doc_full = ""
    add_node.spec.description = "Only a summary"
    panel = PropertyPanel()
    panel.show_node(add_node)
    assert panel.doc_view.toPlainText() == "Only a summary"


def test_show_node_marks_optional_params(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    labels = [panel.params_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
              .widget().text() for row in range(panel.params_form.rowCount())]
    assert labels[0] == "a"
    assert labels[1].startswith("b") and labels[1] != "b"


def test_show_node_none_clears_panel(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    panel.show_node(None)
    assert panel.current_node is None
    assert panel._editors == {}
    assert panel.params_form.rowCount() == 0
    assert panel.doc_view.toPlainText() == ""


def test_show_node_replaces_previous_node_editors(qapp, add_node, double_spec):
    panel = PropertyPanel()
    panel.show_node(add_node)
    panel.show_node(NodeInstance.create(double_spec))
    assert set(panel._editors) == {"value"}
    assert panel.params_form.rowCount() == 1


def test_editing_a_param_updates_node_and_emits_signal(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    emitted = []
    panel.value_changed.connect(lambda: emitted.append(True))

    panel._editors["a"].setText("41.27")
    panel._editors["a"].editingFinished.emit()

    assert add_node.param_values["a"] == 41.27
    assert emitted == [True]


def test_editing_clears_value_to_none(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    panel._editors["b"].setText("")
    panel._editors["b"].editingFinished.emit()
    assert add_node.param_values["b"] is None


def test_param_edit_without_selected_node_is_ignored(qapp, add_node):
    panel = PropertyPanel()
    panel.show_node(add_node)
    editor = panel._editors["a"]
    panel.current_node = None
    editor.setText("5")
    panel._on_param_edited("a", editor)
    assert "a" not in add_node.param_values
