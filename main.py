import sys
from PyQt6.QtWidgets import QWidget, QPushButton, QApplication
from PyQt6.QtGui import QCloseEvent
import mido
import json
import os

from core.md_player import MIDIPlayer
from core.type import MdPlaybackParam

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

        self.player = MIDIPlayer()
        self.player.start_player()
        self.midi_parent_path = "./res/midi/"
        self.midi_current_idx = 0

    def closeEvent(self, event: QCloseEvent):
        if self.player:
            self.player.stop_player()
        event.accept()

    def _testLoad(self, midi_file_path):
        # 1. 加载 MIDI 文件
        mid = mido.MidiFile(midi_file_path)
        print(f"--- 成功加载 MIDI 文件: {midi_file_path} ---")
        noteToKeyConfig = loadJsonConfig('res/md_cfg/md-test-play.json')
        self.player.prepare(md_playback_param=MdPlaybackParam(midi=mid, noteToKey=noteToKeyConfig))

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
    

def loadJsonConfig(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("错误：文件不存在")
        raise
    except json.JSONDecodeError:
        print("错误：JSON 格式无效")
        raise
    except Exception as e:
        print(f"发生错误：{e}")
        raise

def main():

    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
