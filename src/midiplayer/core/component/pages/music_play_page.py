from pathlib import Path
from typing import Optional

from loguru import logger
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, IndeterminateProgressRing

from midiplayer.core.component.common.midi_cards import MidiCards
from midiplayer.core.component.common.music_player_bar import MusicPlayerBar
from midiplayer.core.component.common.present_list import PresentList
from midiplayer.core.component.common.qlazy_widget import QLazyWidget
from midiplayer.core.utils.db_manager import DBManager
from midiplayer.core.utils.style_sheet import StyleSheet
from midiplayer.core.utils.utils import Utils


class MusicPlayPage(QLazyWidget):

    def __init__(self, db: DBManager, parent: Optional[QWidget] = None):
        super().__init__(parent, "正在加载播放器...")
        self.setObjectName("MusicPlayPage")
        self.db = db

        # 播放参数暂存
        self.note_to_key_mappings: dict[str, str] = None
        self.present_name: str | None = None
        self.midi_path: Path | None = None

    def _init_ui(self, ui_content: QWidget):

        self.main_layout = QVBoxLayout(ui_content)
        # --- 原本的初始化代码 ---
        self.top_layout = QHBoxLayout()
        self.present_list_widget = PresentList(self.db, self)
        self.midi_tree = MidiCards(self)
        self.top_layout.addWidget(self.present_list_widget, 1)
        self.top_layout.addWidget(self.midi_tree, 2)
        self.main_layout.addLayout(self.top_layout)

        self.music_player_bar = MusicPlayerBar(self, self.db)
        self.main_layout.addWidget(self.music_player_bar)

        self.connect_signals()
        # Style 应用
        StyleSheet.MUSIC_PLAY_PAGE.apply(self)
        logger.info("MusicPlayPage UI loaded")

    def stop_play(self):
        # 还没加载就不用停
        if self.lazy_loaded and hasattr(self, "music_player_bar"):
            self.music_player_bar.stop_player_and_listener()

    def refresh_preset_list(self):
        # 如果没加载，不需要刷新；等加载时会自动初始化
        if self.lazy_loaded and hasattr(self, "present_list_widget"):
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
            self._handle_cfg_and_song_prepared(
                new_midi_path=self.midi_path, new_present_name=preset_name
            )

    def on_midi_card_clicked(self, midi_path: Path):
        self._handle_cfg_and_song_prepared(
            new_midi_path=midi_path, new_present_name=self.present_name
        )

    def _handle_cfg_and_song_prepared(self, new_midi_path: Path, new_present_name: str):
        if self.midi_path and self.present_name:
            if self.midi_path != new_midi_path:
                # 路径不同，直接触发切歌
                self.music_player_bar.on_external_song_change(
                    name=new_midi_path.name,
                    path=str(new_midi_path),
                    note_to_key_cfg=self.note_to_key_mappings,
                )
                self.midi_path = new_midi_path
            elif self.present_name != new_present_name:
                # 预设切换
                mappings = self.db.load_preset(new_present_name)
                if mappings is not None:
                    self.note_to_key_mappings = mappings
                    self.music_player_bar.on_note_to_key_cfg_change(mappings)
                    self.present_name = new_present_name
                else:
                    Utils.show_warning_infobar(
                        self, "预设加载失败", f"无法加载预设：{new_present_name}"
                    )
                    return
        else:
            self.midi_path = new_midi_path
            if new_present_name:
                mappings = self.db.load_preset(new_present_name)
                if mappings is not None:
                    self.note_to_key_mappings = mappings
                    self.present_name = new_present_name
                else:
                    Utils.show_warning_infobar(
                        self, "预设加载失败", f"无法加载预设：{new_present_name}"
                    )
                    return
            # 若配置已经完善，开始播放
            if self.midi_path and self.present_name:
                self.music_player_bar.on_external_song_change(
                    name=new_midi_path.name,
                    path=str(new_midi_path),
                    note_to_key_cfg=self.note_to_key_mappings,
                )

    def on_change_song_action(self, action):
        """处理歌曲切换操作"""
        self.midi_tree.get_card_and_select(action)
