"""
engine/codegen.py
-------------------
تبدیل Graph به یک اسکریپت پایتون خوانا و واقعی.

این بخش، اصل "شفافیت" طرح اولیه را پیاده می‌کند: کاربر همیشه می‌تواند
دقیقاً همان کدی را ببیند که اجرا می‌شود، آن را کپی کند، در Jupyter
Notebook اجرا کند یا حتی خارج از AstroStudio از آن استفاده کند.
"""

from __future__ import annotations

import ast

from .graph import Graph
from .node import NodeInstance

_SAFE_LITERAL_TYPES = (str, int, float, bool, complex, type(None))


def _format_value(value) -> str:
    """مقدار پارامتر را به یک literal پایتونی معتبر و امن تبدیل می‌کند.

    فقط انواع literal ساده (و کانتینرهای آن‌ها) مجازند؛ repr اشیای دلخواه
    می‌تواند متن غیرقابل‌پیش‌بینی تولید کند که بعداً exec می‌شود.
    """
    if isinstance(value, _SAFE_LITERAL_TYPES):
        return repr(value)
    if isinstance(value, (list, tuple, set)):
        inner = ", ".join(_format_value(v) for v in value)
        if isinstance(value, list):
            return f"[{inner}]"
        if isinstance(value, set):
            return f"{{{inner}}}" if value else "set()"
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, dict):
        inner = ", ".join(f"{_format_value(k)}: {_format_value(v)}" for k, v in value.items())
        return f"{{{inner}}}"
    raise ValueError(
        f"مقدار پارامتر از نوع غیرمجاز {type(value).__name__!r} است و نمی‌تواند به کد تبدیل شود"
    )


def _sanitize_comment(text: str) -> str:
    """متن کامنت را تک‌خطی می‌کند تا نتواند کد جدیدی به اسکریپت تزریق کند."""
    return " ".join(str(text).split())


def _validate_import_path(import_path: str) -> str:
    """بررسی می‌کند که import_path واقعاً فقط یک عبارت import باشد."""
    try:
        tree = ast.parse(import_path)
    except SyntaxError as exc:
        raise ValueError(f"import_path نامعتبر است: {import_path!r}") from exc
    if not tree.body or not all(isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in tree.body):
        raise ValueError(f"import_path فقط باید شامل عبارت import باشد: {import_path!r}")
    return import_path


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
        imp = _validate_import_path(node.spec.import_path)
        if imp not in seen_imports:
            seen_imports.add(imp)
            imports.append(imp)

    lines: list[str] = []
    lines.extend(imports)
    lines.append("")

    for node in order:
        args = _build_call_arguments(graph, node)
        callable_name = node.spec.callable_ref.__name__
        if not callable_name.isidentifier():
            raise ValueError(f"نام callable نامعتبر است: {callable_name!r}")
        call_expr = f"{callable_name}({args})"
        var = node.var_name()
        lines.append(f"{var} = {call_expr}  # {_sanitize_comment(node.label)}")

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
        if not param.name.isidentifier():
            raise ValueError(f"نام پارامتر نامعتبر است: {param.name!r}")
        if param.name in incoming:
            conn = incoming[param.name]
            source_node = graph.nodes[conn.source_node_id]
            parts.append(f"{param.name}={source_node.var_name()}")
        elif param.name in node.param_values:
            parts.append(f"{param.name}={_format_value(node.param_values[param.name])}")
        elif param.required:
            parts.append(f"{param.name}=None  # TODO: مقدار این پارامتر تنظیم نشده است")

    return ", ".join(parts)
