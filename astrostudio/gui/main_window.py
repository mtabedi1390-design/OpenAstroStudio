"""
gui/main_window.py
---------------------
چیدمان کلی که در طرح اولیه توضیح داده شد:

    Library Panel | Node Editor (Canvas) | Property Panel
    -------------------------------------------------------
                Code Panel + Console + دکمه‌ی Run
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QTextEdit, QTabWidget, QLabel, QMessageBox,
)

from ..engine.node import NodeSpec
from ..engine.codegen import generate_code
from ..engine.executor import execute_direct
from ..engine.overrides import skycoord_node_spec
from ..engine.reflection import reflect
from ..libraries.astropy_adapters import to_galactic, separation_deg

from .node_editor import NodeEditorScene, NodeEditorView
from .property_panel import PropertyPanel
from .library_panel import LibraryPanel

logger = logging.getLogger(__name__)


def default_library() -> list[NodeSpec]:
    """کتابخانه‌ی پیش‌فرضی که هنگام شروع بارگذاری می‌شود (نسخه‌ی نمایشی)."""
    return [
        skycoord_node_spec(),
        reflect(to_galactic, category="astropy.coordinates", display_name="To Galactic"),
        reflect(separation_deg, category="astropy.coordinates", display_name="Separation (deg)"),
    ]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AstroStudio — نمونه‌ی اولیه (MVP)")
        self.resize(1200, 800)

        # ---------- ساخت اجزا ----------
        self.scene = NodeEditorScene()
        self.view = NodeEditorView(self.scene)

        self.library_panel = LibraryPanel()
        self.library_panel.load_specs(default_library())
        self.library_panel.node_double_clicked.connect(self._add_node_from_library)

        self.property_panel = PropertyPanel()
        self.scene.node_selected.connect(self.property_panel.show_node)
        self.property_panel.value_changed.connect(self._refresh_code_preview)
        self.scene.graph_changed.connect(self._refresh_code_preview)
        self.scene.connection_failed.connect(self._show_connection_error)

        self.code_view = QTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setStyleSheet("font-family: monospace; font-size: 11px;")

        self.console_view = QTextEdit()
        self.console_view.setReadOnly(True)
        self.console_view.setStyleSheet("font-family: monospace; font-size: 11px; color: #7CFC00; background: #111;")

        run_button = QPushButton("▶  اجرا (Run)")
        run_button.clicked.connect(self._run_graph)

        # ---------- چیدمان ----------
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(self.library_panel)
        top_splitter.addWidget(self.view)
        top_splitter.addWidget(self.property_panel)
        top_splitter.setSizes([220, 700, 280])

        bottom_tabs = QTabWidget()
        bottom_tabs.addTab(self.code_view, "کد تولیدشده")
        bottom_tabs.addTab(self.console_view, "کنسول خروجی")

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.addWidget(run_button)
        bottom_layout.addWidget(bottom_tabs)

        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_widget)
        main_splitter.setSizes([550, 250])

        self.setCentralWidget(main_splitter)
        self.statusBar().showMessage(
            "بلوکی را از کتابخانه (چپ) دابل‌کلیک کنید تا به بوم اضافه شود. "
            "برای اتصال، از پورت خروجی (سبز) به پورت ورودی (نارنجی) بکشید."
        )

    # ---------- منطق ----------

    def _add_node_from_library(self, spec: NodeSpec):
        # مکان تقریبی وسط ویو فعلی
        center = self.view.mapToScene(self.view.viewport().rect().center())
        self.scene.add_node_from_spec(spec, position=(center.x(), center.y()))

    def _refresh_code_preview(self):
        try:
            code = generate_code(self.scene.graph)
            self.code_view.setPlainText(code)
        except Exception as exc:  # پیش‌نمایش نباید GUI را ببندد
            logger.exception("تولید پیش‌نمایش کد شکست خورد")
            self.code_view.setPlainText(f"# کد قابل تولید نیست:\n# {type(exc).__name__}: {exc}")
            self.statusBar().showMessage(f"تولید کد شکست خورد: {exc}", 8000)

    def _show_connection_error(self, message: str):
        self.statusBar().showMessage(f"اتصال انجام نشد: {message}", 8000)

    def _run_graph(self):
        if not self.scene.graph.nodes:
            QMessageBox.information(self, "اجرا", "هیچ Node ای روی بوم نیست.")
            return
        result = execute_direct(self.scene.graph)
        self.code_view.setPlainText(result.generated_code)
        if result.success:
            lines = ["اجرا با موفقیت انجام شد:\n"]
            for node_id, value in result.results.items():
                node_item = self.scene.node_items.get(node_id)
                label = node_item.node_instance.label if node_item else node_id
                lines.append(f"  {label} -> {value!r}")
            self.console_view.setPlainText("\n".join(lines))
        else:
            lines = [f"خطا در اجرا:\n{result.error}"]
            if result.error_node_id:
                node_item = self.scene.node_items.get(result.error_node_id)
                if node_item is not None:
                    lines.append(f"\nNode مقصر: {node_item.node_instance.label} ({result.error_node_id})")
            if result.results:
                lines.append("\nنتایج جزئی پیش از خطا:")
                for node_id, value in result.results.items():
                    node_item = self.scene.node_items.get(node_id)
                    label = node_item.node_instance.label if node_item else node_id
                    lines.append(f"  {label} -> {value!r}")
            if result.traceback_text:
                lines.append("\nTraceback:\n" + result.traceback_text)
            self.console_view.setPlainText("\n".join(lines))
            self.statusBar().showMessage(f"اجرا شکست خورد: {result.error}", 10000)
