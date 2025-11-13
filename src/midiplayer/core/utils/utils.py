
from PySide6.QtCore import (
    Qt
)
from PySide6.QtWidgets import QWidget,QLabel

from qfluentwidgets import (
    InfoBar, InfoBarPosition
)
import sys
from pathlib import Path
from pypinyin import pinyin,Style

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

    @staticmethod
    def truncate_middle(text, max_len=40):
        """超过max_len时，中间显示省略号"""
        if len(text) <= max_len:
            return text
        # 首尾各保留一半长度（预留3个字符给...）
        half = (max_len - 3) // 2
        return f"{text[:half]}...{text[-half:]}"
    
    @staticmethod
    def isWin11():
        return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000
    
    @staticmethod
    def app_path(relative_path):
        """
        获取app的绝对路径，无论是在开发环境还是在 PyInstaller 打包后。
        """
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 打包后的路径
            # sys._MEIPASS 是 PyInstaller 在运行时创建的临时文件夹
            base_path = Path(sys._MEIPASS)
        else:
        # 1. 获取当前脚本（main.py）的绝对路径
            current_script_path = Path(__file__).resolve()  # resolve() 确保是绝对路径
            base_path = current_script_path.parent.parent.parent
        return Path.joinpath(base_path, relative_path)
    
    @staticmethod
    def right_elide_label(label: QLabel) -> None:
        ori_text = label.text()
        wrap_text = label.fontMetrics().elidedText(ori_text,Qt.TextElideMode.ElideRight,label.width())
        label.setText(wrap_text)
        label.setProperty("ori_text",ori_text)

    @staticmethod
    def elide_label_handle_resize(label: QLabel) -> None:
        ori_text = label.property("ori_text")
        wrap_text = label.fontMetrics().elidedText(ori_text,Qt.TextElideMode.ElideRight,label.width())
        label.setText(wrap_text)

    @staticmethod
    # --- 新增：排序键获取方法 ---
    def _get_path_sort_key(path: Path) -> str:
        """
        获取用于排序的键：
        - 中文：返回第一个字的拼音首字母 (小写)
        - 英文/其他：返回文件名的第一个字符 (小写)
        """
        name = path.name
        if not name:
            return ""
        
        first_char = name[0]
        
        # 检查是否为中文字符 (基本范围)
        if '\u4e00' <= first_char <= '\u9fff':
            try:
                # 获取拼音
                pinyin_list = pinyin(first_char, style=Style.FIRST_LETTER)
                if pinyin_list:
                    return pinyin_list[0][0].lower()
                else:
                    return first_char.lower() # 罕见情况回退
            except Exception:
                return first_char.lower() # 异常时回退
        else:
            # 非中文，直接用首字母小写
            return first_char.lower()
        
    @staticmethod
    def sort_path_list_by_name(paths : list[Path]) -> list[Path]:
        return sorted(paths, key=Utils._get_path_sort_key)