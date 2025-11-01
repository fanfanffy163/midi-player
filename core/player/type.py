from enum import Enum

from mido import MidiFile
from pynput.keyboard import Key  

#
#无法匹配音高时的处理方式
# - 'no-fix'：不进行任何处理，保持原音高播放
# - 'shift-fix'：将无法匹配的音高上/下移八度
#- 'nearby-fix'：寻找最接近的可用音高进行匹配
# 
class MisMatchMode(Enum):
    NoFix       = 1
    ShiftFix    = 2
    NearbyFix   = 3

class MdPlaybackParam:

    # 无法匹配音高时的处理方式
    misMatchMode: MisMatchMode = MisMatchMode.NoFix

    # 音符名称到键盘按键的映射表
    note_to_key_path: str

    midi_path : MidiFile

    def __init__(self, midiPath: str,
                 misMatchMode: MisMatchMode = MisMatchMode.NoFix,
                 noteToKeyPath: str = ''):
        self.midi_path = midiPath
        self.misMatchMode = misMatchMode
        self.note_to_key_path = noteToKeyPath

class MidiNoteBiMap:
    def __init__(self):
        self.midi_to_note = {}  # 正向映射：MIDI编号 → 音符名（如60 → "C4"）
        self.note_to_midi = {}  # 反向映射：音符名 → MIDI编号（如"C4" → 60）
        self._init_mapping()  # 初始化映射关系

    def _init_mapping(self):
        """初始化MIDI与音符的映射关系"""
        # 12个半音的音名（按顺序：C, C#, D, D#, E, F, F#, G, G#, A, A#, B）
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        # MIDI编号范围：0-127
        for midi in range(128):  # 0到127（包含）
            # 计算八度：中央C（60=C4）为基准，每12个半音一个八度
            octave = (midi - 12) // 12  # 确保60对应4
            # 计算在12个半音中的索引（0-11）
            note_index = midi % 12
            # 拼接音符名（如C4、D#5）
            note_name = f"{note_names[note_index]}{octave}"
            # 建立双向映射
            self.midi_to_note[midi] = note_name
            self.note_to_midi[note_name] = midi

    def get_note_by_midi(self, midi: int):
        """通过MIDI编号获取音符名（如60 → "C4"）"""
        if 0 <= midi <= 127:
            return self.midi_to_note.get(midi)
        return None  # 超出范围返回None

    def get_midi_by_note(self, note_name: str):
        """通过音符名获取MIDI编号（如"C4" → 60）"""
        return self.note_to_midi.get(note_name, None)

    def is_valid_midi(self, midi: int) -> bool:
        """检查MIDI编号是否有效（0-127）"""
        return 0 <= midi <= 127

    def is_valid_note(self, note_name: str) -> bool:
        """检查音符名是否有效（如"C4"有效，"H3"无效）"""
        return note_name in self.note_to_midi


# 实例化双向映射（全局可用）
MIDI_NOTE_MAP = MidiNoteBiMap()


#定义一个全局的按键映射表
KEY_MAP: dict[str, any] = {
    'shift': Key.shift,
    'ctrl': Key.ctrl,
    'alt': Key.alt,
    'cmd': Key.cmd,          # 适用于 macOS
    'space': Key.space,
    'enter': Key.enter,
    'tab': Key.tab,
    'esc': Key.esc,
    'backspace': Key.backspace,
    'delete': Key.delete,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'page_up': Key.page_up,
    'page_down': Key.page_down,
    'home': Key.home,
    'end': Key.end,
    'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
    'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
    'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
}