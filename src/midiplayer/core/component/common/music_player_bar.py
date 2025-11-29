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
    Flyout,
    FlyoutAnimationType,
    FlyoutView,
    PushButton,
    Slider,
    StrongBodyLabel,
    TransparentToolButton,
)

from midiplayer.core.component.common.trace_select_view import TrackContentView
from midiplayer.core.utils.note_key_binding_db_manger import DBManager

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

    def __init__(self, parent=None, db: DBManager = None):
        super().__init__(parent)
        self.current_playback_rate = 1.0
        self.db = db

        # --- 1. 手动播放列表 ---
        self.loop_mode = "ListLoop"
        self.user_action_stop = None
        self._on_play_mode_change(cfg.get(cfg.player_play_single_loop))
        self.current_song: None | dict = None
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
                self.toggle_play()
            elif name == self.pause_play_shortcut:
                self.toggle_pause()
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

        # --- 新增：音轨选择按钮 ---
        # 放在速度控制旁边，或者控制栏右侧
        self.track_select_button = TransparentToolButton(
            FluentIcon.MUSIC_FOLDER
        )  # 或者选一个像图层的图标
        self.track_select_button.setToolTip("选择音轨")
        self.track_select_button.clicked.connect(self.show_track_selection_flyout)

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
        # 新增
        speed_layout.addSpacing(10)
        speed_layout.addWidget(self.track_select_button)
        main_layout.addLayout(speed_layout, 2)

        self.correct_info_label.setObjectName("CorrectInfoLabel")

    def connect_signals(self):
        # --- 按钮点击 ---
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.toggle_stop)
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

    # --- 核心逻辑：显示弹窗 ---
    def show_track_selection_flyout(self):
        if not self.current_song:
            return

        current_path = self.current_song["path"]

        # 1. 获取后端音轨信息
        # 格式示例: [{"index": 0, "name": "Piano"}, {"index": 1, "name": "Bass"}]
        track_info_list = self._get_track_details()

        # 2. 获取当前配置
        active_tracks = self.db.get_active_tracks(current_path)
        if active_tracks is None:
            # 默认全部激活
            active_tracks = [t["index"] for t in track_info_list]

        # 3. 创建并显示 Flyout
        view = TrackContentView(track_info_list, active_tracks)
        view.signal_track_state_changed.connect(self._on_track_toggled)

        # 使用 FluentWidgets 的 Flyout
        Flyout.make(
            view,
            self.track_select_button,
            self.window(),
            aniType=FlyoutAnimationType.PULL_UP,
        )

    def _get_track_details(self):
        return self.player.get_all_tracks()

    def _get_total_tracks_idx(self):
        return [x["index"] for x in self.player.get_all_tracks()]

    def _on_track_toggled(self, track_index, is_checked):
        if not self.current_song:
            return

        total_track_idx = None
        current_path = self.current_song["path"]
        last_active_tracks = self.current_song["tracks"]
        if last_active_tracks is None:
            last_active_tracks = self._get_total_tracks_idx()

        # 更新 active list
        active_list = self._get_tracks_by_path(current_path)
        if active_list is None:
            active_list = (
                self._get_total_tracks_idx()
                if total_track_idx is None
                else total_track_idx
            )

        if is_checked:
            if track_index not in active_list:
                active_list.append(track_index)
        else:
            if track_index in active_list:
                active_list.remove(track_index)

        active_list.sort()
        if set(last_active_tracks) == set(active_list):
            return

        # 处理播放
        self._handle_cfg_changed(new_active_tracks=active_list)
        # 保存到磁盘
        self.db.save_active_tracks(current_path, active_list)

    # 处理预设配置变化/轨道信息变化
    def _handle_cfg_changed(self, new_note_to_key_cfg=None, new_active_tracks=None):
        # 先停止当前歌曲
        if self.current_song:
            tmp_playing = (
                self.player.get_playback_state() == QMidiPlayer.PlayState.PLAYING
            )
            self.prepare_song(
                name=self.current_song["name"],
                path=self.current_song["path"],
                note_to_key_cfg=(
                    new_note_to_key_cfg
                    if new_note_to_key_cfg is not None
                    else self.current_song["note_to_key_cfg"]
                ),
                tracks=(
                    new_active_tracks
                    if new_active_tracks is not None
                    else self.current_song["tracks"]
                ),
            )
            if tmp_playing:
                self.play_current_song()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        Utils.elide_label_handle_resize(self.correct_info_label)
        Utils.elide_label_handle_resize(self.song_info_label)

    def _on_correct_info_change(self, correct_info_label, octave_change):
        text = (
            f"提高{abs(octave_change)}个调"
            if octave_change > 0
            else f"降低{abs(octave_change)}个调" if octave_change < 0 else ""
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
    def prepare_song(self, name: str, path: str, note_to_key_cfg: dict, tracks):
        # 设置媒体源并播放
        self.current_song = {
            "name": name,
            "path": path,
            "note_to_key_cfg": note_to_key_cfg,
            "tracks": tracks,
        }
        self.player.prepare(
            md_playback_param=MdPlaybackParam(
                midiPath=path, noteToKeyMapping=note_to_key_cfg, active_tracks=tracks
            )
        )
        self.song_info_label.setText(name)
        Utils.right_elide_label(self.song_info_label)

    def next_song(self):
        self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.NEXT_SONG)  # 列表循环

    def previous_song(self):
        self.signal_change_song_action.emit(
            SONG_CHANGE_ACTIONS.PREVIOUS_SONG
        )  # 列表循环

    # 用户手动触发的播放、停止、暂停，携带一下用户信号，用于决定后续切换歌时的行为
    # ---------------------------------
    def toggle_stop(self):
        self.stop_current_song()
        self.user_action_stop = True

    def toggle_play(self):
        self.play_current_song()
        self.user_action_stop = False

    def toggle_pause(self):
        self.pause_current_song()
        self.user_action_stop = True

    def toggle_play_pause(self):
        if self.player.get_playback_state() == QMidiPlayer.PlayState.PLAYING:
            self.pause_current_song()
            self.user_action_stop = True
        else:
            self.play_current_song()
            self.user_action_stop = False

    # ---------------------------------
    # 用户主动触发结束

    def play_current_song(self):
        if self.current_song:
            self.player.play()

    def stop_current_song(self):
        self.player.stop()
        self.update_slider_position(0)

    def pause_current_song(self):
        if self.current_song:
            self.player.pause()

    def _get_tracks_by_path(self, path):
        return self.db.get_active_tracks(path)

    def on_external_song_change(self, name, path, note_to_key_cfg):
        tracks = self._get_tracks_by_path(path)
        self.prepare_song(
            name=name, path=path, note_to_key_cfg=note_to_key_cfg, tracks=tracks
        )
        # 根据之前歌是否被用户停止，决定切换后歌的行为
        if not self.user_action_stop:
            self.play_current_song()
        else:
            self.stop_current_song()

    def on_note_to_key_cfg_change(self, new_note_to_key_cfg):
        self._handle_cfg_changed(new_note_to_key_cfg=new_note_to_key_cfg)

    def on_media_status_changed(self, done):
        """关键槽函数：处理歌曲自动播放完毕"""
        if done:
            if self.loop_mode == "SongLoop":
                # 单曲循环
                self.play_current_song()
            else:
                # 触发下一曲
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
