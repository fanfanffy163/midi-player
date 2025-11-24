from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from ...utils.note_key_binding_db_manger import NoteKeyBindingDBManager
from ...utils.style_sheet import StyleSheet
from ...utils.utils import Utils
from ..common.midi_cards import MidiCards
from ..common.music_player_bar import MusicPlayerBar
from ..common.present_list import PresentList


class MusicPlayPage(QWidget):
    """预设管理页面"""

    def __init__(self, db: NoteKeyBindingDBManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MusicPlayPage")
        self.db = db

        # 播放需要使用的参数
        self.note_to_key_mappings: Dict[str, str] = None
        self.song_name: str = None
        self.song_path: Path = None

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
        self.music_player_bar = MusicPlayerBar(self)
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
            mappings = self.db.load_preset(preset_name)
            if mappings is not None:
                self.note_to_key_mappings = mappings
            else:
                Utils.show_warning_infobar(
                    self, "预设加载失败", f"无法加载预设：{preset_name}"
                )

    def on_midi_card_clicked(self, midi_path: Path):
        self.song_path = midi_path
        self.song_name = midi_path.name
        if self.note_to_key_mappings is not None:
            self.music_player_bar.prepare_song(
                name=self.song_name,
                path=str(self.song_path),
                note_to_key_cfg=self.note_to_key_mappings,
            )
            self.music_player_bar.play_current_song()
        else:
            Utils.show_warning_infobar(
                self, "未选择预设", "请先从左侧列表中选择一个按键预设"
            )

    def on_change_song_action(self, action):
        """处理歌曲切换操作"""
        self.midi_tree.get_card_and_select(action)
