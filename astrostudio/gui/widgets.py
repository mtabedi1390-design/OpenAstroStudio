"""
gui/widgets.py
----------------
کمک‌تابع‌های ساخت ویجت‌های تکراری GUI (پنل کد، کنسول، ...).
"""

from __future__ import annotations

from PySide6.QtWidgets import QTextEdit

MONOSPACE_STYLE = "font-family: monospace; font-size: 11px;"


def make_monospace_view(*, text_color: str | None = None,
                        background: str | None = None) -> QTextEdit:
    """یک QTextEdit فقط-خواندنی با فونت مونواسپیس (برای نمایش کد یا لاگ)."""
    view = QTextEdit()
    view.setReadOnly(True)
    style = MONOSPACE_STYLE
    if text_color:
        style += f" color: {text_color};"
    if background:
        style += f" background: {background};"
    view.setStyleSheet(style)
    return view
