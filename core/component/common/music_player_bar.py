from PyQt6.QtWidgets import (QHBoxLayout, 
                             QFrame)
from PyQt6.QtCore import Qt,pyqtSignal

# 导入 Fluent Widgets
from qfluentwidgets import (TitleLabel, BodyLabel,
                            TransparentToolButton, PushButton, Slider, 
                            FluentIcon, InfoBar, InfoBarPosition)

from ...player.type import MdPlaybackParam,SONG_CHANGE_ACTIONS
from ...player.midi_player import QMidiPlayer



class MusicPlayerBar(QFrame):
    signal_change_song_action = pyqtSignal(SONG_CHANGE_ACTIONS)

    """
    使用手动列表管理 (替代 QMediaPlaylist) 的 Qt 6 播放器 Bar
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_playback_rate = 1.0
        
        # --- 1. 手动播放列表 ---
        self.loop_mode = "ListLoop" # "ListLoop", "NoLoop", "SongLoop"
        self.last_song : None | dict = None

        # --- 2. 初始化midi播放器 ---
        self.player = QMidiPlayer()
        self.player.start_player()
        
        # --- 3. 初始化UI控件 (使用 Fluent Widgets) ---
        self.init_ui()

        # --- 4. 连接信号与槽 ---
        self.connect_signals()

        # 设置播放Bar的温暖样式
        self.setObjectName("MusicPlayerBar")
        self.setStyleSheet("""
            #MusicPlayerBar {
                background-color: #fdfaf5;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
        """)

    def init_ui(self):
        # ... (这部分和上一个示例完全相同) ...
        # --- 图标 ---
        self.play_icon = FluentIcon.PLAY
        self.pause_icon = FluentIcon.PAUSE

        # --- 控件 ---
        self.song_info_label = TitleLabel("未选择歌曲")
        self.song_info_label.setWordWrap(True)

        self.prev_button = TransparentToolButton(FluentIcon.LEFT_ARROW)
        self.play_pause_button = TransparentToolButton(self.play_icon)
        self.stop_button = TransparentToolButton(FluentIcon.CLOSE)
        self.next_button = TransparentToolButton(FluentIcon.RIGHT_ARROW)
        
        for btn in [self.prev_button, self.play_pause_button, self.stop_button, self.next_button]:
            btn.setIconSize(btn.iconSize() * 1.2) 

        self.seek_slider = Slider(Qt.Orientation.Horizontal)
        self.time_label = BodyLabel("00:00 / 00:00")

        self.slow_down_button = PushButton("-0.25")
        self.speed_up_button = PushButton("+0.25")
        self.rate_label = BodyLabel("x1.0")
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- 布局 ---
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.song_info_label, 2)
        
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.prev_button)
        control_layout.addWidget(self.play_pause_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.next_button)
        main_layout.addLayout(control_layout, 1)

        seek_layout = QHBoxLayout()
        seek_layout.addWidget(self.seek_slider, 10)
        seek_layout.addWidget(self.time_label)
        main_layout.addLayout(seek_layout, 4)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(self.slow_down_button)
        speed_layout.addWidget(self.rate_label)
        speed_layout.addWidget(self.speed_up_button)
        main_layout.addLayout(speed_layout, 1)

    def connect_signals(self):
        # --- 按钮点击 ---
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop_playback)
        self.prev_button.clicked.connect(self.previous_song)
        self.next_button.clicked.connect(self.next_song)
        
        self.speed_up_button.clicked.connect(self.speed_up)
        self.slow_down_button.clicked.connect(self.slow_down)

        # --- 播放器信号 ---
        self.player.signal_state.connect(self.update_play_button_icon)
        self.player.signal_play_duration.connect(self.update_duration)
        self.player.signal_play_position.connect(self.update_slider_position)
        
        # *** 关键：连接歌曲结束信号 ***
        self.player.signal_media_done.connect(self.on_media_status_changed)

        # --- 滑块信号 ---
        self.seek_slider.sliderReleased.connect(self.slider_released)
        self.seek_slider.sliderMoved.connect(self.update_time_on_drag)
        self.seek_slider.clicked.connect(self.update_time_on_click)

        # -- 销毁信号 ---
        self.destroyed.connect(self.player.stop_player)


    # --- 核心播放逻辑 ---
    def prepare_song(self, name : str, path: str, note_to_key_cfg: dict):
        # 设置媒体源并播放
        self.last_song = {"name": name, "path": path, "note_to_key_cfg": note_to_key_cfg}
        self.player.prepare(md_playback_param=MdPlaybackParam(midiPath=path, noteToKeyMapping=note_to_key_cfg))
        self.song_info_label.setText(name)

    def play_current_song(self):
        if self.last_song:
            self.player.play()
            
    def next_song(self):     
        if self.loop_mode == "ListLoop":
            self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.NEXT_SONG) # 列表循环
        elif self.loop_mode == "NoLoop":
            self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.STOP) # 非循环，播放完停止
        elif self.loop_mode == "SongLoop":
            # 单曲循环，继续播放当前
            self.play_current_song()
            self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.LOOP_THIS)

    def previous_song(self):
        if self.loop_mode == "ListLoop":
            self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.PREVIOUS_SONG) # 列表循环
        elif self.loop_mode == "NoLoop":
            self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.STOP) # 非循环，播放完停止
        elif self.loop_mode == "SongLoop":
            # 单曲循环，继续播放当前
            self.play_current_song()
            self.signal_change_song_action.emit(SONG_CHANGE_ACTIONS.LOOP_THIS)

    def stop_playback(self):
        self.player.stop()
        self.update_slider_position(0)

    def toggle_play_pause(self):
        if self.player.playbackState() == QMidiPlayer.PlayState.PLAYING:
            self.player.pause()
        else:
            self.play_current_song()

    def on_media_status_changed(self, done):
        """ 关键槽函数：处理歌曲自动播放完毕 """
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
        print(f"duration : {duration}")
        self.seek_slider.setRange(0, duration)
        if duration > 0:
            self.update_time_label(0, duration)

    def update_slider_position(self, position):
        print(f"position : {position}")
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
        minutes = (seconds // 60)
        seconds = (seconds % 60)
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