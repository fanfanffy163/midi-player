import threading

import pydirectinput
from pynput import keyboard
from PySide6 import QtGui
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLayout, QSizePolicy, QVBoxLayout

# 导入 Fluent Widgets
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    PushButton,
    Slider,
    StrongBodyLabel,
    TransparentToolButton,
)

from ...player.midi_player import QMidiPlayer
from ...player.type import SONG_CHANGE_ACTIONS, MdPlaybackParam
from ...utils.config import cfg
from ...utils.utils import Utils
from ..settings.cmd_binding_setting import CmdKeys


class MusicPlayerBar(QFrame):
    signal_change_song_action = Signal(SONG_CHANGE_ACTIONS)
    signal_cmd_key_pressed = Signal(object)

    """
    使用手动列表管理 (替代 QMediaPlaylist) 的 Qt 6 播放器 Bar
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_playback_rate = 1.0

        # --- 1. 手动播放列表 ---
        self.loop_mode = "ListLoop"
        self._on_play_mode_change(cfg.get(cfg.player_play_single_loop))
        self.last_song: None | dict = None
        pydirectinput.PAUSE = cfg.get(cfg.player_play_press_delay) / 1000

        # --- 2. 初始化midi播放器 ---
        self.player = QMidiPlayer()
        self.player.start_player()

        # --- 3. 初始化UI控件 (使用 Fluent Widgets) ---
        self.init_ui()

        # --- 4. 连接信号与槽 ---
        self.connect_signals()

        # --- 5. 监听键盘
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_press_key_call_by_another_thread
        )
        self.keyboard_listener.start()
        self.shortcuts = cfg.get(cfg.player_play_shortcuts)
        self.shortcuts_lock = threading.Lock()
        self._init_shortcuts()
        self.signal_cmd_key_pressed.connect(self._on_press_key)
        cfg.player_play_shortcuts.valueChanged.connect(self._on_change_shortcuts)

        # 设置播放Bar的温暖样式
        self.setObjectName("MusicPlayerBar")

    def _init_shortcuts(self):
        with self.shortcuts_lock:
            self.trigger_play_shortcut = self.shortcuts.get(CmdKeys.TriggerPlay.name)
            self.start_play_shortcut = self.shortcuts.get(CmdKeys.StartPlay.name)
            self.pause_play_shortcut = self.shortcuts.get(CmdKeys.PausePlay.name)
            self.play_next_shortcut = self.shortcuts.get(CmdKeys.PlayNext.name)
            self.play_pre_shortcut = self.shortcuts.get(CmdKeys.PlayPre.name)

    def _on_change_shortcuts(self, value):
        self.shortcuts = value
        self._init_shortcuts()

    def _on_press_key_call_by_another_thread(self, key):
        name = None
        if hasattr(key, "name"):
            name = key.name
        elif hasattr(key, "char"):
            name = key.char
        else:
            name = key
        with self.shortcuts_lock:
            if name in [
                self.trigger_play_shortcut,
                self.start_play_shortcut,
                self.pause_play_shortcut,
                self.play_next_shortcut,
                self.play_pre_shortcut,
            ]:
                self.signal_cmd_key_pressed.emit(name)

    def _on_press_key(self, name):
        with self.shortcuts_lock:
            if name == self.trigger_play_shortcut:
                self.toggle_play_pause()
            elif name == self.start_play_shortcut:
                self.play_current_song()
            elif name == self.pause_play_shortcut:
                self.pause_current_song()
            elif name == self.play_next_shortcut:
                self.next_song()
            elif name == self.play_pre_shortcut:
                self.previous_song()
            else:
                return

    def init_ui(self):
        # ... (这部分和上一个示例完全相同) ...
        # --- 图标 ---
        self.play_icon = FluentIcon.PLAY
        self.pause_icon = FluentIcon.PAUSE

        # --- 控件 ---
        self.song_info_label = StrongBodyLabel("未选择歌曲")
        self.song_info_label.setWordWrap(False)
        self.song_info_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        Utils.right_elide_label(self.song_info_label)

        self.correct_info_label = BodyLabel("未加载")
        self.correct_info_label.setWordWrap(False)
        self.correct_info_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        Utils.right_elide_label(self.correct_info_label)

        self.prev_button = TransparentToolButton(FluentIcon.LEFT_ARROW)
        self.play_pause_button = TransparentToolButton(self.play_icon)
        self.stop_button = TransparentToolButton(FluentIcon.CLOSE)
        self.next_button = TransparentToolButton(FluentIcon.RIGHT_ARROW)

        self.seek_slider = Slider(Qt.Orientation.Horizontal)
        self.time_label = BodyLabel("00:00 / 00:00")

        self.slow_down_button = PushButton("-0.25")
        self.speed_up_button = PushButton("+0.25")
        self.rate_label = BodyLabel("x1.0")
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- 布局 ---
        main_layout = QHBoxLayout(self)
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        header_layout.addWidget(self.song_info_label)
        header_layout.addWidget(self.correct_info_label)
        main_layout.addLayout(header_layout, 2)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.prev_button)
        control_layout.addWidget(self.play_pause_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.next_button)
        control_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(control_layout, 2)

        seek_layout = QHBoxLayout()
        seek_layout.addWidget(self.seek_slider, 10)
        seek_layout.addWidget(self.time_label)
        main_layout.addLayout(seek_layout, 8)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(self.slow_down_button)
        speed_layout.addWidget(self.rate_label)
        speed_layout.addWidget(self.speed_up_button)
        main_layout.addLayout(speed_layout, 2)

        self.correct_info_label.setObjectName("CorrectInfoLabel")

    def connect_signals(self):
        # --- 按钮点击 ---
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop_current_song)
        self.prev_button.clicked.connect(self.previous_song)
        self.next_button.clicked.connect(self.next_song)

        self.speed_up_button.clicked.connect(self.speed_up)
        self.slow_down_button.clicked.connect(self.slow_down)

        # --- 播放器信号 ---
        self.player.signal_state.connect(self.update_play_button_icon)
        self.player.signal_play_duration.connect(self.update_duration)
        self.player.signal_play_position.connect(self.update_slider_position)
        self.player.signal_correct_info_changed.connect(self._on_correct_info_change)

        # *** 关键：连接歌曲结束信号 ***
        self.player.signal_media_done.connect(self.on_media_status_changed)

        # --- 滑块信号 ---
        self.seek_slider.sliderReleased.connect(self.slider_released)
        self.seek_slider.sliderMoved.connect(self.update_time_on_drag)
        self.seek_slider.clicked.connect(self.update_time_on_click)

        # -- 销毁信号 ---
        self.destroyed.connect(self.player.stop_player)

        # -- 变换播放模式信号 --
        cfg.player_play_single_loop.valueChanged.connect(self._on_play_mode_change)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        Utils.elide_label_handle_resize(self.correct_info_label)
        Utils.elide_label_handle_resize(self.song_info_label)

    def _on_correct_info_change(self, correct_info_label, octave_change):
        text = (
            f"提高{abs(octave_change)}个八度"
            if octave_change > 0
            else f"降低{abs(octave_change)}个八度" if octave_change < 0 else ""
        )
        correct_info = f"命中率:{correct_info_label*100 : .2f}% {text}"
        self.correct_info_label.setText(correct_info)
        Utils.right_elide_label(self.correct_info_label)

    def _on_play_mode_change(self, loop):
        if loop:
            self.loop_mode = "SongLoop"
        else:
            self.loop_mode = "ListLoop"

    def stop_player_and_listener(self):
        self.player.stop_player()
        self.keyboard_listener.stop()

    # --- 核心播放逻辑 ---
    def prepare_song(self, name: str, path: str, note_to_key_cfg: dict):
        # 设置媒体源并播放
        self.last_song = {
            "name": name,
            "path": path,
            "note_to_key_cfg": note_to_key_cfg,
        }
        self.player.prepare(
            md_playback_param=MdPlaybackParam(
                midiPath=path, noteToKeyMapping=note_to_key_cfg
            )
        )
        self.song_info_label.setText(name)
        Utils.right_elide_label(self.song_info_label)

    def play_current_song(self):
        if self.last_song:
            self.player.play()

    def next_song(self):
        self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.NEXT_SONG)  # 列表循环

    def previous_song(self):
        self.signal_change_song_action.emit(
            SONG_CHANGE_ACTIONS.PREVIOUS_SONG
        )  # 列表循环

    def stop_current_song(self):
        self.player.stop()
        self.update_slider_position(0)

    def pause_current_song(self):
        if self.last_song:
            self.player.pause()

    def toggle_play_pause(self):
        if self.player.get_playback_state() == QMidiPlayer.PlayState.PLAYING:
            self.pause_current_song()
        else:
            self.play_current_song()

    def on_media_status_changed(self, done):
        """关键槽函数：处理歌曲自动播放完毕"""
        if done:
            if self.loop_mode == "SongLoop":
                # 单曲循环
                self.play_current_song()
            else:
                # 触发下一曲 (ListLoop 或 NoLoop 逻辑在 next_song 中处理)
                self.next_song()

    def update_play_button_icon(self, state):
        if state == QMidiPlayer.PlayState.PLAYING:
            self.play_pause_button.setIcon(self.pause_icon)
        else:
            self.play_pause_button.setIcon(self.play_icon)

    def update_duration(self, duration):
        self.seek_slider.setRange(0, duration)
        if duration > 0:
            self.update_time_label(0, duration)

    def update_slider_position(self, position):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        self.update_time_label(position, self.seek_slider.maximum())

    def slider_released(self):
        self.player.seek(self.seek_slider.value())

    def update_time_on_drag(self, position):
        self.update_time_label(position, self.seek_slider.maximum())

    def update_time_on_click(self, position):
        self.player.seek(position)
        self.update_time_label(position, self.seek_slider.maximum())

    def format_time(self, milliseconds):
        seconds = round(milliseconds / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"

    def update_time_label(self, position, duration):
        self.time_label.setText(
            f"{self.format_time(position)} / {self.format_time(duration)}"
        )

    def speed_up(self):
        self.current_playback_rate = min(self.current_playback_rate + 0.25, 2.0)
        self.player.set_speed(self.current_playback_rate)
        self.rate_label.setText(f"x{self.current_playback_rate:.2f}")

    def slow_down(self):
        self.current_playback_rate = max(self.current_playback_rate - 0.25, 0.5)
        self.player.set_speed(self.current_playback_rate)
        self.rate_label.setText(f"x{self.current_playback_rate:.2f}")
