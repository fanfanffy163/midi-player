from midiplayer.core.component.main_window import MainWindow
from PySide6.QtWidgets import QApplication
import sys

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())