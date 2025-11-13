from typing import Optional

from PySide6.QtCore import (
    Signal
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout,
    QListWidgetItem
)

from qfluentwidgets import (
    SearchLineEdit, ListWidget
)
from ...utils.note_key_binding_db_manger import NoteKeyBindingDBManager


class PresentList(QWidget):
    signal_item_selected = Signal(object)

    def __init__(self,db: NoteKeyBindingDBManager, parent=None):
        super().__init__(parent)
        self.db = db

        # 左侧：列表和搜索
        self.main_layout = QVBoxLayout(self)
        self.search_edit = SearchLineEdit(self)
        self.search_edit.setPlaceholderText("搜索预设...")
        self.search_edit.textChanged.connect(self.refresh_preset_list)
        
        self.preset_list_widget = ListWidget(self)
        
        self.main_layout.addWidget(self.search_edit)
        self.main_layout.addWidget(self.preset_list_widget)

        self.preset_list_widget.currentItemChanged.connect(self._on_selection_changed)
        self._on_selection_changed(None) # 初始禁用按钮
        self.refresh_preset_list()

    def _on_selection_changed(self, current_item: Optional[QListWidgetItem]):
        self.signal_item_selected.emit(current_item)
    
    def get_selected_preset_name(self) -> Optional[str]:
        """获取当前选中的预设名称"""
        item = self.preset_list_widget.currentItem()
        return item.text() if item else None
    
    def refresh_preset_list(self):
        """刷新预设列表"""
        current_selection = self.get_selected_preset_name()
        
        self.preset_list_widget.clear()
        search_query = self.search_edit.text()
        presets = self.db.list_presets(search_query)
        
        new_item_to_select = None
        for name in presets:
            item = QListWidgetItem(name)
            self.preset_list_widget.addItem(item)
            if name == current_selection:
                new_item_to_select = item
        
        if new_item_to_select:
            self.preset_list_widget.setCurrentItem(new_item_to_select)