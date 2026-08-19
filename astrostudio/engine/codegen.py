"""
engine/codegen.py
-------------------
تبدیل Graph به یک اسکریپت پایتون خوانا و واقعی.

این بخش، اصل "شفافیت" طرح اولیه را پیاده می‌کند: کاربر همیشه می‌تواند
دقیقاً همان کدی را ببیند که اجرا می‌شود، آن را کپی کند، در Jupyter
Notebook اجرا کند یا حتی خارج از AstroStudio از آن استفاده کند.
"""

from __future__ import annotations

from .binding import param_bindings
from .graph import Graph
from .node import NodeInstance


def _format_value(value) -> str:
    """مقدار پارامتر را به یک literal پایتونی معتبر تبدیل می‌کند."""
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
    parts: list[str] = []
    for binding in param_bindings(graph, node):
        if binding.is_connected:
            parts.append(f"{binding.name}={binding.source.var_name()}")
        elif binding.has_value:
            parts.append(f"{binding.name}={_format_value(binding.value)}")
        elif binding.is_missing_required:
            parts.append(f"{binding.name}=None  # TODO: مقدار این پارامتر تنظیم نشده است")

    return ", ".join(parts)
