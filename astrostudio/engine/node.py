"""
engine/node.py
--------------
دیتاکلاس‌های پایه‌ی سیستم Node.

یک NodeSpec توصیف "نوع" یک بلوک است (مثلاً تابع SkyCoord از astropy.coordinates)
و توسط ReflectionEngine به‌صورت خودکار از یک تابع/کلاس پایتون تولید می‌شود.

یک NodeInstance نمونه‌ای از NodeSpec است که روی بوم (canvas) قرار گرفته،
مقادیر پارامترهایش تنظیم شده و ممکن است به Instanceهای دیگر وصل باشد.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import itertools

_id_counter = itertools.count(1)


def _next_id(prefix: str) -> str:
    return f"{prefix}_{next(_id_counter)}"


@dataclass
class ParamSpec:
    """توصیف یک پارامتر ورودی تابع/کلاس اصلی."""

    name: str
    annotation: str = "Any"          # نمایش متنی نوع، برای GUI
    default: Any = None
    has_default: bool = False
    required: bool = True
    description: str = ""            # از docstring استخراج می‌شود
    kind: str = "POSITIONAL_OR_KEYWORD"  # از inspect.Parameter.kind


@dataclass
class PortSpec:
    """یک پورت ورودی یا خروجی که می‌تواند به Nodeهای دیگر وصل شود."""

    name: str
    annotation: str = "Any"
    description: str = ""
    direction: str = "in"  # "in" | "out"


@dataclass
class NodeSpec:
    """
    توصیف کامل یک "نوع" بلوک - نتیجه‌ی نهایی ReflectionEngine.
    این شیء تغییرناپذیر (immutable) در نظر گرفته می‌شود؛ یک بار ساخته و
    برای ساخت چندین NodeInstance استفاده می‌شود.
    """

    id: str                       # مسیر کامل مثل "astropy.coordinates.SkyCoord"
    display_name: str             # نام نمایشی مثل "Coordinate Converter"
    category: str                 # دسته‌بندی برای منو، مثل "astropy.coordinates"
    description: str              # خلاصه‌ی docstring
    doc_full: str                 # docstring کامل
    params: list[ParamSpec]
    inputs: list[PortSpec]
    outputs: list[PortSpec]
    callable_ref: Callable         # ارجاع واقعی به تابع/کلاس پایتون
    import_path: str              # مثلاً "from astropy.coordinates import SkyCoord"
    kind: str = "function"        # "function" | "class" | "method"
    icon: str = "\U0001F4E6"
    color: str = "#4C7EA8"


@dataclass
class Connection:
    """اتصال بین پورت خروجی یک Node و پورت ورودی Node دیگر."""

    id: str
    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str

    @staticmethod
    def create(source_node_id: str, source_port: str,
               target_node_id: str, target_port: str) -> "Connection":
        return Connection(
            id=_next_id("conn"),
            source_node_id=source_node_id,
            source_port=source_port,
            target_node_id=target_node_id,
            target_port=target_port,
        )


@dataclass
class NodeInstance:
    """نمونه‌ی واقعی یک Node روی بوم، همراه با مقادیر پارامترها و موقعیت گرافیکی."""

    id: str
    spec: NodeSpec
    param_values: dict[str, Any] = field(default_factory=dict)
    position: tuple[float, float] = (0.0, 0.0)
    label: str = ""

    @staticmethod
    def create(spec: NodeSpec, position: tuple[float, float] = (0.0, 0.0)) -> "NodeInstance":
        values = {
            p.name: p.default for p in spec.params if p.has_default
        }
        return NodeInstance(
            id=_next_id("node"),
            spec=spec,
            param_values=values,
            position=position,
            label=spec.display_name,
        )

    def var_name(self) -> str:
        """نام متغیر پایتون که در کد تولیدشده برای خروجی این Node استفاده می‌شود."""
        return f"n_{self.id}"


def has_value(node: NodeInstance, param: ParamSpec) -> bool:
    """آیا کاربر برای این پارامتر مقدار قابل‌استفاده‌ای تنظیم کرده است؟

    خالی گذاشتن یک ورودی اجباری در پنل، مقدار None ذخیره می‌کند؛ آن را
    «تنظیم‌نشده» می‌شماریم تا به‌جای خطای مبهم کتابخانه (مثل TypeError روی None)
    خطای واضح MissingParameterError داده شود.
    """
    if param.name not in node.param_values:
        return False
    return not (param.required and node.param_values[param.name] is None)
