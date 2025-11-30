from typing import Optional

from loguru import logger
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    IndeterminateProgressRing,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SubtitleLabel,
    SwitchButton,
)

from midiplayer.core.component.common.confirm_message_box import ConfirmInputBox
from midiplayer.core.component.common.key_binding_widget import KeyBindingWidget
from midiplayer.core.component.common.qlazy_widget import QLazyWidget
from midiplayer.core.utils.db_manager import DBManager
from midiplayer.core.utils.style_sheet import StyleSheet
from midiplayer.core.utils.utils import Utils

# --- 音符常量 ---
# 用户提供的完整音符列表
ALL_NOTES = [
    "C0",
    "C#0",
    "D0",
    "D#0",
    "E0",
    "F0",
    "F#0",
    "G0",
    "G#0",
    "A0",
    "A#0",
    "B0",
    "C1",
    "C#1",
    "D1",
    "D#1",
    "E1",
    "F1",
    "F#1",
    "G1",
    "G#1",
    "A1",
    "A#1",
    "B1",
    "C2",
    "C#2",
    "D2",
    "D#2",
    "E2",
    "F2",
    "F#2",
    "G2",
    "G#2",
    "A2",
    "A#2",
    "B2",
    "C3",
    "C#3",
    "D3",
    "D#3",
    "E3",
    "F3",
    "F#3",
    "G3",
    "G#3",
    "A3",
    "A#3",
    "B3",
    "C4",
    "C#4",
    "D4",
    "D#4",
    "E4",
    "F4",
    "F#4",
    "G4",
    "G#4",
    "A4",
    "A#4",
    "B4",
    "C5",
    "C#5",
    "D5",
    "D#5",
    "E5",
    "F5",
    "F#5",
    "G5",
    "G#5",
    "A5",
    "A#5",
    "B5",
    "C6",
    "C#6",
    "D6",
    "D#6",
    "E6",
    "F6",
    "F#6",
    "G6",
    "G#6",
    "A6",
    "A#6",
    "B6",
    "C7",
    "C#7",
    "D7",
    "D#7",
    "E7",
    "F7",
    "F#7",
    "G7",
    "G#7",
    "A7",
    "A#7",
    "B7",
    "C8",
    "C#8",
    "D8",
    "D#8",
    "E8",
    "F8",
    "F#8",
    "G8",
    "G#8",
    "A8",
    "A#8",
    "B8",
]

# 定义哪些音符属于“精简版”
# 这里我们假设 C3 到 B5 是常见的
SIMPLE_NOTES_SET = {
    "C3",
    "C#3",
    "D3",
    "D#3",
    "E3",
    "F3",
    "F#3",
    "G3",
    "G#3",
    "A3",
    "A#3",
    "B3",
    "C4",
    "C#4",
    "D4",
    "D#4",
    "E4",
    "F4",
    "F#4",
    "G4",
    "G#4",
    "A4",
    "A#4",
    "B4",
    "C5",
    "C#5",
    "D5",
    "D#5",
    "E5",
    "F5",
    "F#5",
    "G5",
    "G#5",
    "A5",
    "A#5",
    "B5",
}

# --- UI 页面 ---


class EditorPage(QLazyWidget):
    signal_save_preset = Signal(bool)

    """按键绑定编辑器页面"""

    def __init__(self, db: DBManager, parent: Optional[QWidget] = None):
        super().__init__(parent, "正在初始化编辑器...")
        self.setObjectName("EditorPage")
        self.db = db
        self.current_preset_name: Optional[str] = None

        self._pending_mappings = None  # 暂存外部传入的数据
        self.binding_widgets: list[KeyBindingWidget] = []

    def _init_ui(self, ui_content: QWidget):
        """真正的 UI 初始化逻辑"""
        # --- 以下是原本 __init__ 中的逻辑 ---

        # 1. layout
        self.main_layout = QVBoxLayout(ui_content)
        # 2. 顶部控制栏
        control_layout = QHBoxLayout()
        self.title_label = SubtitleLabel("按键绑定编辑器", self)
        control_layout.addWidget(self.title_label)
        control_layout.addStretch()
        control_layout.addWidget(CaptionLabel("精简模式"))
        self.simple_mode_switch = SwitchButton(self)
        self.simple_mode_switch.setChecked(True)
        self.simple_mode_switch.checkedChanged.connect(self.toggle_view_mode)
        control_layout.addWidget(self.simple_mode_switch)

        self.main_layout.addLayout(control_layout)

        # 3. 滚动区域
        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        self.form_layout = QFormLayout(scroll_content)
        self.form_layout.setContentsMargins(10, 10, 10, 10)
        self.form_layout.setHorizontalSpacing(20)
        self.form_layout.setVerticalSpacing(10)

        # 4. 创建所有按键绑定控件
        for note in ALL_NOTES:
            binding_widget = KeyBindingWidget(note)
            self.binding_widgets.append(binding_widget)
            self.form_layout.addRow(binding_widget.label, binding_widget)

        self.scroll_area.setWidget(scroll_content)
        scroll_content.setObjectName("ScrollContent")
        self.main_layout.addWidget(self.scroll_area)

        # 5.创建按钮
        self.main_layout.addSpacing(10)
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reset_button = PushButton(FluentIcon.CLOSE, "重置所有绑定", self)
        self.save_current_button = PrimaryPushButton(
            FluentIcon.SAVE, "保存当前预设", self
        )
        button_layout.addWidget(self.reset_button)
        button_layout.addSpacing(20)
        button_layout.addWidget(self.save_current_button)
        self.main_layout.addLayout(button_layout)

        self.save_current_button.clicked.connect(self.on_save_current_preset)
        self.reset_button.clicked.connect(self.on_reset_editor)

        # 初始设置
        self.toggle_view_mode(True)
        self.set_editor_title(self.current_preset_name)

        # 检查是否有挂起的数据需要加载
        if self._pending_mappings:
            self.set_all_mappings(self._pending_mappings)
            self._pending_mappings = None

        StyleSheet.EDITOR_PAGE.apply(self)
        logger.info("EditorPage UI loaded")

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
                    is_visible = (
                        not is_simple_mode
                        or binding_widget.get_name() in SIMPLE_NOTES_SET
                    )
                    binding_widget.setVisible(is_visible)
                    label_widget.setVisible(
                        is_visible
                    )  # 同时隐藏/显示 QFormLayout 的标签

    def get_all_mappings(self) -> dict[str, str]:
        """获取当前编辑器的所有映射"""
        mappings = {}
        for widget in self.binding_widgets:
            binding = widget.get_binding()
            if binding:  # 只保存有绑定的
                mappings[widget.get_name()] = binding
        return mappings

    def set_all_mappings(self, mappings: dict[str, list[str]]):
        """从字典加载映射到编辑器"""
        if not self.lazy_loaded or not self.binding_widgets:
            self._pending_mappings = mappings
            return

        for widget in self.binding_widgets:
            note_name = widget.get_name()
            binding = mappings.get(note_name, "")
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
        ok, text = ConfirmInputBox(
            title,
            label,
            self,
            default_name,
            lambda s: len(s.strip()) > 0,
            "名称不能为空。",
        ).exec()

        if ok:
            mappings = self.get_all_mappings()
            if self.db.save_preset(text, mappings):
                Utils.show_success_infobar(self, "保存成功", f"预设 '{text}' 已保存。")
                self.set_editor_title(text)
                self.signal_save_preset.emit(True)
            else:
                Utils.show_error_infobar(self, "保存失败", "无法保存到数据库。")

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
