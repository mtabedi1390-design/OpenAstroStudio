"""
engine/library_scanner.py
--------------------------
یک ماژول پایتون (مثلاً astropy.coordinates) را اسکن می‌کند و برای هر
تابع/کلاس عمومی آن، با استفاده از ReflectionEngine یک NodeSpec می‌سازد.

این ماژول همان چیزی است که در طرح اولیه "libraries/astropy" نامیده شده بود:
پلی خودکار بین یک کتابخانه‌ی پایتون و مجموعه‌ای از بلوک‌های گرافیکی.
"""

from __future__ import annotations

import importlib
import inspect
from types import ModuleType
from typing import Iterable

from .node import NodeSpec
from .reflection import reflect


def safe_reflect(callable_ref, *, category: str = "") -> NodeSpec | None:
    """
    reflect با تحمل خطا: اگر یک عضو خاص قابل reflect نبود (مثلاً امضای
    عجیبی دارد) به‌جای توقف کل اسکن، None برمی‌گرداند.
    """
    try:
        return reflect(callable_ref, category=category)
    except Exception:
        return None


def scan_module(module: ModuleType | str, *,
                 include: Iterable[str] | None = None,
                 exclude: Iterable[str] | None = None,
                 max_items: int | None = None) -> list[NodeSpec]:
    """
    ماژول را اسکن کرده و لیستی از NodeSpec برمی‌گرداند.

    include/exclude: لیست نام‌های دقیق برای فیلتر کردن (اگر داده نشود، همه‌ی
    اعضای عمومی -- یعنی بدون آندرلاین پیشوندی -- در نظر گرفته می‌شوند).
    max_items: برای جلوگیری از overload در اسکن کتابخانه‌های بسیار بزرگ.
    """
    if isinstance(module, str):
        module = importlib.import_module(module)

    include_set = set(include) if include else None
    exclude_set = set(exclude) if exclude else set()

    specs: list[NodeSpec] = []
    for name, member in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        if include_set is not None and name not in include_set:
            continue
        if name in exclude_set:
            continue
        if not (inspect.isfunction(member) or inspect.isclass(member)):
            continue
        # فقط اعضایی که واقعاً متعلق به همین ماژول هستند (نه import شده از جای دیگر)
        member_module = getattr(member, "__module__", "")
        if member_module and not member_module.startswith(module.__name__.split(".")[0]):
            continue

        spec = safe_reflect(member, category=module.__name__)
        if spec is None:
            continue
        specs.append(spec)

        if max_items is not None and len(specs) >= max_items:
            break

    return specs


def scan_callable_list(callables: Iterable, category: str = "") -> list[NodeSpec]:
    """نسخه‌ی ساده‌تر: لیست مشخصی از توابع/کلاس‌ها را مستقیماً reflect می‌کند."""
    specs = [safe_reflect(c, category=category) for c in callables]
    return [s for s in specs if s is not None]
