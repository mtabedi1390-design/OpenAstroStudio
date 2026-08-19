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

import logging
import traceback
from dataclasses import dataclass, field
from typing import Any

from .errors import AstroStudioError, MissingParameterError, NodeExecutionError
from .graph import Graph
from .node import NodeInstance, has_value
from .codegen import generate_code

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    results: dict[str, Any] = field(default_factory=dict)   # node_id -> خروجی
    generated_code: str = ""
    error: str | None = None
    error_node_id: str | None = None      # اگر خطا مربوط به یک Node مشخص باشد
    traceback_text: str | None = None     # تریس‌بک کامل برای دیباگ
    exception: BaseException | None = None  # خطای اصلی، برای فراخواننده‌های برنامه‌ای

    def raise_if_failed(self) -> ExecutionResult:
        """برای کدهای غیرGUI (اسکریپت، تست): خطای اجرا را دوباره raise می‌کند."""
        if not self.success:
            if self.exception is not None:
                raise self.exception
            raise AstroStudioError(self.error or "اجرای گراف شکست خورد")
        return self


def execute_direct(graph: Graph) -> ExecutionResult:
    """گراف را اجرا می‌کند و خطاها را در ExecutionResult برمی‌گرداند.

    خطای ساختاری گراف (مثلاً حلقه) هم مانند خطای اجرای Node گزارش می‌شود؛
    قبلاً این دسته خطاها به بیرون پرتاب می‌شدند و در GUI بدون مدیریت می‌ماندند.
    """
    results: dict[str, Any] = {}

    try:
        order = graph.execution_order()
    except Exception as exc:  # هر خطای گراف باید به کاربر نشان داده شود
        logger.exception("محاسبه‌ی ترتیب اجرا شکست خورد")
        return _failure(exc, results=results, code="")

    code = _safe_generate_code(graph)

    for node in order:
        try:
            kwargs = _resolve_kwargs(graph, node, results)
        except AstroStudioError as exc:
            logger.error("ورودی‌های Node %s قابل تعیین نیست: %s", node.id, exc)
            return _failure(exc, results=results, code=code, node_id=node.id)

        try:
            results[node.id] = node.spec.callable_ref(**kwargs)
        except Exception as exc:  # خطای کتابخانه‌ی کاربر
            wrapped = NodeExecutionError(node.id, node.label, exc)
            logger.exception("اجرای Node %s (%s) شکست خورد", node.id, node.label)
            return _failure(wrapped, results=results, code=code, node_id=node.id,
                            traceback_source=exc)

    return ExecutionResult(success=True, results=results, generated_code=code)


def _failure(exc: BaseException, *, results: dict[str, Any], code: str,
              node_id: str | None = None,
              traceback_source: BaseException | None = None) -> ExecutionResult:
    source = traceback_source if traceback_source is not None else exc
    return ExecutionResult(
        success=False,
        results=results,
        generated_code=code,
        error=f"{type(exc).__name__}: {exc}",
        error_node_id=node_id,
        traceback_text="".join(
            traceback.format_exception(type(source), source, source.__traceback__)
        ),
        exception=exc,
    )


def _safe_generate_code(graph: Graph) -> str:
    """تولید کد برای نمایش؛ شکست آن نباید خطای اصلی اجرا را پنهان کند."""
    try:
        return generate_code(graph)
    except Exception:  
        logger.exception("تولید کد برای نمایش شکست خورد")
        return ""


def _resolve_kwargs(graph: Graph, node: NodeInstance,
                     results: dict[str, Any]) -> dict[str, Any]:
    incoming = {c.target_port: c for c in graph.incoming_connections(node.id)}
    kwargs: dict[str, Any] = {}
    for param in node.spec.params:
        if param.name in incoming:
            conn = incoming[param.name]
            if conn.source_node_id not in results:
                # فقط وقتی رخ می‌دهد که ترتیب اجرا نامعتبر باشد -> باید بلند باشد
                raise AstroStudioError(
                    f"خروجی Node منبع '{conn.source_node_id}' برای پارامتر "
                    f"'{param.name}' در Node '{node.label}' موجود نیست"
                )
            kwargs[param.name] = results[conn.source_node_id]
        elif has_value(node, param):
            kwargs[param.name] = node.param_values[param.name]
        elif param.required:
            raise MissingParameterError(node.id, node.label, param.name)
    return kwargs


def execute_generated_code(graph: Graph) -> ExecutionResult:
    """
    کد را با exec واقعاً اجرا می‌کند. برای دیباگ و برای اطمینان از این‌که
    کد نمایش داده‌شده به کاربر دقیقاً قابل‌اجراست استفاده می‌شود.
    """
    try:
        order = graph.execution_order()
        code = generate_code(graph)
    except Exception as exc:  
        logger.exception("تولید کد برای اجرا شکست خورد")
        return _failure(exc, results={}, code="")

    namespace: dict[str, Any] = {}
    try:
        exec(code, namespace)  # noqa: S102 - این پروژه ذاتاً یک اجراکننده‌ی کد است
    except Exception as exc:  
        logger.exception("اجرای کد تولیدشده شکست خورد")
        return _failure(exc, results={}, code=code)

    missing = [node.id for node in order if node.var_name() not in namespace]
    if missing:
        # بدون این بررسی، نتیجه‌ی غایب به شکل یک مقدار None معتبر دیده می‌شد
        return _failure(
            AstroStudioError(
                "کد تولیدشده برای این Nodeها متغیری نساخت: " + ", ".join(missing)
            ),
            results={}, code=code,
        )

    results = {node.id: namespace[node.var_name()] for node in order}
    return ExecutionResult(success=True, results=results, generated_code=code)
