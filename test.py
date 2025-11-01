import sys
from PyQt6.QtWidgets import QWidget, QPushButton, QApplication
from PyQt6.QtGui import QCloseEvent
import os

from core.player.md_player import QMidiPlayer
from core.player.type import MdPlaybackParam
from core.component.music_player_bar import MusicPlayerBar
from qfluentwidgets import (setTheme, Theme)
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel as QtLabel)
from PyQt6.QtCore import Qt

class Example(QWidget):

    def __init__(self):
        super().__init__()

        self.initUI()


    def initUI(self):

        qbtn = QPushButton('Quit', self)
        qbtn.clicked.connect(self.testQuit)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(50, 50)

        qbtn = QPushButton('Play', self)
        qbtn.clicked.connect(self.testPlay)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(20, 100)

        qbtn = QPushButton('Stop', self)
        qbtn.clicked.connect(self.testStop)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(120, 100)

        qbtn = QPushButton('Puase', self)
        qbtn.clicked.connect(self.testPuase)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(220, 100)

        qbtn = QPushButton('SpeedUp', self)
        qbtn.clicked.connect(self.testSpeedUp)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(320, 100)

        qbtn = QPushButton('SpeedDown', self)
        qbtn.clicked.connect(self.testSpeedDown)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(420, 100)

        qbtn = QPushButton('Seek', self)
        qbtn.clicked.connect(self.testSeek)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(520, 100)

        qbtn = QPushButton('Pre', self)
        qbtn.clicked.connect(self.testPre)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(20, 130)

        qbtn = QPushButton('Next', self)
        qbtn.clicked.connect(self.testNext)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(120, 130)

        self.setGeometry(300, 300, 800, 600)
        self.setWindowTitle('Quit button')
        self.show()

        self.player = QMidiPlayer()
        self.player.start_player()
        self.midi_parent_path = "./res/midi/"
        self.midi_current_idx = 0

    def closeEvent(self, event: QCloseEvent):
        if self.player:
            self.player.stop_player()
        event.accept()

    def _testLoad(self, midi_file_path):
        self.player.prepare(md_playback_param=MdPlaybackParam(midiPath=midi_file_path, noteToKeyPath='res/md_cfg/md-test-play.json'))
        self.testPlay()

    def testPre(self):
        all_files = os.listdir(self.midi_parent_path)
        total_len = len(all_files)
        self.midi_current_idx = self.midi_current_idx - 1 if self.midi_current_idx > 0 else total_len - 1
        file = all_files[self.midi_current_idx]
        self._testLoad(f"{self.midi_parent_path}{file}")

    def testNext(self):
        all_files = os.listdir(self.midi_parent_path)
        total_len = len(all_files)
        self.midi_current_idx = self.midi_current_idx + 1 if self.midi_current_idx < total_len - 1 else 0
        file = all_files[self.midi_current_idx]
        self._testLoad(f"{self.midi_parent_path}/{file}")

    def testPlay(self):
        if self.player:
            self.player.play()

    def testStop(self):
        if self.player:
            self.player.stop()

    def testPuase(self):
        if self.player:
            self.player.pause()
    
    def testSpeedUp(self):
        if self.player:
            self.player.set_speed(self.player.get_playback_info()["speed"] + 0.1)

    def testSpeedDown(self):
        if self.player:
            self.player.set_speed(self.player.get_playback_info()["speed"] - 0.1)

    def testSeek(self):
        if self.player:
            self.player.seek(self.player.get_playback_info()["current_time_ms"] + 10000)

    def testQuit(self):       
        QApplication.instance().quit()
    

def main():

    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec())


# --- 运行主程序 (与之前相同) ---
def testBar():
    app = QApplication(sys.argv)
    
    # 设置 Fluent UI 的亮色主题
    setTheme(Theme.LIGHT)

    main_window = QWidget()
    main_window.setWindowTitle("Fluent 音乐播放器 (Qt 6 手动列表)")
    main_window.resize(900, 150)
    
    window_layout = QVBoxLayout(main_window)
    info_label = QtLabel(
        "这是一个使用 PyQt-Fluent-Widgets 制作的音乐播放Bar。\n"
        "已使用 Qt 6 的手动列表管理方案替代 QMediaPlaylist。"
    )
    info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    info_label.setStyleSheet("color: #606060; margin: 10px;")
    
    player_bar = MusicPlayerBar()
    
    window_layout.addWidget(info_label)
    window_layout.addWidget(player_bar)
    window_layout.addStretch(1)

    main_window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    testBar()
