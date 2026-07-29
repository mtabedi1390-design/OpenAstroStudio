"""
gui/property_panel.py
------------------------
پنل سمت راست طرح اصلی:

    Coordinate Converter
    -------------------------
    RA
    DEC
    Frame
    -------------------------
    Documentation
    -------------------------
    Generated Python Code
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel,
    QTextEdit, QGroupBox, QScrollArea,
)

from ..engine.node import NodeInstance


class PropertyPanel(QWidget):
    value_changed = Signal()

    def __init__(self):
        super().__init__()
        self.current_node: NodeInstance | None = None
        self._editors: dict[str, QLineEdit] = {}

        outer = QVBoxLayout(self)
        self.title_label = QLabel("هیچ Node ای انتخاب نشده")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        outer.addWidget(self.title_label)

        self.params_group = QGroupBox("پارامترها")
        self.params_form = QFormLayout()
        self.params_group.setLayout(self.params_form)
        outer.addWidget(self.params_group)

        outer.addWidget(QLabel("مستندات:"))
        self.doc_view = QTextEdit()
        self.doc_view.setReadOnly(True)
        self.doc_view.setMaximumHeight(140)
        outer.addWidget(self.doc_view)

        outer.addStretch()

    def show_node(self, node: NodeInstance | None):
        self.current_node = node
        self._editors.clear()
        while self.params_form.rowCount() > 0:
            self.params_form.removeRow(0)

        if node is None:
            self.title_label.setText("هیچ Node ای انتخاب نشده")
            self.doc_view.setPlainText("")
            return

        self.title_label.setText(f"{node.label}  ({node.spec.kind})")
        self.doc_view.setPlainText(node.spec.doc_full or node.spec.description)

        for param in node.spec.params:
            editor = QLineEdit()
            current = node.param_values.get(param.name, param.default if param.has_default else "")
            editor.setText("" if current is None else str(current))
            editor.setPlaceholderText(param.annotation)
            editor.editingFinished.connect(
                lambda p=param.name, e=editor: self._on_param_edited(p, e)
            )
            label_text = param.name + ("" if param.required else " (اختیاری)")
            self.params_form.addRow(label_text, editor)
            self._editors[param.name] = editor

    def _on_param_edited(self, param_name: str, editor: QLineEdit):
        if self.current_node is None:
            return
        text = editor.text()
        self.current_node.param_values[param_name] = _coerce(text)
        self.value_changed.emit()


def _coerce(text: str):
    """سعی می‌کند مقدار وارد شده در پنل را به نوع مناسب (عدد/بولین/رشته) تبدیل کند."""
    if text == "":
        return None
    lowered = text.strip().lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        if "." in text or "e" in lowered:
            return float(text)
        return int(text)
    except ValueError:
        return text
