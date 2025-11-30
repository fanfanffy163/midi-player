from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QStackedLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, IndeterminateProgressRing


class QLazyWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None, loading_info="正在加载..."):
        super().__init__(parent)
        self.lazy_loaded = False

        # 1. 根布局
        self.root_layout = QStackedLayout(self)

        # 2. 创建一个临时容器放 Loading 动画
        self.loading_container = QWidget()
        self._setup_loading_ui(loading_info)

        # 3. 加到堆叠布局第 0 页
        self.root_layout.addWidget(self.loading_container)

    def _setup_loading_ui(self, info):
        """构建 Loading 界面"""
        layout = QVBoxLayout(self.loading_container)
        self.lazy_ring = IndeterminateProgressRing(self.loading_container)
        self.lazy_label = CaptionLabel(info, self.loading_container)
        self.lazy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(self.lazy_ring, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lazy_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.lazy_loaded:
            self.lazy_loaded = True
            QTimer.singleShot(50, self._init_real_ui)

    def _init_real_ui(self):
        ui_content = QWidget()
        self.finish_loading(ui_content)
        self._init_ui(ui_content)

    def _init_ui(self, ui_content: QWidget):
        """
        子类必须重写此方法
        """
        pass

    def finish_loading(self, ui_content: QWidget):
        """
        :param ui_content: 包含真实界面的容器
        """
        # 1. 把做好的真实界面加到第 1 页
        self.root_layout.addWidget(ui_content)

        # 2. 切换显示
        self.root_layout.setCurrentWidget(ui_content)

        # 3. 销毁 Loading 页面释放内存
        self.loading_container.deleteLater()
