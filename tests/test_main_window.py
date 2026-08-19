"""Tests for gui/main_window.py and main.py — wiring of panels, code preview and Run."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from astrostudio import main as main_module
from astrostudio.gui import main_window as main_window_module
from astrostudio.gui.main_window import MainWindow, default_library


@pytest.fixture
def window(qapp) -> MainWindow:
    return MainWindow()


def test_default_library_contains_the_demo_blocks():
    specs = default_library()
    assert [spec.display_name for spec in specs] == [
        "Coordinate (ICRS)", "To Galactic", "Separation (deg)"]
    assert all(spec.category == "astropy.coordinates" for spec in specs)
    assert all(spec.params for spec in specs)


def test_window_loads_default_library(window):
    assert len(window.library_panel._specs) == len(default_library())
    assert window.library_panel.tree.topLevelItemCount() == 1


def test_window_starts_with_empty_canvas_and_readonly_views(window):
    assert window.scene.graph.nodes == {}
    assert window.code_view.isReadOnly()
    assert window.console_view.isReadOnly()


def test_double_clicking_library_adds_node_to_canvas(window):
    spec = window.library_panel._specs[default_library()[0].id]
    window.library_panel.node_double_clicked.emit(spec)

    assert len(window.scene.graph.nodes) == 1
    node = next(iter(window.scene.graph.nodes.values()))
    assert node.spec.display_name == spec.display_name


def test_adding_node_refreshes_code_preview(window):
    spec = default_library()[0]
    window._add_node_from_library(spec)
    code = window.code_view.toPlainText()
    assert "from astropy.coordinates import SkyCoord" in code
    assert "SkyCoord(" in code


def test_selecting_node_populates_property_panel(window):
    item = window.scene.add_node_from_spec(default_library()[0])
    window.scene.node_selected.emit(item.node_instance)
    assert window.property_panel.current_node is item.node_instance
    assert set(window.property_panel._editors) == {"ra", "dec", "unit", "frame"}


def test_property_panel_edit_refreshes_code_preview(window):
    item = window.scene.add_node_from_spec(default_library()[0])
    window.scene.node_selected.emit(item.node_instance)

    editor = window.property_panel._editors["ra"]
    editor.setText("10.68")
    editor.editingFinished.emit()

    assert item.node_instance.param_values["ra"] == 10.68
    assert "ra=10.68" in window.code_view.toPlainText()


def test_code_preview_reports_generation_errors(window):
    item = window.scene.add_node_from_spec(default_library()[0])
    window.scene.graph.connect(item.node_instance.id, "result",
                               item.node_instance.id, "ra")
    window._refresh_code_preview()
    assert "GraphCycleError" in window.code_view.toPlainText()


def test_run_on_empty_canvas_shows_information_dialog(window, monkeypatch):
    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *args, **kwargs: calls.append(args[1:]))
    window._run_graph()
    assert len(calls) == 1
    assert window.console_view.toPlainText() == ""


def test_run_executes_graph_and_reports_results(window):
    coord_item = window.scene.add_node_from_spec(default_library()[0])
    coord_item.node_instance.param_values.update({"ra": 10.68, "dec": 41.27})
    galactic_item = window.scene.add_node_from_spec(default_library()[1])
    window.scene._create_connection(coord_item.out_ports["result"],
                                    galactic_item.in_ports["coord"])

    window._run_graph()

    console = window.console_view.toPlainText()
    assert "Galactic" in console
    assert coord_item.node_instance.label in console
    assert galactic_item.node_instance.label in console
    assert "SkyCoord(" in window.code_view.toPlainText()


def test_run_reports_execution_errors_in_console(window):
    item = window.scene.add_node_from_spec(default_library()[1])  # To Galactic
    item.node_instance.param_values["coord"] = "not a coordinate"
    window._run_graph()
    console = window.console_view.toPlainText()
    assert "AttributeError" in console


def test_add_node_from_library_places_node_near_view_center(window):
    window._add_node_from_library(default_library()[0])
    node = next(iter(window.scene.graph.nodes.values()))
    expected = window.view.mapToScene(window.view.viewport().rect().center())
    assert node.position == (expected.x(), expected.y())


def test_main_creates_window_and_starts_event_loop(monkeypatch):
    events = []

    class FakeApp:
        def __init__(self, argv):
            events.append(("app", tuple(argv)))

        def exec(self):
            events.append(("exec",))
            return 0

    class FakeWindow:
        def show(self):
            events.append(("show",))

    monkeypatch.setattr(main_module, "QApplication", FakeApp)
    monkeypatch.setattr(main_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(main_module.sys, "argv", ["astrostudio"])

    with pytest.raises(SystemExit) as excinfo:
        main_module.main()

    assert excinfo.value.code == 0
    assert [e[0] for e in events] == ["app", "show", "exec"]


def test_main_window_module_exposes_expected_helpers():
    assert callable(main_window_module.default_library)
    assert issubclass(main_window_module.MainWindow, main_window_module.QMainWindow)
