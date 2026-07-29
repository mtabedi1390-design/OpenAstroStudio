"""
engine/graph.py
----------------
نگهداری گراف Nodeها و Connectionها، به‌علاوه‌ی محاسبه‌ی ترتیب اجرا
(Dependency Solver -> Execution Order) که در طرح اصلی توضیح داده شده بود.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .node import NodeInstance, Connection


class GraphCycleError(Exception):
    """وقتی گراف دارای وابستگی حلقوی باشد (A به B و B به A وابسته است)."""


@dataclass
class Graph:
    nodes: dict[str, NodeInstance] = field(default_factory=dict)
    connections: dict[str, Connection] = field(default_factory=dict)

    # ---------- ساخت گراف ----------

    def add_node(self, node: NodeInstance) -> None:
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        to_remove = [
            cid for cid, c in self.connections.items()
            if c.source_node_id == node_id or c.target_node_id == node_id
        ]
        for cid in to_remove:
            del self.connections[cid]

    def connect(self, source_node_id: str, source_port: str,
                target_node_id: str, target_port: str) -> Connection:
        if source_node_id not in self.nodes or target_node_id not in self.nodes:
            raise KeyError("هر دو Node باید قبلاً به گراف اضافه شده باشند")
        conn = Connection.create(source_node_id, source_port, target_node_id, target_port)
        self.connections[conn.id] = conn
        return conn

    def disconnect(self, connection_id: str) -> None:
        self.connections.pop(connection_id, None)

    # ---------- کوئری‌ها ----------

    def incoming_connections(self, node_id: str) -> list[Connection]:
        return [c for c in self.connections.values() if c.target_node_id == node_id]

    def outgoing_connections(self, node_id: str) -> list[Connection]:
        return [c for c in self.connections.values() if c.source_node_id == node_id]

    # ---------- Dependency Solver ----------

    def execution_order(self) -> list[NodeInstance]:
        """
        مرتب‌سازی توپولوژیک Kahn: هر Node فقط پس از تمام Nodeهایی که
        به آن‌ها ورودی وصل است اجرا می‌شود.
        """
        in_degree = {nid: 0 for nid in self.nodes}
        for c in self.connections.values():
            in_degree[c.target_node_id] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        ordered_ids: list[str] = []

        while queue:
            queue.sort()  # ترتیب پایدار و قابل‌پیش‌بینی
            nid = queue.pop(0)
            ordered_ids.append(nid)
            for c in self.outgoing_connections(nid):
                in_degree[c.target_node_id] -= 1
                if in_degree[c.target_node_id] == 0:
                    queue.append(c.target_node_id)

        if len(ordered_ids) != len(self.nodes):
            raise GraphCycleError("گراف شامل وابستگی حلقوی است و قابل اجرا نیست")

        return [self.nodes[nid] for nid in ordered_ids]

    def to_dict(self) -> dict:
        """برای سریالایز کردن پروژه (ذخیره/بارگذاری .astroproj)."""
        return {
            "nodes": {
                nid: {
                    "spec_id": n.spec.id,
                    "param_values": n.param_values,
                    "position": n.position,
                    "label": n.label,
                }
                for nid, n in self.nodes.items()
            },
            "connections": {
                cid: {
                    "source_node_id": c.source_node_id,
                    "source_port": c.source_port,
                    "target_node_id": c.target_node_id,
                    "target_port": c.target_port,
                }
                for cid, c in self.connections.items()
            },
        }
