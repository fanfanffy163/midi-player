from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import CheckBox, SimpleCardWidget, SmoothScrollArea, StrongBodyLabel


# 1. 改为继承 SimpleCardWidget，自带卡片背景和边框
class TrackContentView(SimpleCardWidget):
    """音轨选择的具体内容组件"""

    signal_track_state_changed = Signal(int, bool)

    def __init__(self, track_info_list: list, active_tracks: list, parent=None):
        super().__init__(parent)
        self.setObjectName("TrackContentView")

        # 布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            0, 0, 0, 0
        )  # 卡片内部贴边，由头部和内容控制间距
        self.main_layout.setSpacing(0)

        # --- 1. 优化的标题区域 ---
        # 创建一个头部容器，用于放标题和底部分割线
        self.header_widget = QWidget()
        self.header_widget.setObjectName("headerWidget")
        self.header_layout = QVBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(16, 12, 16, 12)  # 标题的内边距
        self.header_layout.setSpacing(0)

        self.title_label = StrongBodyLabel("选择音轨", self)
        self.header_layout.addWidget(self.title_label)

        self.main_layout.addWidget(self.header_widget)

        # 添加一条分割线，区分标题和列表
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)
        self.main_layout.addWidget(self.separator)

        # --- 2. 滚动内容区域 ---
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(16, 8, 16, 16)  # 列表内容的内边距
        self.content_layout.setSpacing(8)

        # 滚动区域容器
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(4)  # 选项稍微紧凑一点

        # 动态生成复选框
        self.checkboxes = []
        for i, info in enumerate(track_info_list):
            track_name = info.get("name", f"Track {i}")
            if not track_name or not track_name.strip():
                track_name = f"Track {i}"

            note_num = info.get("num", None)
            note_info = f"({note_num})" if note_num is not None else ""
            info_text = f"{track_name}{note_info}"
            cb = CheckBox(info_text)

            is_checked = True
            if active_tracks is not None:
                is_checked = i in active_tracks
            cb.setChecked(is_checked)

            cb.stateChanged.connect(
                lambda state, idx=i, checkbox=cb: self._on_state_changed(idx, checkbox)
            )

            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)

        # 底部加一个弹簧，把选项顶上去
        self.scroll_layout.addStretch(1)

        # 滚动区域配置
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(300)
        self.scroll_area.enableTransparentBackground()

        self.content_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(self.content_container)

        self.setMinimumWidth(280)

    def _on_state_changed(self, index, checkbox):
        self.signal_track_state_changed.emit(index, checkbox.isChecked())
