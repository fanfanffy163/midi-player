# 音符拟合
"""
核心想法是对比midi文件的音轨信息 与 键盘按键映射
整体升高或降低八度，直到找到最大正确率的方案
"""
import copy

from mido import MidiTrack

from .type import MIDI_NOTE_MAP


def NoteFitting(
    tracks: list[MidiTrack],
    note_to_key_mapping: dict[str, str],
    disableNoteFitting: bool,
) -> tuple[dict[str, str], float, int]:
    note_num: dict[int, int] = {}
    for track in tracks:
        for msg in track:
            if msg.type in ("note_on", "note_off"):
                note_num[msg.note] = note_num.get(msg.note, 0) + 1

    note_keys = set(note_num.keys())

    # 转化mapping为int
    mapped_note_to_keys_mapping: dict[int, str] = {
        MIDI_NOTE_MAP.get_midi_by_note(k): v for k, v in note_to_key_mapping.items()
    }
    mapped_note_keys = set(mapped_note_to_keys_mapping.keys())
    # 获取差异note
    diffent_note = note_keys.difference(mapped_note_keys)
    # 最完美的方案，不变
    if len(diffent_note) == 0:
        return note_to_key_mapping, 1.0, 0

    note_num_sum = 0
    for note, count in note_num.items():
        note_num_sum += count

    if disableNoteFitting:
        correct_count = 0
        for note, count in note_num.items():
            if note in mapped_note_to_keys_mapping:
                correct_count += count
        correct_precetage = correct_count / note_num_sum
        return note_to_key_mapping, correct_precetage, 0

    min_note = min(note_keys)
    max_note = max(note_keys)
    mapped_min_note = min(mapped_note_keys)
    mapped_max_note = max(mapped_note_keys)
    tmp_mapped_note_to_keys_mapping = copy.deepcopy(mapped_note_to_keys_mapping)

    # 首先将mapped_max_note 降到 min_note
    # 然后一路上升mapped_note，直到mapped_min_note 大于 max_note为止
    # 注意最小不能为0，最大不能超过127
    # 从中选一个正确性最高的方案

    # 降八度-1，升八度+1
    change_times = 0
    while mapped_max_note > min_note and mapped_max_note >= 0:
        change_times -= 1
        mapped_min_note -= 12
        mapped_max_note -= 12
        tmp_mapped_note_to_keys_mapping = {
            key - 12: value for key, value in tmp_mapped_note_to_keys_mapping.items()
        }

    finest_plan: int = 0
    finest_correct_precetage = -1.0
    while mapped_min_note < max_note and mapped_min_note <= 127:
        correct_count = 0
        for note, count in note_num.items():
            if note in tmp_mapped_note_to_keys_mapping:
                correct_count += count
        correct_precetage = correct_count / note_num_sum
        if correct_precetage >= 1:
            finest_plan = change_times
            finest_correct_precetage = 1
            break
        elif correct_precetage > finest_correct_precetage:
            finest_correct_precetage = correct_precetage
            finest_plan = change_times

        change_times += 1
        mapped_min_note += 12
        mapped_max_note += 12
        tmp_mapped_note_to_keys_mapping = {
            key + 12: value for key, value in tmp_mapped_note_to_keys_mapping.items()
        }

    # 改变映射
    octave_change = -finest_plan
    while finest_plan != 0:
        if finest_plan > 0:
            finest_plan -= 1
            mapped_note_to_keys_mapping = {
                key + 12: value for key, value in mapped_note_to_keys_mapping.items()
            }
        else:
            finest_plan += 1
            mapped_note_to_keys_mapping = {
                key - 12: value for key, value in mapped_note_to_keys_mapping.items()
            }
    note_to_key_mapping = {
        MIDI_NOTE_MAP.get_note_by_midi(key): value
        for key, value in mapped_note_to_keys_mapping.items()
        if key >= 0 and key <= 127
    }
    return note_to_key_mapping, finest_correct_precetage, octave_change
