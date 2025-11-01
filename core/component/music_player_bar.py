from PyQt6.QtWidgets import (QHBoxLayout, 
                             QFrame)
from PyQt6.QtCore import Qt

# 导入 Fluent Widgets
from qfluentwidgets import (TitleLabel, BodyLabel,
                            TransparentToolButton, PushButton, Slider, 
                            FluentIcon, InfoBar, InfoBarPosition)

from ..player.type import MdPlaybackParam
from ..player.md_player import QMidiPlayer

class MusicPlayerBar(QFrame):
    """
    使用手动列表管理 (替代 QMediaPlaylist) 的 Qt 6 播放器 Bar
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_playback_rate = 1.0
        
        # --- 1. 手动播放列表 ---
        self.song_list = [] # 存储 QUrl
        self.current_index = -1
        self.loop_mode = "ListLoop" # "ListLoop", "NoLoop", "SongLoop"

        # --- 2. 初始化midi播放器 ---
        self.player = QMidiPlayer()
        self.player.start_player()
        
        # --- 3. 初始化UI控件 (使用 Fluent Widgets) ---
        self.init_ui()

        # --- 4. 连接信号与槽 ---
        self.connect_signals()

        # --- 5. 加载示例播放列表 ---
        self.load_dummy_playlist()

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


    def load_dummy_playlist(self):     
        self.song_list = [
            "./res/midi/test.mid",
            "./res/midi/潮鳴り.mid"
        ]
        
        # 加载第一首歌准备播放
        self.play_song_at_index(0)
        self.player.pause() # 加载后先暂停

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


    # --- 核心播放逻辑 (替代 QMediaPlaylist) ---

    def play_song_at_index(self, index):
        if 0 <= index < len(self.song_list):
            self.current_index = index
            media_source = self.song_list[self.current_index]
            
            # 设置媒体源并播放
            self.player.prepare(md_playback_param=MdPlaybackParam(midiPath=media_source, noteToKeyPath='res/md_cfg/md-test-play.json'))
            self.player.play()
            
            self.song_info_label.setText(media_source)
        else:
            self.current_index = -1
            self.player.stop()
            self.song_info_label.setText("播放列表为空")
            
    def next_song(self):
        if not self.song_list:
            return
        
        new_index = self.current_index + 1
        if new_index >= len(self.song_list):
            if self.loop_mode == "ListLoop":
                new_index = 0 # 列表循环
            else:
                return # 不循环
        
        self.play_song_at_index(new_index)

    def previous_song(self):
        if not self.song_list:
            return

        new_index = self.current_index - 1
        if new_index < 0:
            if self.loop_mode == "ListLoop":
                new_index = len(self.song_list) - 1 # 列表循环
            else:
                return # 不循环

        self.play_song_at_index(new_index)

    def stop_playback(self):
        self.player.stop()
        self.update_slider_position(0)

    def toggle_play_pause(self):
        if self.player.playbackState() == QMidiPlayer.PlayState.PLAYING:
            self.player.pause()
        else:
            if not self.song_list:
                InfoBar.warning(
                    title='播放列表为空',
                    content='请先确保已正确加载音乐文件',
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                return
            
            # 如果是停止状态或未加载，播放当前 (或第一首)
            if self.current_index == -1:
                self.play_song_at_index(0)
            else:
                self.player.play()

    def on_media_status_changed(self, done):
        """ 关键槽函数：处理歌曲自动播放完毕 """
        if done:
            if self.loop_mode == "SongLoop":
                # 单曲循环
                self.play_song_at_index(self.current_index)
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
        self.update_time_label(position, self.player.duration())

    def slider_released(self):
        self.player.seek(self.seek_slider.value())

    def update_time_on_drag(self, position):
        self.update_time_label(position, self.player.duration())

    def update_time_on_click(self, position):
        self.player.seek(position)
        self.update_time_label(position, self.player.duration())      

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