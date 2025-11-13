import json
from typing import Optional

from PySide6.QtCore import (
    Signal
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout,
    QHBoxLayout, QFileDialog, QListWidgetItem
)

from qfluentwidgets import (
    PrimaryPushButton, PushButton, FluentIcon, MessageBox
)
from ..common.confirm_message_box import ConfirmInputBox
from ...utils.note_key_binding_db_manger import NoteKeyBindingDBManager
from ...utils.utils import Utils
from ..common.present_list import PresentList

class PresentPage(QWidget):
    signal_load_present = Signal(str,dict)
    signal_change_present = Signal(bool)

    """预设管理页面"""
    def __init__(self, db: NoteKeyBindingDBManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("PresetPage")
        self.db = db
        
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)

        # 左侧：列表和搜索
        left_layout = QVBoxLayout()
        self.present_list_widget = PresentList(self.db, self)
        left_layout.addWidget(self.present_list_widget)

        # 右侧：操作按钮
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        
        self.load_button = PrimaryPushButton(FluentIcon.FOLDER, "加载选定预设", self)
        self.delete_button = PushButton(FluentIcon.DELETE, "删除选定预设", self)
        self.duplicate_button = PushButton(FluentIcon.COPY, "复制选定预设", self)
        self.import_button = PushButton(FluentIcon.DOWNLOAD, "导入 (JSON)...", self)
        self.export_button = PushButton(FluentIcon.RETURN, "导出 (JSON)...", self)
        
        right_layout.addWidget(self.load_button)
        right_layout.addWidget(self.delete_button)
        right_layout.addWidget(self.duplicate_button)
        right_layout.addStretch()
        right_layout.addWidget(self.import_button)
        right_layout.addWidget(self.export_button)
        right_layout.addStretch()

        main_layout.addLayout(left_layout, 2) # 左侧占2份
        main_layout.addLayout(right_layout, 1) # 右侧占1份
        
        # 信号连接
        self.present_list_widget.signal_item_selected.connect(self.on_selection_changed)
        self.connect_signals()

    def on_selection_changed(self, current_item: Optional[QListWidgetItem]):
        """当列表选择变化时，更新按钮状态"""
        is_selected = current_item is not None
        self.load_button.setEnabled(is_selected)
        self.delete_button.setEnabled(is_selected)
        self.duplicate_button.setEnabled(is_selected)
        self.export_button.setEnabled(is_selected)
    
    def connect_signals(self):
        self.load_button.clicked.connect(self.on_load_selected_preset)
        self.delete_button.clicked.connect(self.on_delete_selected_preset)
        self.duplicate_button.clicked.connect(self.on_duplicate_selected_preset)
        self.import_button.clicked.connect(self.on_import_preset)
        self.export_button.clicked.connect(self.on_export_selected_preset)

    def refresh_preset_list(self):
        """刷新预设列表"""
        self.present_list_widget.refresh_preset_list()

    def on_load_selected_preset(self):
        """点击"加载选定预设"按钮"""
        name = self.present_list_widget.get_selected_preset_name()
        if not name:
            Utils.show_warning_infobar(self,"未选择", "请先在列表中选择一个预设。")
            return
       
        mappings = self.db.load_preset(name)
        if mappings is not None:
            self.signal_load_present.emit(name,mappings)
            Utils.show_success_infobar(self,"加载成功", f"已加载预设 '{name}'。")
        else:
            Utils.show_error_infobar(self,"加载失败", f"无法从数据库中找到 '{name}'。")

    def on_delete_selected_preset(self):
        """点击"删除选定预设"按钮"""
        name = self.present_list_widget.get_selected_preset_name()
        if not name:
            Utils.show_warning_infobar(self,"未选择", "请先选择一个预设。")
            return

        # 确认对话框
        title = "确认删除"
        content = f"您确定要永久删除预设 '{name}' 吗？此操作无法撤销。"
        w = MessageBox(title, content, self.window())
        
        if w.exec(): # 'Yes'
            if self.db.delete_preset(name):
                Utils.show_success_infobar(self,"删除成功", f"预设 '{name}' 已被删除。")
                self.signal_change_present.emit(True)
            else:
                Utils.show_error_infobar(self,"删除失败", f"无法从数据库中删除 '{name}'。")

    def on_duplicate_selected_preset(self):
        """点击"复制选定预设"按钮"""
        old_name = self.present_list_widget.get_selected_preset_name()
        if not old_name:
            Utils.show_warning_infobar(self,"未选择", "请先选择一个预设。")
            return
            
        ok, new_name = ConfirmInputBox("复制预设", "请输入新预设的名称:", self,f"{old_name} - 副本",lambda s: len(s.strip()) > 0, "名称不能为空。").exec()
        
        if ok and new_name:
            if new_name == old_name:
                Utils.show_error_infobar(self,"名称无效", "新名称不能与旧名称相同。")
                return
            
            if self.db.load_preset(new_name) is not None:
                Utils.show_error_infobar(self,"名称已存在", f"名为 '{new_name}' 的预设已存在。")
                return

            if self.db.duplicate_preset(old_name, new_name):
                Utils.show_success_infobar(self,"复制成功", f"已创建副本 '{new_name}'。")
                self.signal_change_present.emit(True)
            else:
                Utils.show_error_infobar(self,"复制失败", "复制操作失败。")
        elif ok and not new_name:
            Utils.show_error_infobar(self,"名称无效", "预设名称不能为空。")

    def on_import_preset(self):
        """点击"导入 (JSON)"按钮"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入预设", "", "JSON 文件 (*.json)"
        )
        
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 假设 JSON 格式为 {"name": "...", "mappings": {...}}
            if "name" not in data or "mappings" not in data:
                raise ValueError("JSON格式无效，缺少 'name' 或 'mappings' 键。")

            preset_name = data["name"]
            mappings = data["mappings"]
            
            # 检查名称是否冲突
            if self.db.load_preset(preset_name) is not None:
                title = "名称冲突"
                content = f"名为 '{preset_name}' 的预设已存在。要覆盖它吗？"
                w = MessageBox(title, content, self.window())
                if not w.exec(): # 'No'
                    Utils.show_warning_infobar(self,"导入取消", "操作已取消。")
                    return

            # 保存到数据库
            if self.db.save_preset(preset_name, mappings):
                Utils.show_success_infobar(self,"导入成功", f"已成功导入 '{preset_name}'。")
                self.signal_change_present.emit(True)
            else:
                Utils.show_error_infobar(self,"导入失败", "保存到数据库时出错。")

        except Exception as e:
            Utils.show_error_infobar(self,"导入错误", f"无法解析JSON文件: {e}")

    def on_export_selected_preset(self):
        """点击"导出 (JSON)"按钮"""
        name = self.present_list_widget.get_selected_preset_name()
        if not name:
            Utils.show_warning_infobar(self,"未选择", "请先选择一个预设。")
            return
            
        mappings = self.db.load_preset(name)
        if mappings is None:
            Utils.show_error_infobar(self,"加载失败", "无法从数据库加载该预设。")
            return

        # 准备导出的数据
        export_data = {
            "name": name,
            "mappings": mappings
        }
        
        # 建议的文件名
        safe_name = name.replace(r'[\/:*?"<>|]', '_') # 移除文件名非法字符
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出预设", f"{safe_name}.json", "JSON 文件 (*.json)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            Utils.show_success_infobar(self,"导出成功", f"已导出预设到 {file_path}")
        except Exception as e:
            Utils.show_error_infobar(self,"导出失败", f"写入文件时出错: {e}")
