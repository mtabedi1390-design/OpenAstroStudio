"""
gui/main_window.py
---------------------
چیدمان کلی که در طرح اولیه توضیح داده شد:

    Library Panel | Node Editor (Canvas) | Property Panel
    -------------------------------------------------------
                Code Panel + Console + دکمه‌ی Run
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QPushButton, QTabWidget, QMessageBox,
)

from ..engine.node import NodeSpec
from ..engine.codegen import generate_code
from ..engine.executor import execute_direct
from ..engine.overrides import skycoord_node_spec
from ..engine.reflection import reflect
from ..engine.utils import format_exception
from ..libraries.astropy_adapters import to_galactic, separation_deg

from .node_editor import NodeEditorScene, NodeEditorView
from .property_panel import PropertyPanel
from .library_panel import LibraryPanel
from .widgets import make_monospace_view


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

        self.code_view = make_monospace_view()
        self.console_view = make_monospace_view(text_color="#7CFC00", background="#111")

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
        except Exception as exc:  # noqa: BLE001
            self.code_view.setPlainText(f"# کد قابل تولید نیست:\n# {format_exception(exc)}")

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
            self.console_view.setPlainText(f"خطا در اجرا:\n{result.error}")
