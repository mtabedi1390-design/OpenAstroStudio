"""Tests for gui/node_graphics.py — port/node/connection graphics items."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from astrostudio.engine.node import NodeInstance
from astrostudio.gui.node_graphics import (
    HEADER_HEIGHT,
    NODE_WIDTH,
    PORT_RADIUS,
    ROW_HEIGHT,
    ConnectionGraphicsItem,
    NodeGraphicsItem,
)


def _node_item(spec, position=(0.0, 0.0)) -> NodeGraphicsItem:
    instance = NodeInstance.create(spec, position=position)
    return NodeGraphicsItem(instance, editor=None)


def test_node_item_geometry_scales_with_port_count(qapp, add_spec, double_spec):
    two_rows = _node_item(add_spec)
    one_row = _node_item(double_spec)
    assert two_rows.rect().width() == NODE_WIDTH
    assert two_rows.rect().height() == HEADER_HEIGHT + 2 * ROW_HEIGHT + 8
    assert one_row.rect().height() == HEADER_HEIGHT + 1 * ROW_HEIGHT + 8


def test_node_item_is_movable_and_selectable(qapp, add_spec):
    item = _node_item(add_spec)
    flags = item.flags()
    assert flags & QGraphicsItem.ItemIsMovable
    assert flags & QGraphicsItem.ItemIsSelectable
    assert flags & QGraphicsItem.ItemSendsGeometryChanges


def test_node_item_uses_instance_position(qapp, add_spec):
    item = _node_item(add_spec, position=(25.0, 40.0))
    assert (item.pos().x(), item.pos().y()) == (25.0, 40.0)


def test_node_item_creates_ports_for_every_spec_port(qapp, add_spec):
    item = _node_item(add_spec)
    assert set(item.in_ports) == {"a", "b"}
    assert set(item.out_ports) == {"result"}
    assert item.in_ports["a"].direction == "in"
    assert item.out_ports["result"].direction == "out"
    assert item.in_ports["a"].node_item is item


def test_ports_sit_on_the_expected_sides(qapp, add_spec):
    item = _node_item(add_spec)
    assert item.in_ports["a"].rect().left() == -PORT_RADIUS
    assert item.out_ports["result"].rect().left() == NODE_WIDTH - PORT_RADIUS


def test_input_ports_are_stacked_by_index(qapp, add_spec):
    item = _node_item(add_spec)
    assert (item.in_ports["b"].scene_center().y()
            - item.in_ports["a"].scene_center().y()) == ROW_HEIGHT


def test_port_scene_center_follows_node_position(qapp, add_spec):
    item = _node_item(add_spec)
    before = item.in_ports["a"].scene_center()
    item.setPos(100, 50)
    after = item.in_ports["a"].scene_center()
    assert (after.x() - before.x(), after.y() - before.y()) == (100, 50)


def test_port_at_finds_nearby_port_and_ignores_far_points(qapp, add_spec):
    scene = QGraphicsScene()
    item = _node_item(add_spec)
    scene.addItem(item)
    center = item.out_ports["result"].scene_center()
    assert item.port_at(center) is item.out_ports["result"]
    assert item.port_at(center + QPointF(5, 5)) is item.out_ports["result"]
    assert item.port_at(center + QPointF(500, 500)) is None


def test_moving_node_item_syncs_instance_position(qapp, add_spec):
    scene = QGraphicsScene()
    item = _node_item(add_spec)
    scene.addItem(item)
    item.setPos(120, 60)
    assert item.node_instance.position == (120.0, 60.0)


def test_connection_registers_with_both_nodes(qapp, add_spec, double_spec):
    scene = QGraphicsScene()
    source = _node_item(double_spec)
    target = _node_item(add_spec, position=(300.0, 0.0))
    scene.addItem(source)
    scene.addItem(target)

    conn = ConnectionGraphicsItem("conn_1", source.out_ports["result"],
                                  target.in_ports["a"])
    scene.addItem(conn)

    assert conn.connection_id == "conn_1"
    assert conn in source.connections
    assert conn in target.connections
    assert not conn.path().isEmpty()
    assert conn.zValue() == -1


def test_connection_path_endpoints_match_ports(qapp, add_spec, double_spec):
    scene = QGraphicsScene()
    source = _node_item(double_spec)
    target = _node_item(add_spec, position=(300.0, 0.0))
    scene.addItem(source)
    scene.addItem(target)
    conn = ConnectionGraphicsItem("conn_1", source.out_ports["result"],
                                  target.in_ports["a"])
    scene.addItem(conn)

    path = conn.path()
    assert path.pointAtPercent(0.0) == source.out_ports["result"].scene_center()
    assert path.pointAtPercent(1.0) == target.in_ports["a"].scene_center()


def test_connection_path_updates_when_node_moves(qapp, add_spec, double_spec):
    scene = QGraphicsScene()
    source = _node_item(double_spec)
    target = _node_item(add_spec, position=(300.0, 0.0))
    scene.addItem(source)
    scene.addItem(target)
    conn = ConnectionGraphicsItem("conn_1", source.out_ports["result"],
                                  target.in_ports["a"])
    scene.addItem(conn)

    target.setPos(300, 200)
    assert conn.path().pointAtPercent(1.0) == target.in_ports["a"].scene_center()
