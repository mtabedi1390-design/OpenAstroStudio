"""
gui/library_panel.py
-----------------------
لیست بلوک‌های موجود، گروه‌بندی‌شده بر اساس category. با دابل‌کلیک روی هر
مورد، یک Node جدید در مرکز بوم فعلی ساخته می‌شود.

منبع این لیست: engine.library_scanner.scan_module (خودکار) یا
engine.overrides (دستی، برای کلاس‌های پیچیده).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem

from ..engine.node import NodeSpec


class LibraryPanel(QWidget):
    node_double_clicked = Signal(object)  # NodeSpec

    def __init__(self):
        super().__init__()
        self._specs: dict[str, NodeSpec] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("کتابخانه‌ی بلوک‌ها"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.tree)

    def load_specs(self, specs: list[NodeSpec]):
        self.tree.clear()
        self._specs.clear()
        categories: dict[str, QTreeWidgetItem] = {}

        for spec in specs:
            self._specs[spec.id] = spec
            cat = spec.category or "بدون دسته"
            if cat not in categories:
                cat_item = QTreeWidgetItem([cat])
                self.tree.addTopLevelItem(cat_item)
                categories[cat] = cat_item
            leaf = QTreeWidgetItem([spec.display_name])
            leaf.setData(0, 32, spec.id)  # Qt.UserRole = 32
            categories[cat].addChild(leaf)

        self.tree.expandAll()

    def _on_double_clicked(self, item: QTreeWidgetItem, _col: int):
        spec_id = item.data(0, 32)
        if spec_id and spec_id in self._specs:
            self.node_double_clicked.emit(self._specs[spec_id])
