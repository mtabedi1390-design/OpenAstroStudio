"""
engine/codegen.py
-------------------
تبدیل Graph به یک اسکریپت پایتون خوانا و واقعی.

این بخش، اصل "شفافیت" طرح اولیه را پیاده می‌کند: کاربر همیشه می‌تواند
دقیقاً همان کدی را ببیند که اجرا می‌شود، آن را کپی کند، در Jupyter
Notebook اجرا کند یا حتی خارج از AstroStudio از آن استفاده کند.
"""

from __future__ import annotations

from .graph import Graph
from .node import NodeInstance


def _format_value(value) -> str:
    """مقدار پارامتر را به یک literal پایتونی معتبر تبدیل می‌کند."""
    if isinstance(value, str):
        return repr(value)
    return repr(value)


def generate_code(graph: Graph) -> str:
    """
    خروجی: یک رشته‌ی کد پایتون کامل و قابل‌اجرا، شامل:
      1. importهای لازم (بدون تکرار)
      2. یک خط برای هر Node، به ترتیب اجرای صحیح (Dependency Solver)
    """
    order = graph.execution_order()

    imports: list[str] = []
    seen_imports = set()
    for node in order:
        imp = node.spec.import_path
        if imp not in seen_imports:
            seen_imports.add(imp)
            imports.append(imp)

    lines: list[str] = []
    lines.extend(imports)
    lines.append("")

    for node in order:
        args = _build_call_arguments(graph, node)
        call_expr = f"{node.spec.callable_ref.__name__}({args})"
        var = node.var_name()
        lines.append(f"{var} = {call_expr}  # {node.label}")

    return "\n".join(lines)


def _build_call_arguments(graph: Graph, node: NodeInstance) -> str:
    """
    برای یک Node، رشته‌ی آرگومان‌های فراخوانی را می‌سازد؛ با در نظر گرفتن
    این‌که هر پارامتر ممکن است:
      (الف) به خروجی یک Node دیگر وصل باشد (از طریق Connection), یا
      (ب) مقدار ثابتی داشته باشد که کاربر در پنل تنظیم کرده.
    """
    incoming = {c.target_port: c for c in graph.incoming_connections(node.id)}

    parts: list[str] = []
    for param in node.spec.params:
        if param.name in incoming:
            conn = incoming[param.name]
            source_node = graph.nodes[conn.source_node_id]
            parts.append(f"{param.name}={source_node.var_name()}")
        elif param.name in node.param_values:
            parts.append(f"{param.name}={_format_value(node.param_values[param.name])}")
        elif param.required:
            parts.append(f"{param.name}=None  # TODO: مقدار این پارامتر تنظیم نشده است")

    return ", ".join(parts)
