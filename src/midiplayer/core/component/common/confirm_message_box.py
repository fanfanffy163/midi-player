# coding:utf-8

from typing import Callable

from PySide6.QtGui import QColor
from qfluentwidgets import CaptionLabel, LineEdit, MessageBoxBase, SubtitleLabel


class ConfirmInputBox(MessageBoxBase):
    """Custom message box"""

    def __init__(
        self,
        title,
        place_holder,
        parent,
        default_val="",
        validater: Callable = None,
        warning="输入信息有误",
    ):
        super().__init__(parent.window())
        self.title_label = SubtitleLabel(title, self)
        self.message_edit = LineEdit(self)

        self.message_edit.setText(default_val)
        self.message_edit.setPlaceholderText(place_holder)
        self.message_edit.setClearButtonEnabled(True)

        self.warning_label = CaptionLabel(warning)
        self.warning_label.setTextColor("#cf1010", QColor(255, 28, 32))

        # add widget to view layout
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.message_edit)
        self.viewLayout.addWidget(self.warning_label)
        self.warning_label.hide()

        # change the text of button
        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")
        self.validater = validater

        self.widget.setMinimumWidth(350)

        # self.hideYesButton()

    def validate(self):
        """Rewrite the virtual method"""
        if self.validater:
            isValid = self.validater(self.message_edit.text())
            self.warning_label.setHidden(isValid)
            self.message_edit.setError(not isValid)
            return isValid
        return True

    def exec(self):
        ok = super().exec()
        if ok:
            return True, self.message_edit.text().strip()
        else:
            return False, None
