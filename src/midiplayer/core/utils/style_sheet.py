import os
from enum import Enum

from qfluentwidgets import StyleSheetBase, Theme, qconfig

from midiplayer.core.utils.utils import Utils


class StyleSheet(StyleSheetBase, Enum):
    """Style sheet"""

    EDITOR_PAGE = "editor_page"
    SETTING_PAGE = "setting_page"
    MUSIC_PLAY_PAGE = "music_play_page"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        path = os.path.join(
            str(Utils.resource_path("resources")),
            "qss",
            theme.value.lower(),
            f"{self.value}.qss",
        )
        return path
