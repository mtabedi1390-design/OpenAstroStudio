"""
engine/errors.py
------------------
سلسله‌مراتب خطاهای AstroStudio.

همه‌ی خطاهای قابل‌انتظار موتور از `AstroStudioError` ارث می‌برند تا لایه‌ی GUI
بتواند خطاهای «قابل نمایش به کاربر» را از باگ‌های واقعی برنامه تشخیص دهد.
"""

from __future__ import annotations


class AstroStudioError(Exception):
    """پایه‌ی همه‌ی خطاهای AstroStudio."""


class ReflectionError(AstroStudioError):
    """وقتی ساخت NodeSpec از یک تابع/کلاس پایتون ممکن نیست."""


class GraphError(AstroStudioError):
    """پایه‌ی خطاهای مربوط به ساخت یا اعتبارسنجی گراف."""


class GraphCycleError(GraphError):
    """وقتی گراف دارای وابستگی حلقوی باشد (A به B و B به A وابسته است)."""


class InvalidConnectionError(GraphError):
    """وقتی اتصال درخواست‌شده معتبر نیست (Node یا پورت ناموجود، اتصال به خود)."""


class MissingParameterError(AstroStudioError):
    """وقتی پارامتر اجباری یک Node نه مقدار ثابت دارد و نه به Node دیگری وصل است."""

    def __init__(self, node_id: str, node_label: str, param_name: str):
        self.node_id = node_id
        self.node_label = node_label
        self.param_name = param_name
        super().__init__(
            f"پارامتر اجباری '{param_name}' در Node '{node_label}' ({node_id}) "
            "تنظیم نشده و به هیچ Node دیگری هم وصل نیست"
        )


class NodeExecutionError(AstroStudioError):
    """خطای رخ‌داده هنگام اجرای یک Node مشخص؛ خطای اصلی را حفظ می‌کند."""

    def __init__(self, node_id: str, node_label: str, original: BaseException):
        self.node_id = node_id
        self.node_label = node_label
        self.original = original
        super().__init__(
            f"اجرای Node '{node_label}' ({node_id}) شکست خورد: "
            f"{type(original).__name__}: {original}"
        )
