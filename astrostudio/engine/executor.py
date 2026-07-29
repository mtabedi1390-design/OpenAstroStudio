"""
engine/executor.py
--------------------
اجرای واقعی گراف.

دو روش پشتیبانی می‌شود:

1. execute_direct(graph): هر Node را با فراخوانی مستقیم callable_ref آن
   اجرا می‌کند و نتایج را در حافظه (دیکشنری results) نگه می‌دارد.
   این روش برای Live Renderer مناسب است چون سریع است و نیازی به
   parse کردن دوباره‌ی کد ندارد.

2. execute_generated_code(graph): کدی را که codegen.generate_code تولید
   کرده، واقعاً exec می‌کند. این تضمین می‌کند که "کد نمایش داده‌شده"
   دقیقاً همان چیزی است که اجرا می‌شود (اصل شفافیت).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .graph import Graph
from .node import NodeInstance
from .codegen import generate_code


@dataclass
class ExecutionResult:
    success: bool
    results: dict[str, Any] = field(default_factory=dict)   # node_id -> خروجی
    generated_code: str = ""
    error: str | None = None


def execute_direct(graph: Graph) -> ExecutionResult:
    order = graph.execution_order()
    results: dict[str, Any] = {}

    try:
        for node in order:
            kwargs = _resolve_kwargs(graph, node, results)
            results[node.id] = node.spec.callable_ref(**kwargs)
        return ExecutionResult(success=True, results=results,
                                generated_code=generate_code(graph))
    except Exception as exc:  # noqa: BLE001 - می‌خواهیم هر خطا را به کاربر نشان دهیم
        return ExecutionResult(success=False, results=results,
                                generated_code=generate_code(graph),
                                error=f"{type(exc).__name__}: {exc}")


def _resolve_kwargs(graph: Graph, node: NodeInstance,
                     results: dict[str, Any]) -> dict[str, Any]:
    incoming = {c.target_port: c for c in graph.incoming_connections(node.id)}
    kwargs: dict[str, Any] = {}
    for param in node.spec.params:
        if param.name in incoming:
            conn = incoming[param.name]
            kwargs[param.name] = results[conn.source_node_id]
        elif param.name in node.param_values:
            kwargs[param.name] = node.param_values[param.name]
    return kwargs


def execute_generated_code(graph: Graph) -> ExecutionResult:
    """
    کد را با exec واقعاً اجرا می‌کند. برای دیباگ و برای اطمینان از این‌که
    کد نمایش داده‌شده به کاربر دقیقاً قابل‌اجراست استفاده می‌شود.
    """
    code = generate_code(graph)
    namespace: dict[str, Any] = {}
    try:
        exec(code, namespace)  # noqa: S102 - این پروژه ذاتاً یک اجراکننده‌ی کد است
        order = graph.execution_order()
        results = {node.id: namespace.get(node.var_name()) for node in order}
        return ExecutionResult(success=True, results=results, generated_code=code)
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(success=False, generated_code=code,
                                error=f"{type(exc).__name__}: {exc}")
