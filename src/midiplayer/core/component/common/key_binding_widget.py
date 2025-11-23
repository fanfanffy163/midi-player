from typing import List, Optional, Set

from PySide6.QtCore import (
    Qt, Signal
)
from PySide6.QtGui import QKeyEvent, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout
)

from qfluentwidgets import (
    LineEdit, ToolButton,
    FluentIcon, BodyLabel
)
from ...player.type import QT_KEY_MAP, QT_MODIFIER_KEYS

# --- 自定义按键捕捉控件 ---

class KeyCaptureLineEdit(LineEdit):
    """
    一个自定义的LineEdit，用于捕捉按键组合。
    它不使用pynput，而是覆盖Qt的keyPressEvent。
    """

    # 信号：当组合键被设置时发出
    # 传递 (str) 格式化后的组合键字符串
    key_combo_set = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None, max_key_count = None):
        super().__init__(parent)
        self.pressed_keys: Set[int] = set()
        self.max_key_count = max_key_count
        self.show_placeholder_text()
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
        if self.max_key_count is not None and len(self.pressed_keys) > self.max_key_count - 1:
            return
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
            self.show_placeholder_text()
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
        self.key_combo_set.emit(self.binding_keys)
        self.clearFocus() # 释放焦点以"锁定"

    def get_binding(self) -> list[str]:
        return self.binding_keys

    def set_binding(self, text: list[str]):
        """从外部（如加载预设）设置绑定"""
        self.binding_text = (" + ").join(text)
        self.binding_keys = text if isinstance(text, list) else []
        self.setText(self.binding_text)
        if not self.binding_text:
            self.show_placeholder_text()

    def show_placeholder_text(self):
        if self.max_key_count is None:
            self.setPlaceholderText("点击并按下按键组合...")
        else:
            self.setPlaceholderText(f"点击并按下按键组合,最多支持{self.max_key_count}个按键")

class KeyBindingWidget(QWidget):
    signal_keys_change = Signal(str,list)
    """一个组合控件，包含 标签名称 + 按键捕捉框 + 清除按钮"""
    def __init__(self, name: str, parent: Optional[QWidget] = None, max_key_count = None):
        super().__init__(parent)
        self.name = name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = BodyLabel(name, self)
        # 根据标签内容自动设置一个合理的最小宽度
        fm = QFontMetrics(self.label.font())
        width = fm.horizontalAdvance(name + "  ") # 增加一点padding
        self.label.setMinimumWidth(width)

        self.key_capture_edit = KeyCaptureLineEdit(self, max_key_count)
        self.key_capture_edit.key_combo_set.connect(self._on_keys_change)
        
        self.clear_button = ToolButton(FluentIcon.REMOVE, self)
        self.clear_button.setToolTip("清除此绑定")
        self.clear_button.clicked.connect(self.clear_binding)
        
        layout.addWidget(self.label)
        layout.addWidget(self.key_capture_edit)
        layout.addWidget(self.clear_button)

    def get_name(self) -> str:
        return self.name

    def get_binding(self) -> list[str]:
        return self.key_capture_edit.get_binding()

    def set_binding(self, text: list[str]):
        self.key_capture_edit.set_binding(text)

    def clear_binding(self):
        self.key_capture_edit.set_binding([])
        self._on_keys_change([])

    def _on_keys_change(self, keys: list[str]):
        self.signal_keys_change.emit(self.name,keys)