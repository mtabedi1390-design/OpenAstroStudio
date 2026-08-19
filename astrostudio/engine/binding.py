"""
engine/binding.py
-------------------
منطق مشترک «هر پارامتر یک Node از کجا مقدار می‌گیرد؟».

codegen و executor هر دو به همین سؤال نیاز دارند (یکی برای ساختن متن کد و
دیگری برای ساختن kwargs واقعی)، پس این تصمیم فقط یک بار -- همین‌جا -- گرفته
می‌شود تا رفتار کد تولیدشده و اجرای مستقیم همیشه یکسان بماند.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .graph import Graph
from .node import Connection, NodeInstance, ParamSpec


def incoming_by_port(graph: Graph, node_id: str) -> dict[str, Connection]:
    """اتصال‌های ورودی یک Node را بر اساس نام پورت هدف ایندکس می‌کند."""
    return {c.target_port: c for c in graph.incoming_connections(node_id)}


@dataclass
class ParamBinding:
    """منبع مقدار یک پارامتر: یا خروجی Node دیگر، یا مقدار ثابت، یا هیچ."""

    param: ParamSpec
    source: NodeInstance | None = None
    value: Any = None
    has_value: bool = False

    @property
    def name(self) -> str:
        return self.param.name

    @property
    def is_connected(self) -> bool:
        return self.source is not None

    @property
    def is_missing_required(self) -> bool:
        return self.source is None and not self.has_value and self.param.required


def param_bindings(graph: Graph, node: NodeInstance) -> list[ParamBinding]:
    """برای هر پارامتر Node، به ترتیب امضای اصلی، یک ParamBinding می‌سازد."""
    incoming = incoming_by_port(graph, node.id)

    bindings: list[ParamBinding] = []
    for param in node.spec.params:
        conn = incoming.get(param.name)
        if conn is not None:
            bindings.append(ParamBinding(param=param,
                                         source=graph.nodes[conn.source_node_id]))
        elif param.name in node.param_values:
            bindings.append(ParamBinding(param=param,
                                         value=node.param_values[param.name],
                                         has_value=True))
        else:
            bindings.append(ParamBinding(param=param))
    return bindings
