
from PyQt6.QtCore import (
    Qt
)
from PyQt6.QtWidgets import QWidget

from qfluentwidgets import (
    InfoBar, InfoBarPosition
)

class Utils:
    # --- 信息栏辅助函数 ---
    @staticmethod
    def show_success_infobar(self : QWidget, title: str, content: str,duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.success(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,    # vertical layout
            duration=duration,
            parent=parent
        ).show()

    @staticmethod
    def show_error_infobar(self : QWidget, title: str, content: str,duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.error(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,    # vertical layout
            duration=duration,
            parent=parent
        ).show()

    @staticmethod
    def show_warning_infobar(self : QWidget, title: str, content: str,duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.warning(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,    # vertical layout
            duration=duration,
            parent=parent
        ).show()