import sys
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication
)

from qfluentwidgets import (
    FluentIcon, FluentWindow,NavigationItemPosition
)
from ..component.pages.editor_page import EditorPage
from .pages.present_page import PresentPage
from ..component.pages.music_play_page import MusicPlayPage
from ..component.pages.setting_page import SettingPage
from ..utils.note_key_binding_db_manger import NoteKeyBindingDBManager

# --- 主窗口 ---
class MainWindow(FluentWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("音符按键绑定器")
        self.setWindowIcon(QIcon(FluentIcon.MUSIC.path()))

        self.resize(1000, 800)
        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)     
        
        # 跟踪当前加载的预设
        self.current_preset_name: Optional[str] = None
        
        # 1. 初始化数据库管理器
        self.db = NoteKeyBindingDBManager()

        # 2. 初始化UI页面
        self.editor_page = EditorPage(self.db, self)
        self.present_page = PresentPage(self.db, self)
        self.music_play_page = MusicPlayPage(self.db, self)
        self.setting_page = SettingPage(self)
        self.editor_page.signal_save_preset.connect(self.on_preset_changed)
        self.present_page.signal_load_present.connect(self.on_load_preset)
        self.present_page.signal_change_present.connect(self.on_preset_changed)

        # 3. 添加导航项
        self.addSubInterface(self.editor_page, FluentIcon.EDIT, "按键编辑器")
        self.addSubInterface(self.present_page, FluentIcon.BOOK_SHELF, "按键预设管理")
        self.addSubInterface(self.music_play_page, FluentIcon.MUSIC, "Midi播放")
        self.addSubInterface(self.setting_page, FluentIcon.SETTING, '设置', NavigationItemPosition.BOTTOM)
    
    def on_load_preset(self,name, mappings: Optional[dict]):
        """从预设页面加载预设"""
        if mappings is not None:
            self.editor_page.set_all_mappings(mappings)
            self.editor_page.set_editor_title(name)
            self.switchTo(self.editor_page)

    def on_preset_changed(self, success: bool):
        """处理预设保存后的操作"""
        if success:
            self.present_page.refresh_preset_list()
            self.music_play_page.refresh_preset_list()

    def closeEvent(self, event):
        """处理窗口关闭事件，确保播放器正确关闭"""
        self.music_play_page.stop_player()
        super().closeEvent(event)
