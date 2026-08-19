"""
engine/overrides.py
---------------------
چرا این فایل لازم است؟

Reflection خودکار برای اکثر توابع پایتون عالی کار می‌کند، اما برخی کلاس‌های
علمی پرکاربرد (مثل astropy.coordinates.SkyCoord) امضای واقعی‌شان را پشت
`*args, **kwargs` پنهان می‌کنند و پارامترهای واقعی (ra, dec, unit, frame, ...)
فقط در مستندات و در زمان اجرا مشخص می‌شوند -- نه در `inspect.signature`.

راه‌حل عملی (و رایج در چنین پروژه‌هایی): برای درصد کوچکی از پرکاربردترین
کلاس‌ها، به‌جای reflect خودکار، یک NodeSpec دستی و دقیق تعریف می‌کنیم.
بقیه‌ی هزاران تابع کتابخانه همچنان به‌طور کامل خودکار پوشش داده می‌شوند.

این الگو دقیقاً همان چیزی است که در بخش "libraries/" طرح اصلی پیش‌بینی شده بود:
هر کتابخانه می‌تواند یک ماژول override اختصاصی داشته باشد.
"""

from __future__ import annotations

from astropy.coordinates import SkyCoord

from .node import (
    NodeSpec, ParamSpec, input_ports_from_params, result_output_ports,
)


def skycoord_node_spec() -> NodeSpec:
    """NodeSpec دستی برای SkyCoord با پارامترهای واقعی‌ای که کاربران استفاده می‌کنند."""
    params = [
        ParamSpec(name="ra", annotation="float", default=0.0, has_default=True,
                   required=False, description="طول جغرافیایی آسمانی (Right Ascension)"),
        ParamSpec(name="dec", annotation="float", default=0.0, has_default=True,
                   required=False, description="عرض جغرافیایی آسمانی (Declination)"),
        ParamSpec(name="unit", annotation="str", default="deg", has_default=True,
                   required=False, description="واحد اندازه‌گیری، مثل 'deg' یا 'hourangle,deg'"),
        ParamSpec(name="frame", annotation="str", default="icrs", has_default=True,
                   required=False, description="سیستم مرجع مختصات، مثل 'icrs', 'galactic'"),
    ]
    inputs = input_ports_from_params(params)
    outputs = result_output_ports("SkyCoord", "شیء مختصات ساخته‌شده")

    return NodeSpec(
        id="astropy.coordinates.SkyCoord.manual",
        display_name="Coordinate (ICRS)",
        category="astropy.coordinates",
        description="یک نقطه‌ی مختصات آسمانی می‌سازد (override دستی به‌دلیل امضای پویای SkyCoord).",
        doc_full=SkyCoord.__doc__ or "",
        params=params,
        inputs=inputs,
        outputs=outputs,
        callable_ref=SkyCoord,
        import_path="from astropy.coordinates import SkyCoord",
        kind="class",
    )


# رجیستری ساده: نگاشت از مسیر کامل کلاس/تابع به تابعی که NodeSpec دستی می‌سازد.
# GUI و library_scanner می‌توانند قبل از reflect خودکار، این رجیستری را چک کنند.
MANUAL_OVERRIDES = {
    "astropy.coordinates.SkyCoord": skycoord_node_spec,
}
