"""Tests for gui/node_editor.py — scene/graph synchronization and drag-to-connect."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QGraphicsSceneMouseEvent

from astrostudio.gui.node_editor import NodeEditorScene, NodeEditorView
from astrostudio.gui.node_graphics import ConnectionGraphicsItem, NodeGraphicsItem


def _mouse_event(event_type, scene_pos: QPointF) -> QGraphicsSceneMouseEvent:
    event = QGraphicsSceneMouseEvent(event_type)
    event.setScenePos(scene_pos)
    event.setButton(Qt.LeftButton)
    event.setButtons(Qt.LeftButton)
    return event


def _drag(scene: NodeEditorScene, start: QPointF, end: QPointF) -> None:
    scene.mousePressEvent(_mouse_event(QEvent.GraphicsSceneMousePress, start))
    scene.mouseMoveEvent(_mouse_event(QEvent.GraphicsSceneMouseMove, end))
    scene.mouseReleaseEvent(_mouse_event(QEvent.GraphicsSceneMouseRelease, end))


@pytest.fixture
def scene(qapp) -> NodeEditorScene:
    return NodeEditorScene()


@pytest.fixture
def two_nodes(scene, add_spec, double_spec):
    producer = scene.add_node_from_spec(double_spec, position=(0, 0))
    consumer = scene.add_node_from_spec(add_spec, position=(400, 0))
    return producer, consumer


def test_new_scene_is_empty(scene):
    assert scene.graph.nodes == {}
    assert scene.node_items == {}
    assert scene.connection_items == {}
    assert scene._drag_source_port is None


def test_add_node_from_spec_updates_scene_and_graph(scene, add_spec):
    emitted = []
    scene.graph_changed.connect(lambda: emitted.append(True))

    item = scene.add_node_from_spec(add_spec, position=(30, 40))

    assert isinstance(item, NodeGraphicsItem)
    assert item in scene.items()
    assert scene.node_items == {item.node_instance.id: item}
    assert scene.graph.nodes[item.node_instance.id] is item.node_instance
    assert item.node_instance.position == (30, 40)
    assert emitted == [True]


def test_add_node_from_spec_seeds_default_param_values(scene, add_spec):
    item = scene.add_node_from_spec(add_spec)
    assert item.node_instance.param_values == {"b": 2}


def test_remove_node_item_clears_scene_graph_and_connections(scene, two_nodes):
    producer, consumer = two_nodes
    scene._create_connection(producer.out_ports["result"], consumer.in_ports["a"])
    emitted = []
    scene.graph_changed.connect(lambda: emitted.append(True))

    scene.remove_node_item(producer)

    assert producer not in scene.items()
    assert producer.node_instance.id not in scene.node_items
    assert producer.node_instance.id not in scene.graph.nodes
    assert scene.connection_items == {}
    assert scene.graph.connections == {}
    assert consumer.connections == []
    assert emitted == [True]


def test_create_connection_syncs_graph_and_scene(scene, two_nodes):
    producer, consumer = two_nodes
    scene._create_connection(producer.out_ports["result"], consumer.in_ports["a"])

    assert len(scene.graph.connections) == 1
    conn = next(iter(scene.graph.connections.values()))
    assert (conn.source_node_id, conn.source_port) == (producer.node_instance.id, "result")
    assert (conn.target_node_id, conn.target_port) == (consumer.node_instance.id, "a")
    assert isinstance(scene.connection_items[conn.id], ConnectionGraphicsItem)


def test_create_connection_replaces_existing_input_connection(scene, add_spec,
                                                              double_spec):
    first = scene.add_node_from_spec(double_spec, position=(0, 0))
    second = scene.add_node_from_spec(double_spec, position=(0, 200))
    consumer = scene.add_node_from_spec(add_spec, position=(400, 0))

    scene._create_connection(first.out_ports["result"], consumer.in_ports["a"])
    scene._create_connection(second.out_ports["result"], consumer.in_ports["a"])

    assert len(scene.graph.connections) == 1
    assert len(scene.connection_items) == 1
    conn = next(iter(scene.graph.connections.values()))
    assert conn.source_node_id == second.node_instance.id
    assert len(consumer.connections) == 1


def test_create_connection_ignores_nodes_missing_from_graph(scene, two_nodes):
    producer, consumer = two_nodes
    scene.graph.nodes.pop(producer.node_instance.id)
    scene._create_connection(producer.out_ports["result"], consumer.in_ports["a"])
    assert scene.connection_items == {}


def test_drag_from_output_to_input_creates_connection(scene, two_nodes):
    producer, consumer = two_nodes
    _drag(scene, producer.out_ports["result"].scene_center(),
          consumer.in_ports["a"].scene_center())

    assert len(scene.graph.connections) == 1
    assert scene._drag_source_port is None
    assert scene._temp_path_item is None


def test_drag_shows_temporary_path_while_moving(scene, two_nodes):
    producer, _ = two_nodes
    scene.mousePressEvent(_mouse_event(QEvent.GraphicsSceneMousePress,
                                       producer.out_ports["result"].scene_center()))
    assert scene._drag_source_port is producer.out_ports["result"]
    assert scene._temp_path_item in scene.items()

    scene.mouseMoveEvent(_mouse_event(QEvent.GraphicsSceneMouseMove, QPointF(200, 100)))
    assert not scene._temp_path_item.path().isEmpty()


def test_drag_ending_on_empty_canvas_creates_nothing(scene, two_nodes):
    producer, _ = two_nodes
    _drag(scene, producer.out_ports["result"].scene_center(), QPointF(900, 900))
    assert scene.graph.connections == {}
    assert scene._temp_path_item is None


def test_drag_from_output_to_own_input_is_rejected(scene, add_spec):
    item = scene.add_node_from_spec(add_spec)
    _drag(scene, item.out_ports["result"].scene_center(),
          item.in_ports["a"].scene_center())
    assert scene.graph.connections == {}


def test_drag_starting_from_input_port_does_not_start_a_connection(scene, two_nodes):
    producer, consumer = two_nodes
    _drag(scene, consumer.in_ports["a"].scene_center(),
          producer.out_ports["result"].scene_center())
    assert scene.graph.connections == {}
    assert scene._drag_source_port is None


def test_click_on_node_emits_node_selected(scene, add_spec):
    item = scene.add_node_from_spec(add_spec)
    selected = []
    scene.node_selected.connect(selected.append)

    scene.mousePressEvent(_mouse_event(QEvent.GraphicsSceneMousePress,
                                       item.sceneBoundingRect().center()))
    assert selected == [item.node_instance]


def test_click_on_empty_canvas_emits_none(scene, add_spec):
    scene.add_node_from_spec(add_spec)
    selected = []
    scene.node_selected.connect(selected.append)

    scene.mousePressEvent(_mouse_event(QEvent.GraphicsSceneMousePress,
                                       QPointF(2000, 2000)))
    assert selected == [None]


def test_find_port_at_uses_node_tolerance(scene, add_spec):
    item = scene.add_node_from_spec(add_spec)
    port_center = item.in_ports["a"].scene_center()
    assert scene._find_port_at(port_center) is item.in_ports["a"]
    # A point inside the node body but outside the port circle still snaps to it.
    assert scene._find_port_at(port_center + QPointF(9, 0)) is item.in_ports["a"]
    assert scene._find_port_at(QPointF(5000, 5000)) is None


def test_view_wheel_event_zooms_in_and_out(scene):
    view = NodeEditorView(scene)

    def wheel(delta):
        return QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0),
                           QPoint(0, delta), Qt.NoButton, Qt.NoModifier,
                           Qt.NoScrollPhase, False)

    view.wheelEvent(wheel(120))
    zoomed_in = view.transform().m11()
    assert zoomed_in > 1.0

    view.wheelEvent(wheel(-120))
    assert view.transform().m11() == pytest.approx(1.0, abs=1e-6)
