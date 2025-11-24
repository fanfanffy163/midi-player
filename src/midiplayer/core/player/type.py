from enum import Enum

from mido import MidiFile
from pynput.keyboard import Key
from PySide6.QtCore import Qt


#
# 无法匹配音高时的处理方式
# - 'no-fix'：不进行任何处理，保持原音高播放
# - 'shift-fix'：将无法匹配的音高上/下移八度
# - 'nearby-fix'：寻找最接近的可用音高进行匹配
#
class MisMatchMode(Enum):
    NoFix = 1
    ShiftFix = 2
    NearbyFix = 3


class MdPlaybackParam:

    # 无法匹配音高时的处理方式
    misMatchMode: MisMatchMode = MisMatchMode.NoFix

    # 音符名称到键盘按键的映射表
    note_to_key_mapping: dict

    midi_path: MidiFile

    def __init__(
        self,
        midiPath: str,
        misMatchMode: MisMatchMode = MisMatchMode.NoFix,
        noteToKeyMapping: dict = {},
    ):
        self.midi_path = midiPath
        self.misMatchMode = misMatchMode
        self.note_to_key_mapping = noteToKeyMapping


class MidiNoteBiMap:
    def __init__(self):
        self.midi_to_note = {}  # 正向映射：MIDI编号 → 音符名（如60 → "C4"）
        self.note_to_midi = {}  # 反向映射：音符名 → MIDI编号（如"C4" → 60）
        self._init_mapping()  # 初始化映射关系

    def _init_mapping(self):
        """初始化MIDI与音符的映射关系"""
        # 12个半音的音名（按顺序：C, C#, D, D#, E, F, F#, G, G#, A, A#, B）
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
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


class SONG_CHANGE_ACTIONS(Enum):
    PREVIOUS_SONG = 1
    NEXT_SONG = 2
    LOOP_THIS = 3
    STOP = 4


# 实例化双向映射（全局可用）
MIDI_NOTE_MAP = MidiNoteBiMap()


# 存储的字符串按键值枚举
class KEY_VALUES(Enum):
    SHIFT = "shift"
    CTRL = "ctrl"
    ALT = "alt"
    ctrl = "ctrl"
    CMD = "cmd"
    SPACE = "space"
    ENTER = "enter"
    TAB = "tab"
    ESC = "esc"
    BACKSPACE = "backspace"
    DELETE = "delete"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PAGE_UP = "page_up"
    PAGE_DOWN = "page_down"
    HOME = "home"
    END = "end"
    INSERT = "insert"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
    COMMA = ","
    PERIOD = "."
    SLASH = "/"
    SEMICOLON = ";"
    APOSTROPHE = "'"
    OPENING_BRACKET = "["
    CLOSING_BRACKET = "]"
    SLASH_BACK = "\\"
    EQUAL = "="
    MINUS = "-"


# 定义一个全局的按键映射表
KEY_MAP: dict[str, any] = {
    KEY_VALUES.SHIFT.value: Key.shift,
    KEY_VALUES.CTRL.value: Key.ctrl,
    KEY_VALUES.ALT.value: Key.alt,
    KEY_VALUES.CMD.value: Key.cmd,  # 适用于 macOS
    KEY_VALUES.SPACE.value: Key.space,
    KEY_VALUES.ENTER.value: Key.enter,
    KEY_VALUES.TAB.value: Key.tab,
    KEY_VALUES.ESC.value: Key.esc,
    KEY_VALUES.BACKSPACE.value: Key.backspace,
    KEY_VALUES.DELETE.value: Key.delete,
    KEY_VALUES.UP.value: Key.up,
    KEY_VALUES.DOWN.value: Key.down,
    KEY_VALUES.LEFT.value: Key.left,
    KEY_VALUES.RIGHT.value: Key.right,
    KEY_VALUES.PAGE_UP.value: Key.page_up,
    KEY_VALUES.PAGE_DOWN.value: Key.page_down,
    KEY_VALUES.HOME.value: Key.home,
    KEY_VALUES.END.value: Key.end,
    KEY_VALUES.INSERT.value: Key.insert,
    KEY_VALUES.F1.value: Key.f1,
    KEY_VALUES.F2.value: Key.f2,
    KEY_VALUES.F3.value: Key.f3,
    KEY_VALUES.F4.value: Key.f4,
    KEY_VALUES.F5.value: Key.f5,
    KEY_VALUES.F6.value: Key.f6,
    KEY_VALUES.F7.value: Key.f7,
    KEY_VALUES.F8.value: Key.f8,
    KEY_VALUES.F9.value: Key.f9,
    KEY_VALUES.F10.value: Key.f10,
    KEY_VALUES.F11.value: Key.f11,
    KEY_VALUES.F12.value: Key.f12,
}

CONTROL_KEY_MAP = {
    KEY_VALUES.SHIFT.value: Key.shift,
    KEY_VALUES.CTRL.value: Key.ctrl,
    KEY_VALUES.ALT.value: Key.alt,
    KEY_VALUES.CMD.value: Key.cmd,  # 适用于 macOS
}

# Qt.Key
QT_MODIFIER_KEYS = {
    Qt.Key.Key_Control: KEY_VALUES.CTRL.value,
    Qt.Key.Key_Shift: KEY_VALUES.SHIFT.value,
    Qt.Key.Key_Alt: KEY_VALUES.ALT.value,
    Qt.Key.Key_Meta: KEY_VALUES.CMD.value,  # Win/Cmd
}

# Qt.Key
QT_KEY_MAP = {
    # 字母
    **{
        getattr(Qt.Key, f"Key_{char}"): char.lower()
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    },
    # F键
    **{getattr(Qt.Key, f"Key_F{i}"): f"f{i}" for i in range(1, 13)},
    # 其他
    Qt.Key.Key_Backspace: KEY_VALUES.BACKSPACE.value,
    Qt.Key.Key_Tab: KEY_VALUES.TAB.value,
    Qt.Key.Key_Enter: KEY_VALUES.ENTER.value,
    Qt.Key.Key_Return: KEY_VALUES.ENTER.value,
    Qt.Key.Key_Escape: KEY_VALUES.ESC.value,
    Qt.Key.Key_Space: KEY_VALUES.SPACE.value,
    Qt.Key.Key_Delete: KEY_VALUES.DELETE.value,
    Qt.Key.Key_Insert: KEY_VALUES.INSERT.value,
    Qt.Key.Key_Home: KEY_VALUES.HOME.value,
    Qt.Key.Key_End: KEY_VALUES.END.value,
    Qt.Key.Key_PageUp: KEY_VALUES.PAGE_UP.value,
    Qt.Key.Key_PageDown: KEY_VALUES.PAGE_DOWN.value,
    Qt.Key.Key_Up: KEY_VALUES.UP.value,
    Qt.Key.Key_Down: KEY_VALUES.DOWN.value,
    Qt.Key.Key_Left: KEY_VALUES.LEFT.value,
    Qt.Key.Key_Right: KEY_VALUES.RIGHT.value,
    Qt.Key.Key_Minus: KEY_VALUES.MINUS.value,
    Qt.Key.Key_Equal: KEY_VALUES.EQUAL.value,
    Qt.Key.Key_BracketLeft: KEY_VALUES.OPENING_BRACKET.value,
    Qt.Key.Key_BracketRight: KEY_VALUES.CLOSING_BRACKET.value,
    Qt.Key.Key_Backslash: KEY_VALUES.SLASH_BACK.value,
    Qt.Key.Key_Semicolon: KEY_VALUES.SEMICOLON.value,
    Qt.Key.Key_Apostrophe: KEY_VALUES.APOSTROPHE.value,
    Qt.Key.Key_Comma: KEY_VALUES.COMMA.value,
    Qt.Key.Key_Period: KEY_VALUES.PERIOD.value,
    Qt.Key.Key_Slash: KEY_VALUES.SLASH.value,
    # 特殊符号 即 组合符号 shift + 键，此时只保存非shift键的值
    Qt.Key.Key_Greater: KEY_VALUES.PERIOD.value,
    Qt.Key.Key_Less: KEY_VALUES.COMMA.value,
    Qt.Key.Key_Colon: KEY_VALUES.SEMICOLON.value,
    Qt.Key.Key_QuoteDbl: KEY_VALUES.APOSTROPHE.value,
    Qt.Key.Key_Bar: KEY_VALUES.SLASH_BACK.value,
    Qt.Key.Key_Underscore: KEY_VALUES.MINUS.value,
    Qt.Key.Key_Plus: KEY_VALUES.EQUAL.value,
    Qt.Key.Key_Question: KEY_VALUES.SLASH.value,
    Qt.Key.Key_Exclam: "1",
    Qt.Key.Key_At: "2",
    Qt.Key.Key_NumberSign: "3",
    Qt.Key.Key_Dollar: "4",
    Qt.Key.Key_Percent: "5",
    Qt.Key.Key_AsciiCircum: "6",
    Qt.Key.Key_Ampersand: "7",
    Qt.Key.Key_Asterisk: "8",
    Qt.Key.Key_ParenLeft: "9",
    Qt.Key.Key_ParenRight: "0",
}
