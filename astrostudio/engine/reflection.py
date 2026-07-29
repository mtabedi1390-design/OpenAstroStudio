"""
engine/reflection.py
---------------------
مهم‌ترین بخش پروژه: تبدیل خودکار یک تابع/کلاس پایتون به NodeSpec.

جریان:
    Python Callable -> inspect.signature -> docstring_parser -> NodeSpec

این ماژول مستقیماً به کتابخانه‌ی خاصی (astropy و ...) وابسته نیست؛
هر Callable قابل inspect را می‌پذیرد. این یعنی همان موتور می‌تواند فردا
برای scipy یا هر کتابخانه‌ی دیگری هم استفاده شود -- دقیقاً مطابق چشم‌انداز
"محیط گرافیکی عمومی برای محاسبات علمی".
"""

from __future__ import annotations

import inspect
import typing
from typing import Any, Callable, Optional

try:
    import docstring_parser
    _HAS_DOCSTRING_PARSER = True
except ImportError:  # پروژه باید حتی بدون این کتابخانه هم کار کند (fallback ساده‌تر)
    _HAS_DOCSTRING_PARSER = False

from .node import NodeSpec, ParamSpec, PortSpec


def _annotation_to_str(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "Any"
    if isinstance(annotation, str):
        return annotation
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _parse_docstring(doc: Optional[str]) -> tuple[str, dict[str, str], str]:
    """
    برمی‌گرداند: (خلاصه‌ی یک‌خطی، دیکشنری {نام‌پارامتر: توضیح}, بازگشت کامل)

    اگر docstring_parser نصب نباشد، یک fallback خیلی ساده استفاده می‌شود که
    فقط خط اول را به‌عنوان خلاصه برمی‌گرداند.
    """
    doc = doc or ""
    if not doc.strip():
        return "", {}, ""

    if _HAS_DOCSTRING_PARSER:
        try:
            parsed = docstring_parser.parse(doc)
            summary = parsed.short_description or ""
            param_docs = {
                p.arg_name: (p.description or "")
                for p in parsed.params
                if p.arg_name
            }
            return summary, param_docs, doc
        except Exception:
            pass  # اگر پارس شکست خورد، به fallback برو

    first_line = doc.strip().splitlines()[0].strip()
    return first_line, {}, doc


def _guess_output_type(callable_ref: Callable, is_class: bool) -> str:
    if is_class:
        return getattr(callable_ref, "__name__", "object")
    try:
        sig = inspect.signature(callable_ref)
        return _annotation_to_str(sig.return_annotation)
    except (ValueError, TypeError):
        return "Any"


def reflect(callable_ref: Callable, *, category: str = "",
            display_name: Optional[str] = None,
            import_path: Optional[str] = None) -> NodeSpec:
    """
    نقطه‌ی ورود اصلی موتور Reflection.

    یک تابع یا کلاس پایتون می‌گیرد و یک NodeSpec کامل تولید می‌کند که
    شامل پارامترها، پورت‌های ورودی/خروجی و مستندات است.
    """
    is_class = inspect.isclass(callable_ref)

    # برای کلاس‌ها، امضای __init__ مهم است (بدون self)
    target_for_signature = callable_ref.__init__ if is_class else callable_ref
    try:
        sig = inspect.signature(target_for_signature)
    except (ValueError, TypeError):
        sig = inspect.Signature()

    raw_doc = inspect.getdoc(callable_ref) or ""
    summary, param_docs, full_doc = _parse_docstring(raw_doc)

    params: list[ParamSpec] = []
    inputs: list[PortSpec] = []

    for name, p in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue  # *args / **kwargs فعلاً پشتیبانی نمی‌شوند (نسخه‌ی بعدی)

        has_default = p.default is not inspect.Parameter.empty
        param_spec = ParamSpec(
            name=name,
            annotation=_annotation_to_str(p.annotation),
            default=p.default if has_default else None,
            has_default=has_default,
            required=not has_default,
            description=param_docs.get(name, ""),
            kind=str(p.kind),
        )
        params.append(param_spec)

        # هر پارامتر همزمان یک "پورت ورودی" هم هست -> می‌تواند از خروجی
        # Node دیگری هم مقدار بگیرد، یا از پنل مقدار ثابت بگیرد.
        inputs.append(PortSpec(
            name=name,
            annotation=param_spec.annotation,
            description=param_spec.description,
            direction="in",
        ))

    output_type = _guess_output_type(callable_ref, is_class)
    outputs = [PortSpec(name="result", annotation=output_type,
                         description="خروجی این بلوک", direction="out")]

    module = getattr(callable_ref, "__module__", "")
    qualname = getattr(callable_ref, "__qualname__", getattr(callable_ref, "__name__", "node"))
    node_id = f"{module}.{qualname}" if module else qualname

    if import_path is None:
        name = getattr(callable_ref, "__name__", qualname)
        import_path = f"from {module} import {name}" if module else f"import {name}"

    return NodeSpec(
        id=node_id,
        display_name=display_name or getattr(callable_ref, "__name__", qualname),
        category=category or module,
        description=summary,
        doc_full=full_doc,
        params=params,
        inputs=inputs,
        outputs=outputs,
        callable_ref=callable_ref,
        import_path=import_path,
        kind="class" if is_class else "function",
    )
