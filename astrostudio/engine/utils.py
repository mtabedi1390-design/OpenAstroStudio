"""
engine/utils.py
----------------
کمک‌تابع‌های کوچک مشترک بین لایه‌ی موتور و GUI.
"""

from __future__ import annotations


def format_exception(exc: BaseException) -> str:
    """پیام یکدست خطا برای نمایش به کاربر: «TypeError: ...»."""
    return f"{type(exc).__name__}: {exc}"
