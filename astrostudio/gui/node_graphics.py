"""
gui/node_graphics.py
----------------------
اجزای بصری بوم (canvas): PortItem، NodeGraphicsItem و ConnectionGraphicsItem.

این ماژول لایه‌ی View است -- به هیچ‌کدام از منطق reflection/graph/executor
مستقیماً وابسته نیست، فقط به NodeInstance برای نمایش نیاز دارد.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QBrush, QPen, QColor, QFont, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsPathItem, QGraphicsTextItem, QGraphicsSceneMouseEvent,
)

from ..engine.node import NodeInstance

PORT_RADIUS = 6
NODE_WIDTH = 180
HEADER_HEIGHT = 28
ROW_HEIGHT = 20


class PortItem(QGraphicsEllipseItem):
    """یک پورت ورودی یا خروجی، فرزند NodeGraphicsItem."""

    def __init__(self, name: str, direction: str, parent_node: "NodeGraphicsItem", index: int):
        x = -PORT_RADIUS if direction == "in" else NODE_WIDTH - PORT_RADIUS
        y = HEADER_HEIGHT + index * ROW_HEIGHT + ROW_HEIGHT / 2 - PORT_RADIUS
        super().__init__(x, y, PORT_RADIUS * 2, PORT_RADIUS * 2, parent_node)
        self.name = name
        self.direction = direction
        self.node_item = parent_node
        color = QColor("#E0A030") if direction == "in" else QColor("#4FA86A")
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#222222"), 1))
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    def scene_center(self) -> QPointF:
        return self.mapToScene(self.rect().center())


class NodeGraphicsItem(QGraphicsRectItem):
    """نمایش بصری یک NodeInstance؛ قابل جابجایی، با پورت‌های ورودی/خروجی."""

    def __init__(self, node_instance: NodeInstance, editor: "NodeEditorScene"):
        n_rows = max(len(node_instance.spec.inputs), len(node_instance.spec.outputs), 1)
        height = HEADER_HEIGHT + n_rows * ROW_HEIGHT + 8
        super().__init__(0, 0, NODE_WIDTH, height)

        self.node_instance = node_instance
        self.editor = editor
        self.connections: list["ConnectionGraphicsItem"] = []

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setBrush(QBrush(QColor(node_instance.spec.color)))
        self.setPen(QPen(QColor("#1c1c1c"), 1.5))
        self.setPos(*node_instance.position)

        title = QGraphicsTextItem(node_instance.label, self)
        title.setDefaultTextColor(QColor("white"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        title.setFont(font)
        title.setPos(6, 4)

        self.in_ports: dict[str, PortItem] = {}
        self.out_ports: dict[str, PortItem] = {}

        for i, port_spec in enumerate(node_instance.spec.inputs):
            item = PortItem(port_spec.name, "in", self, i)
            self.in_ports[port_spec.name] = item
            label = QGraphicsTextItem(port_spec.name, self)
            label.setDefaultTextColor(QColor("white"))
            label.setPos(8, HEADER_HEIGHT + i * ROW_HEIGHT)
            small = QFont()
            small.setPointSize(8)
            label.setFont(small)

        for i, port_spec in enumerate(node_instance.spec.outputs):
            item = PortItem(port_spec.name, "out", self, i)
            self.out_ports[port_spec.name] = item
            label = QGraphicsTextItem(port_spec.name, self)
            label.setDefaultTextColor(QColor("white"))
            label.setPos(NODE_WIDTH - 8 - 60, HEADER_HEIGHT + i * ROW_HEIGHT)
            small = QFont()
            small.setPointSize(8)
            label.setFont(small)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.node_instance.position = (self.pos().x(), self.pos().y())
            for conn in self.connections:
                conn.update_path()
        return super().itemChange(change, value)

    def port_at(self, scene_pos: QPointF, radius: float = 12.0):
        """نزدیک‌ترین پورت به یک نقطه‌ی صحنه را برمی‌گرداند (برای شروع/پایان اتصال)."""
        for port in list(self.in_ports.values()) + list(self.out_ports.values()):
            d = port.scene_center() - scene_pos
            if (d.x() ** 2 + d.y() ** 2) ** 0.5 <= radius:
                return port
        return None


class ConnectionGraphicsItem(QGraphicsPathItem):
    """یک خط منحنی بین پورت خروجی و پورت ورودی، متناظر با یک Connection منطقی."""

    def __init__(self, connection_id: str, source_port: PortItem, target_port: PortItem):
        super().__init__()
        self.connection_id = connection_id
        self.source_port = source_port
        self.target_port = target_port
        self.setPen(QPen(QColor("#DDDDDD"), 2))
        self.setZValue(-1)
        source_port.node_item.connections.append(self)
        target_port.node_item.connections.append(self)
        self.update_path()

    def update_path(self):
        p1 = self.source_port.scene_center()
        p2 = self.target_port.scene_center()
        path = QPainterPath(p1)
        dx = max(abs(p2.x() - p1.x()) * 0.5, 40)
        c1 = QPointF(p1.x() + dx, p1.y())
        c2 = QPointF(p2.x() - dx, p2.y())
        path.cubicTo(c1, c2, p2)
        self.setPath(path)
