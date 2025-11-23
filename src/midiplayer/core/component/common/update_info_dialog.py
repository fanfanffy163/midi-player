from qfluentwidgets import (SubtitleLabel, ProgressBar, MessageBoxBase)

class UpdateProgressDialog(MessageBoxBase):
    """自定义下载进度弹窗"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("正在下载更新", self)
        self.progressBar = ProgressBar(self)
        self.statusLabel = SubtitleLabel("准备中...", self)
        
        # 布局设置
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.statusLabel)
        self.viewLayout.addWidget(self.progressBar)
        
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        
        # 隐藏 确定/取消 按钮，强制用户等待下载完成或出错
        self.yesButton.hide()
        self.cancelButton.setText("取消") # 仅保留取消按钮逻辑
        
        self.widget.setMinimumWidth(350)

    def set_progress(self, val):
        self.progressBar.setValue(val)
        self.statusLabel.setText(f"已下载 {val}%")