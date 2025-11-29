from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from midiplayer.core.component.common.midi_cards import MidiCards
from midiplayer.core.component.common.music_player_bar import MusicPlayerBar
from midiplayer.core.component.common.present_list import PresentList
from midiplayer.core.utils.note_key_binding_db_manger import DBManager
from midiplayer.core.utils.style_sheet import StyleSheet
from midiplayer.core.utils.utils import Utils


class MusicPlayPage(QWidget):
    """预设管理页面"""

    def __init__(self, db: DBManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MusicPlayPage")
        self.db = db

        # 播放需要使用的参数
        self.note_to_key_mappings: dict[str, str] = None
        self.present_name: str | None = None

        # style
        StyleSheet.MUSIC_PLAY_PAGE.apply(self)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.top_layout = QHBoxLayout()
        self.present_list_widget = PresentList(self.db, self)
        self.midi_tree = MidiCards(self)
        self.top_layout.addWidget(self.present_list_widget, 1)  # 左侧占1份
        self.top_layout.addWidget(self.midi_tree, 2)  # 右侧占1份
        self.main_layout.addLayout(self.top_layout)

        # 添加音乐播放器控制栏
        self.music_player_bar = MusicPlayerBar(self, db)
        self.main_layout.addWidget(self.music_player_bar)

        # 连接信号与槽
        self.connect_signals()

    def stop_play(self):
        self.music_player_bar.stop_player_and_listener()

    def refresh_preset_list(self):
        self.present_list_widget.refresh_preset_list()

    def connect_signals(self):
        self.present_list_widget.signal_item_selected.connect(self.on_preset_selected)
        self.midi_tree.signal_card_clicked.connect(self.on_midi_card_clicked)
        self.music_player_bar.signal_change_song_action.connect(
            self.on_change_song_action
        )

    def on_preset_selected(self, item: Optional[QListWidgetItem]):
        """处理预设选择事件"""
        if item is not None:
            preset_name = item.text()
            if not self.present_name or self.present_name != preset_name:
                mappings = self.db.load_preset(preset_name)
                if mappings is not None:
                    self.note_to_key_mappings = mappings
                    if self.present_name and self.present_name != preset_name:
                        self.music_player_bar.on_note_to_key_cfg_change(mappings)
                    self.present_name = preset_name
                else:
                    Utils.show_warning_infobar(
                        self, "预设加载失败", f"无法加载预设：{preset_name}"
                    )

    def on_midi_card_clicked(self, midi_path: Path):
        if self.note_to_key_mappings is not None:
            self.music_player_bar.on_external_song_change(
                name=midi_path.name,
                path=str(midi_path),
                note_to_key_cfg=self.note_to_key_mappings,
            )
        else:
            Utils.show_warning_infobar(
                self, "未选择预设", "请先从左侧列表中选择一个按键预设"
            )

    def on_change_song_action(self, action):
        """处理歌曲切换操作"""
        self.midi_tree.get_card_and_select(action)
