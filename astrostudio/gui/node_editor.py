"""
gui/node_editor.py
--------------------
NodeEditorScene: پل بین لایه‌ی بصری (node_graphics.py) و لایه‌ی منطقی
(engine.graph.Graph). هر تعامل کاربر (افزودن Node، کشیدن اتصال) هم روی
صحنه‌ی گرافیکی و هم روی گراف منطقی اعمال می‌شود تا این دو همیشه sync باشند.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QPen, QColor, QPainterPath
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsView

from ..engine.graph import Graph
from ..engine.node import NodeInstance, NodeSpec
from .node_graphics import NodeGraphicsItem, ConnectionGraphicsItem, PortItem


class NodeEditorScene(QGraphicsScene):
    graph_changed = Signal()
    node_selected = Signal(object)  # NodeInstance | None

    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(QColor("#2b2b33"))
        self.graph = Graph()
        self.node_items: dict[str, NodeGraphicsItem] = {}
        self.connection_items: dict[str, ConnectionGraphicsItem] = {}

        self._drag_source_port: PortItem | None = None
        self._temp_path_item: QGraphicsPathItem | None = None

    # ---------- افزودن Node ----------

    def add_node_from_spec(self, spec: NodeSpec, position: tuple[float, float] = (0, 0)) -> NodeGraphicsItem:
        instance = NodeInstance.create(spec, position=position)
        self.graph.add_node(instance)
        item = NodeGraphicsItem(instance, self)
        self.addItem(item)
        self.node_items[instance.id] = item
        self.graph_changed.emit()
        return item

    def remove_node_item(self, item: NodeGraphicsItem):
        for conn in list(item.connections):
            self._remove_connection_item(conn)
        self.graph.remove_node(item.node_instance.id)
        self.node_items.pop(item.node_instance.id, None)
        self.removeItem(item)
        self.graph_changed.emit()

    def _remove_connection_item(self, conn: ConnectionGraphicsItem):
        self.graph.disconnect(conn.connection_id)
        self.connection_items.pop(conn.connection_id, None)
        for port in (conn.source_port, conn.target_port):
            if conn in port.node_item.connections:
                port.node_item.connections.remove(conn)
        self.removeItem(conn)

    # ---------- تعامل ماوس: کشیدن اتصال بین پورت‌ها ----------

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform()) if self.views() else None
        port = self._find_port_at(event.scenePos())
        if port is not None and port.direction == "out":
            self._drag_source_port = port
            self._temp_path_item = QGraphicsPathItem()
            self._temp_path_item.setPen(QPen(QColor("#BBBBBB"), 2, Qt.DashLine))
            self._temp_path_item.setZValue(20)
            self.addItem(self._temp_path_item)
            event.accept()
            return
        super().mousePressEvent(event)

        # کلیک روی یک Node -> اطلاع به Property Panel
        clicked_node_item = None
        for it in self.items(event.scenePos()):
            if isinstance(it, NodeGraphicsItem):
                clicked_node_item = it
                break
        self.node_selected.emit(clicked_node_item.node_instance if clicked_node_item else None)

    def mouseMoveEvent(self, event):
        if self._drag_source_port is not None and self._temp_path_item is not None:
            p1 = self._drag_source_port.scene_center()
            p2 = event.scenePos()
            path = QPainterPath(p1)
            path.lineTo(p2)
            self._temp_path_item.setPath(path)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_source_port is not None:
            target_port = self._find_port_at(event.scenePos())
            if self._temp_path_item is not None:
                self.removeItem(self._temp_path_item)
                self._temp_path_item = None

            if (target_port is not None and target_port.direction == "in"
                    and target_port.node_item is not self._drag_source_port.node_item):
                self._create_connection(self._drag_source_port, target_port)

            self._drag_source_port = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _find_port_at(self, scene_pos: QPointF) -> PortItem | None:
        for item in self.items(scene_pos):
            if isinstance(item, PortItem):
                return item
        # همچنین تلورانس بیشتر: بررسی نزدیک‌ترین پورت هر Node زیر ماوس
        for item in self.items(scene_pos):
            if isinstance(item, NodeGraphicsItem):
                port = item.port_at(scene_pos)
                if port:
                    return port
        return None

    def _create_connection(self, source_port: PortItem, target_port: PortItem):
        # اگر پورت ورودی قبلاً اتصال داشت، اول آن را حذف کن (هر ورودی فقط یک منبع دارد)
        existing = [c for c in target_port.node_item.connections
                    if c.target_port is target_port]
        for c in existing:
            self._remove_connection_item(c)

        try:
            conn = self.graph.connect(
                source_port.node_item.node_instance.id, source_port.name,
                target_port.node_item.node_instance.id, target_port.name,
            )
        except KeyError:
            return

        conn_item = ConnectionGraphicsItem(conn.id, source_port, target_port)
        self.addItem(conn_item)
        self.connection_items[conn.id] = conn_item
        self.graph_changed.emit()


class NodeEditorView(QGraphicsView):
    """QGraphicsView با zoom (چرخ ماوس) و پن روان."""

    def __init__(self, scene: NodeEditorScene):
        super().__init__(scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
