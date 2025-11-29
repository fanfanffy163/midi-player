import json
from copy import deepcopy
from enum import Enum

# coding:utf-8
from typing import Union

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel
from qfluentwidgets import (
    ConfigItem,
    ConfigSerializer,
    ExpandSettingCard,
    FluentIconBase,
    qconfig,
)

from midiplayer.core.component.common.key_binding_widget import KeyBindingWidget


class CmdKeys(Enum):
    TriggerPlay = "切换播放"
    StartPlay = "开始播放"
    PausePlay = "暂停播放"
    PlayNext = "下一首"
    PlayPre = "上一首"


class JsonSerializer(ConfigSerializer):
    """enumeration class serializer"""

    def serialize(self, value):
        return json.dumps(value, ensure_ascii=False)

    def deserialize(self, value):
        return json.loads(value)


class CmdBindingSettingCard(ExpandSettingCard):
    def __init__(
        self,
        configItem: ConfigItem,
        icon: Union[str, QIcon, FluentIconBase],
        title,
        content=None,
        parent=None,
    ):
        """
        Parameters
        ----------
        configItem: OptionsConfigItem
            options config item

        icon: str | QIcon | FluentIconBase
            the icon to be drawn

        title: str
            the title of setting card

        content: str
            the content of setting card

        texts: List[str]
            the texts of radio buttons

        parent: QWidget
            parent window
        """
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        self.configName = configItem.name
        self.choiceLabel = QLabel(self)

        self.choiceLabel.setObjectName("titleLabel")
        self.addWidget(self.choiceLabel)

        # create buttons
        self.viewLayout.setSpacing(19)
        self.viewLayout.setContentsMargins(48, 18, 0, 18)

        value = qconfig.get(self.configItem)
        for member in CmdKeys:
            val = member.value
            name = member.name
            binding_widget = KeyBindingWidget(val, self, 1)
            v = value[name] if name in value else None
            binding_widget.set_binding([v] if v else [])
            self.viewLayout.addWidget(binding_widget)
            binding_widget.signal_keys_change.connect(self.__onKeysSet)

        self._adjustViewSize()

    def __onKeysSet(self, val, keys: list[str]):
        """button clicked slot"""
        value = deepcopy(qconfig.get(self.configItem))
        member = CmdKeys(val)
        value[member.name] = keys[0] if len(keys) > 0 else None
        if value[member.name] is None:
            value.pop(member.name, None)
        qconfig.set(self.configItem, value)
