import sys
import os

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
