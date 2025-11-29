# 音符拟合 - 修正版 (支持黑键 & 原调优先)

from mido import MidiTrack

from midiplayer.core.player.type import MIDI_NOTE_MAP


def NoteFitting(
    tracks: list[MidiTrack],
    note_to_key_mapping: dict[str, str],
    disableNoteFitting: bool,
) -> tuple[dict[str, str], float, int]:

    # --- 1. 数据预处理 ---
    note_counts: dict[int, int] = {}
    total_notes = 0
    for track in tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                note_counts[msg.note] = note_counts.get(msg.note, 0) + 1
                total_notes += 1

    if total_notes == 0:
        return note_to_key_mapping, 1.0, 0

    # 解析键盘映射
    # 这里会自动识别你是否给了黑键。如果你给了，valid_pitch_classes 就会包含对应数字
    mapped_midi_to_key: dict[int, str] = {
        MIDI_NOTE_MAP.get_midi_by_note(k): v for k, v in note_to_key_mapping.items()
    }
    available_midis = sorted(mapped_midi_to_key.keys())

    if not available_midis:
        return note_to_key_mapping, 0.0, 0

    valid_pitch_classes = set(m % 12 for m in available_midis)
    min_key_midi = available_midis[0]
    max_key_midi = available_midis[-1]
    keyboard_center = (min_key_midi + max_key_midi) / 2

    # 如果禁用了拟合，直接计算
    if disableNoteFitting:
        hits = sum(count for n, count in note_counts.items() if n in mapped_midi_to_key)
        return note_to_key_mapping, hits / total_notes, 0

    # ==========================================================
    # 核心算法 Start
    # ==========================================================

    # --- Step 1: 最佳半音移调 (原调优先 & 加权评分策略) ---

    def calculate_pitch_class_hit_rate(shift_amount):
        """计算在这个移调量下，音名(Do Re Mi...)命中了多少"""
        current_hits = 0
        for note, count in note_counts.items():
            # 检查移调后的音名是否在键盘支持的列表里
            if (note + shift_amount) % 12 in valid_pitch_classes:
                current_hits += count
        return current_hits / total_notes

    # 1. 满意度阈值：如果原调命中率超过此值，直接停止搜索
    SATISFACTION_THRESHOLD = 0.88
    # 2. 移调惩罚系数：每移动 1 个半音，扣除多少“分数” (0.015 代表 1.5%)
    # 意味着：如果移动 1 个半音只能提升 1% 的命中率，那就不移（因为扣分比得分多）
    SHIFT_PENALTY = 0.015

    # 1. 先计算“原调” (Shift=0) 的情况
    best_semitone_shift = 0
    base_hit_rate = calculate_pitch_class_hit_rate(0)

    # 初始最佳得分就是原调的命中率（因为 shift=0，惩罚为0）
    best_score = base_hit_rate

    # 2. 只有当原调命中率未达到“满意阈值”时，才去搜索其他移调
    if base_hit_rate < SATISFACTION_THRESHOLD:
        # 搜索范围：-6 到 +6
        for shift in range(-6, 7):
            if shift == 0:
                continue

            rate = calculate_pitch_class_hit_rate(shift)

            # 【核心优化算法】
            # 得分 = 命中率 - (移调距离 * 惩罚系数)
            # 距离越远，惩罚越大。只有命中率提升足以抵消距离惩罚时，才认为此方案更好。
            score = rate - (abs(shift) * SHIFT_PENALTY)

            if score > best_score:
                best_score = score
                best_semitone_shift = shift

    # --- Step 2: 全局重心对齐 (Global Center Alignment) ---
    # 计算移调后，所有音符的加权平均音高
    weighted_sum_pitch = sum(
        (n + best_semitone_shift) * c for n, c in note_counts.items()
    )
    avg_pitch = weighted_sum_pitch / total_notes

    # 计算平均音高和键盘中心的距离
    diff = keyboard_center - avg_pitch
    global_octave_shift = round(diff / 12) * 12

    # 【防抖动优化】
    # 如果不做八度平移，大部分音符其实也能放下，那就别平移了
    # 避免本来好好的 C3-C5 曲子被强行移到 C4-C6 (虽然也是对的，但没必要)
    # 我们可以计算一下 "Global Shift = 0" 时的落点率

    # 简单的判据：如果 global_octave_shift 不为0，我们检查一下如果不移八度，是否大部分音符会出界？
    if global_octave_shift != 0:
        notes_in_range_without_shift = 0
        notes_in_range_with_shift = 0

        for n, c in note_counts.items():
            p = n + best_semitone_shift
            if min_key_midi <= p <= max_key_midi:
                notes_in_range_without_shift += c
            if min_key_midi <= (p + global_octave_shift) <= max_key_midi:
                notes_in_range_with_shift += c

        # 只有当“移了八度”比“不移八度”能让更多音符直接落在范围内时，才应用八度平移
        # 否则归零
        if notes_in_range_without_shift >= notes_in_range_with_shift:
            global_octave_shift = 0

    # 最终的基础偏移
    base_shift = best_semitone_shift + global_octave_shift

    # --- Step 3: 构建最终映射 (Smart Folding & Snapping) ---
    new_note_to_key_mapping: dict[str, str] = {}
    final_hits = 0

    for original_note, count in note_counts.items():
        # 1. 应用基础偏移
        target_pitch = original_note + base_shift

        is_correct = True

        # 2. 智能折叠 (Smart Folding)
        while target_pitch > max_key_midi:
            target_pitch -= 12
            is_correct = False
        while target_pitch < min_key_midi:
            target_pitch += 12
            is_correct = False

        # 3. 就近吸附 (Snap)
        if target_pitch not in mapped_midi_to_key:
            is_correct = False
            nearest_pitch = min(available_midis, key=lambda x: abs(x - target_pitch))
            if abs(nearest_pitch - target_pitch) > 2:  # 超过全音就不吸附了，太难听
                continue
            target_pitch = nearest_pitch

        # 4. 生成映射
        original_note_name = MIDI_NOTE_MAP.get_note_by_midi(original_note)
        target_key_char = mapped_midi_to_key[target_pitch]
        new_note_to_key_mapping[original_note_name] = target_key_char

        if is_correct:
            final_hits += count

    final_accuracy = final_hits / total_notes

    return new_note_to_key_mapping, final_accuracy, base_shift
