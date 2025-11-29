from PySide6.QtCore import Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import CheckBox, StrongBodyLabel


class TrackContentView(QWidget):
    """音轨选择的具体内容组件"""

    signal_track_state_changed = Signal(int, bool)

    def __init__(self, track_info_list: list, active_tracks: list, parent=None):
        super().__init__(parent)

        # 布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)  # 设置合适的边距
        self.main_layout.setSpacing(12)

        # --- 1. 手动添加标题 ---
        self.title_label = StrongBodyLabel("选择音轨", self)
        self.main_layout.addWidget(self.title_label)

        # 滚动区域容器
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)

        # 动态生成复选框
        self.checkboxes = []
        for i, info in enumerate(track_info_list):
            track_name = info.get("name", f"Track {i}")
            if not track_name or not track_name.strip():
                track_name = f"Track {i}"

            cb = CheckBox(track_name)

            is_checked = True
            if active_tracks is not None:
                is_checked = i in active_tracks
            cb.setChecked(is_checked)

            cb.stateChanged.connect(
                lambda state, idx=i, checkbox=cb: self._on_state_changed(idx, checkbox)
            )

            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)

        # 滚动区域配置
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea{border: none; background: transparent;}"
        )

        self.scroll_area.setMaximumHeight(300)
        self.setMinimumWidth(250)  # 稍微宽一点

        self.main_layout.addWidget(self.scroll_area)

    def _on_state_changed(self, index, checkbox):
        self.signal_track_state_changed.emit(index, checkbox.isChecked())
