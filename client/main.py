import os
import sys
from pathlib import Path


def _ensure_qt_plugins() -> None:
    """Указывает Qt путь к плагинам (Windows: иначе часто «Could not find platform plugin windows»)."""
    try:
        import PyQt5

        base = Path(PyQt5.__file__).resolve().parent
        candidates = [
            base / "Qt5" / "plugins",
            base / "Qt" / "plugins",
        ]
        plugins = next((p for p in candidates if p.is_dir()), None)
        if not plugins:
            return
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
        platforms = plugins / "platforms"
        if platforms.is_dir():
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms))
    except Exception:
        pass


_ensure_qt_plugins()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile, QTextStream

from ui.main_window import MainWindow


def load_stylesheet() -> str:
    qss_path = os.path.join(os.path.dirname(__file__), "resources", "styles.qss")
    qss_file = QFile(qss_path)
    if qss_file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(qss_file)
        stylesheet = stream.readAll()
        qss_file.close()
        return stylesheet
    return ""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
