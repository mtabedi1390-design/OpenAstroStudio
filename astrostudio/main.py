"""
main.py
--------
نقطه‌ی ورود برنامه. اجرا:

    python3 -m astrostudio.main
"""

import logging
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from .gui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _install_excepthook() -> None:
    """خطاهای مدیریت‌نشده را لاگ و به کاربر نشان می‌دهد (به‌جای خروج بی‌صدا)."""
    previous_hook = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        logger.critical("خطای مدیریت‌نشده", exc_info=(exc_type, exc_value, exc_tb))
        if QApplication.instance() is not None:
            details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("خطای مدیریت‌نشده")
            box.setText(f"{exc_type.__name__}: {exc_value}")
            box.setDetailedText(details)
            box.exec()
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _install_excepthook()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
