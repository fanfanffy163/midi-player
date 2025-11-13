from typing import Dict, List, Optional, Set

from PySide6.QtCore import (
    Qt, Signal
)
from PySide6.QtGui import QKeyEvent, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QVBoxLayout,
    QHBoxLayout, QFrame
)

from qfluentwidgets import (
    ScrollArea, LineEdit, SwitchButton, PrimaryPushButton, PushButton, ToolButton,
    FluentIcon, SubtitleLabel, CaptionLabel,
    StrongBodyLabel
)
from ..common.confirm_message_box import ConfirmInputBox
from ...utils.note_key_binding_db_manger import NoteKeyBindingDBManager
from ...utils.utils import Utils
from ...utils.style_sheet import StyleSheet
from ...player.type import QT_KEY_MAP, QT_MODIFIER_KEYS

# --- 音符常量 ---
# 用户提供的完整音符列表
ALL_NOTES = [
    "C0","C#0", "D0","D#0", "E0", "F0","F#0", "G0","G#0", "A0", "A#0","B0",
    "C1","C#1", "D1","D#1", "E1", "F1","F#1", "G1","G#1", "A1", "A#1","B1",
    "C2","C#2", "D2","D#2", "E2", "F2","F#2", "G2","G#2", "A2", "A#2","B2",
    "C3","C#3", "D3","D#3", "E3", "F3","F#3", "G3","G#3", "A3", "A#3","B3",
    "C4","C#4", "D4","D#4", "E4", "F4","F#4", "G4","G#4", "A4", "A#4","B4",
    "C5","C#5", "D5","D#5", "E5", "F5","F#5", "G5","G#5", "A5", "A#5","B5",
    "C6","C#6", "D6","D#6", "E6", "F6","F#6", "G6","G#6", "A6", "A#6","B6",
    "C7","C#7", "D7","D#7", "E7", "F7","F#7", "G7","G#7", "A7", "A#7","B7",
    "C8","C#8", "D8","D#8", "E8", "F8","F#8", "G8","G#8", "A8", "A#8","B8", 
]

# 定义哪些音符属于“精简版”
# 这里我们假设 C3 到 B5 是常见的
SIMPLE_NOTES_SET = {
    "C3","C#3", "D3","D#3", "E3", "F3","F#3","G3","G#3", "A3","A#3", "B3",
    "C4","C#4", "D4","D#4", "E4", "F4","F#4","G4","G#4", "A4","A#4", "B4",
    "C5","C#5", "D5","D#5", "E5", "F5","F#5","G5","G#5", "A5","A#5", "B5",    
}


# --- 自定义按键捕捉控件 ---

class KeyCaptureLineEdit(LineEdit):
    """
    一个自定义的LineEdit，用于捕捉按键组合。
    它不使用pynput，而是覆盖Qt的keyPressEvent。
    """

    # 信号：当组合键被设置时发出
    # 传递 (str) 格式化后的组合键字符串
    key_combo_set = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pressed_keys: Set[int] = set()
        self.setPlaceholderText("点击并按下按键组合...")
        self.setReadOnly(True) # 初始只读，靠事件修改
        self.binding_text = ""
        self.binding_keys : List[str] = []

    def mousePressEvent(self, event):
        """点击时获取焦点并清空，准备接收"""
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.pressed_keys.clear()
        self.setText("请按键...")
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """核心：捕捉按键按下事件"""
        if event.isAutoRepeat():
            return
        
        key = event.key()
        self.pressed_keys.add(key)
        
        # 格式化显示
        text = self.format_key_combo()
        self.setText(text)

    def keyReleaseEvent(self, event: QKeyEvent):
        """捕捉按键释放事件"""
        if event.isAutoRepeat():
            return
        
        # 如果所有键都释放了
        self.pressed_keys.discard(event.key())
        if not self.pressed_keys:
            self.finalize_binding()
            
    def focusOutEvent(self, event):
        """失去焦点时，重置状态"""
        self.pressed_keys.clear()
        self.setText(self.binding_text) # 恢复到已保存的值
        if not self.binding_text:
            self.setPlaceholderText("点击并按下按键组合...")
        super().focusOutEvent(event)

    def format_key_combo(self) -> str:
        """格式化按键集合为字符串"""
        modifiers = []
        normal_keys = []
        
        for key in self.pressed_keys:
            if key in QT_MODIFIER_KEYS:
                modifiers.append(QT_MODIFIER_KEYS[key])
            else:
                normal_keys.append(QT_KEY_MAP.get(key, f"Key:{key}"))
        
        # 确保 Ctrl, Shift, Alt, Meta 顺序
        modifiers.sort(key=lambda m: [QT_MODIFIER_KEYS[Qt.Key.Key_Control], QT_MODIFIER_KEYS[Qt.Key.Key_Shift], QT_MODIFIER_KEYS[Qt.Key.Key_Alt], QT_MODIFIER_KEYS[Qt.Key.Key_Meta]].index(m) if m in QT_MODIFIER_KEYS.values() else 99)
        self.binding_keys = modifiers + normal_keys
        return " + ".join(self.binding_keys)

    def finalize_binding(self):
        """锁定组合键，释放焦点，并发出信号"""
        self.binding_text = self.text()
        self.key_combo_set.emit(self.binding_text)
        self.clearFocus() # 释放焦点以"锁定"

    def get_binding(self) -> list[str]:
        return self.binding_keys

    def set_binding(self, text: list[str]):
        """从外部（如加载预设）设置绑定"""
        self.binding_text = (" + ").join(text)
        self.binding_keys = text if isinstance(text, list) else []
        self.setText(self.binding_text)
        if not self.binding_text:
            self.setPlaceholderText("点击并按下按键组合...")

class KeyBindingWidget(QWidget):
    """一个组合控件，包含 音符标签 + 按键捕捉框 + 清除按钮"""
    def __init__(self, note_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.note_name = note_name
        self.is_simple = note_name in SIMPLE_NOTES_SET
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = StrongBodyLabel(note_name, self)
        # 根据标签内容自动设置一个合理的最小宽度
        fm = QFontMetrics(self.label.font())
        width = fm.horizontalAdvance(note_name + "  ") # 增加一点padding
        self.label.setMinimumWidth(width)

        self.key_capture_edit = KeyCaptureLineEdit(self)
        
        self.clear_button = ToolButton(FluentIcon.REMOVE, self)
        self.clear_button.setToolTip("清除此绑定")
        self.clear_button.clicked.connect(self.clear_binding)
        
        layout.addWidget(self.label)
        layout.addWidget(self.key_capture_edit)
        layout.addWidget(self.clear_button)

    def get_note_name(self) -> str:
        return self.note_name

    def get_binding(self) -> list[str]:
        return self.key_capture_edit.get_binding()

    def set_binding(self, text: list[str]):
        self.key_capture_edit.set_binding(text)

    def clear_binding(self):
        self.key_capture_edit.set_binding([])

    def set_simple_mode(self, is_simple_mode: bool):
        """根据是否为精简模式显示或隐藏"""
        self.setVisible(not is_simple_mode or self.is_simple)

# --- UI 页面 ---

class EditorPage(QWidget):
    signal_save_preset = Signal(bool)

    """按键绑定编辑器页面"""
    def __init__(self, db:NoteKeyBindingDBManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("EditorPage")
        self.binding_widgets: List[KeyBindingWidget] = []
        # 1. 初始化后端
        self.db = db
        self.current_preset_name: Optional[str] = None
        
        main_layout = QVBoxLayout(self)

        # style
        StyleSheet.EDITOR_PAGE.apply(self)
        
        # 2. 顶部控制栏
        control_layout = QHBoxLayout()
        self.title_label = SubtitleLabel("按键绑定编辑器", self)
        control_layout.addWidget(self.title_label)
        control_layout.addStretch()
        control_layout.addWidget(CaptionLabel("精简模式"))
        self.simple_mode_switch = SwitchButton(self)
        self.simple_mode_switch.setChecked(True) # 默认开启
        self.simple_mode_switch.checkedChanged.connect(self.toggle_view_mode)
        control_layout.addWidget(self.simple_mode_switch)
        
        main_layout.addLayout(control_layout)

        # 3. 滚动区域
        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        self.form_layout = QFormLayout(scroll_content) # 使用QFormLayout实现标签和控件对齐
        self.form_layout.setContentsMargins(10, 10, 10, 10)
        self.form_layout.setHorizontalSpacing(20)
        self.form_layout.setVerticalSpacing(10)
        
        # 4. 创建所有按键绑定控件
        for note in ALL_NOTES:
            binding_widget = KeyBindingWidget(note)
            self.binding_widgets.append(binding_widget)
            # QFormLayout.addRow(QLabel, QWidget)
            # 我们将自定义控件的标签用作 QFormLayout 的标签，控件本身用作 QWidget
            # 为了美观，我们复用 binding_widget 里的 label
            self.form_layout.addRow(binding_widget.label, binding_widget)
        
        self.scroll_area.setWidget(scroll_content)
        scroll_content.setObjectName("ScrollContent")
        main_layout.addWidget(self.scroll_area)
        
        # 5.创建按钮
        main_layout.addSpacing(10)

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reset_button = PushButton(FluentIcon.CLOSE, "重置所有绑定", self)
        self.save_current_button = PrimaryPushButton(FluentIcon.SAVE, "保存当前预设", self)
        button_layout.addWidget(self.reset_button)
        button_layout.addSpacing(20)
        button_layout.addWidget(self.save_current_button)     
        main_layout.addLayout(button_layout)
        
        self.save_current_button.clicked.connect(self.on_save_current_preset)
        self.reset_button.clicked.connect(self.on_reset_editor)

        # 初始加载时应用一次精简模式
        self.toggle_view_mode(True)
        self.set_editor_title(None)

    def toggle_view_mode(self, is_simple_mode: bool):
        """切换精简/完全视图"""
        for i in range(self.form_layout.rowCount()):
            label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            widget_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            
            if label_item and widget_item:
                label_widget = label_item.widget()
                binding_widget = widget_item.widget()
                
                # binding_widget 是我们的 KeyBindingWidget
                if isinstance(binding_widget, KeyBindingWidget):
                    is_visible = not is_simple_mode or binding_widget.is_simple
                    binding_widget.setVisible(is_visible)
                    label_widget.setVisible(is_visible) # 同时隐藏/显示 QFormLayout 的标签

    def get_all_mappings(self) -> Dict[str, str]:
        """获取当前编辑器的所有映射"""
        mappings = {}
        for widget in self.binding_widgets:
            binding = widget.get_binding()
            if binding: # 只保存有绑定的
                mappings[widget.get_note_name()] = binding
        return mappings

    def set_all_mappings(self, mappings: Dict[str, list[str]]):
        """从字典加载映射到编辑器"""
        for widget in self.binding_widgets:
            note_name = widget.get_note_name()
            binding = mappings.get(note_name, "") # 找不到则设置为空
            widget.set_binding(binding)

    def clear_all_mappings(self):
        """清空所有绑定"""
        for widget in self.binding_widgets:
            widget.clear_binding()

    # --- 槽函数 (Slot Functions) ---

    def on_save_current_preset(self):
        """点击"保存当前预设"按钮"""
        # 询问一个新名称，或使用当前名称
        default_name = self.current_preset_name if self.current_preset_name else ""
        
        title = "保存预设"
        label = "请输入预设名称:"
        ok, text = ConfirmInputBox(title, label, self,default_name, lambda s: len(s.strip()) > 0, "名称不能为空。").exec()
        
        if ok:
            mappings = self.get_all_mappings()
            if self.db.save_preset(text, mappings):
                Utils.show_success_infobar(self,"保存成功", f"预设 '{text}' 已保存。")
                self.set_editor_title(text)
                self.signal_save_preset.emit(True)
            else:
                Utils.show_error_infobar(self,"保存失败", "无法保存到数据库。")

    def on_reset_editor(self):
        """重置编辑器页面"""
        self.clear_all_mappings()

    def set_editor_title(self, name: Optional[str]):
        """更新编辑器页面的标题"""
        if name:
            self.current_preset_name = name
            title = f"按键绑定编辑器 (当前: {name})"
        else:
            self.current_preset_name = None
            title = "按键绑定编辑器 (未保存)"
            
        self.title_label.setText(title)
