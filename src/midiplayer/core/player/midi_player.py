import queue
import threading
import time
from enum import Enum
from typing import List, Set  # 用于类型提示

import mido
import pydirectinput
from loguru import logger
from PySide6 import QtCore

from ..utils.config import cfg
from .note_fitting import NoteFitting
from .type import CONTROL_KEY_MAP, KEY_MAP, MIDI_NOTE_MAP, MdPlaybackParam


class QMidiPlayer(QtCore.QObject):
    class PlayState(Enum):
        IDLE = 1
        PLAYING = 2
        PAUSED = 3

    signal_state = QtCore.Signal(PlayState)
    signal_play_position = QtCore.Signal(int)
    signal_play_duration = QtCore.Signal(int)
    signal_media_done = QtCore.Signal(bool)
    signal_correct_info_changed = QtCore.Signal(float, int)

    def __init__(self):
        super().__init__()

        # config
        self.midi = None
        self.music_track_index = None
        self.control_track_index = None
        self.note_to_key = {}

        self.task_queue = queue.Queue()
        self.events = []  # (绝对微秒, 事件类型, 音符)

        self.ticks_per_beat = None
        self.total_duration_us = 0
        self.total_events = 0

        # 播放状态
        self.state = QMidiPlayer.PlayState.IDLE  # 'idle', 'playing', 'paused'
        # 用于延时
        self.start_flag = False

        # 线程控制
        self.running = True
        # 锁1：保护时钟和调度
        self.clock_lock = threading.Lock()
        # 锁2：保护按键状态
        self.keys_lock = threading.Lock()
        self.wake_up_event = threading.Event()
        self.play_delay_event = threading.Event()
        self.scheduler_thread = None
        self.executor_thread = None

        # 播放时钟（虚拟时钟）
        self.current_playback_time_us = 0
        self.last_real_time_ns = 0
        self.playback_speed = 1.0

        self.event_index = 0
        self.pressed_keys: Set[str] = set()

        # 引入混合调度阈值

        # 自旋等待阈值（纳秒）：当距下个事件小于此值，线程自旋以保证最高精度
        self.SPIN_WAIT_THRESHOLD_NS = 5000

        # 响应式轮询时间（纳秒）：当距下个事件较远时，以此间隔苏醒以检查UI响应
        self.RESPONSIVE_LOOP_TIME_NS = 5000

        self.position_timer = QtCore.QTimer(self)
        self.position_timer.setInterval(1000)  # 1000ms = 1s
        self.position_timer.timeout.connect(self._on_position_update)

    def _on_position_update(self):
        # 这里的锁粒度非常小，很安全
        with self.clock_lock:
            pos_ms = int(self.current_playback_time_us // 1000)
        self.signal_play_position.emit(pos_ms)

    def _split_control_and_music_track(self):
        """
        分离控制和实际演奏音符的index
        """
        music_track_index = []
        control_track_index = []

        for i, track in enumerate(self.midi.tracks):
            control_track = True
            for msg in track:
                if msg.type == "note_on" or msg.type == "note_off":
                    control_track = False
                    break

            if control_track:
                control_track_index.append(i)
            else:
                music_track_index.append(i)

        self.music_track_index = music_track_index
        self.control_track_index = control_track_index

    def get_all_tracks(self):
        track_info = []
        with self.clock_lock:
            if self.midi:
                for i, track_idx in enumerate(self.music_track_index):
                    track = self.midi.tracks[track_idx]
                    track_info.append({"index": i, "name": track.name})
        return track_info

    def prepare(self, md_playback_param: MdPlaybackParam):
        self.stop()

        with self.clock_lock:
            self.note_to_key = md_playback_param.note_to_key_mapping

            self.midi = mido.MidiFile(md_playback_param.midi_path)
            self._split_control_and_music_track()
            self.ticks_per_beat = self.midi.ticks_per_beat

            raw_events = []  # (tick, type, note)
            tempo_events = []  # (tick, tempo)

            # 初始 tempo
            initial_tempo = 500000

            tracks = (
                [self.midi.tracks[t] for t in self.control_track_index]
                + [
                    self.midi.tracks[self.music_track_index[t]]
                    for t in md_playback_param.active_tracks
                ]
                if md_playback_param.active_tracks is not None
                else self.midi.tracks
            )
            self.note_to_key, correct_radio_1base, octave_change = NoteFitting(
                tracks, self.note_to_key, cfg.get(cfg.player_play_disable_note_fitting)
            )
            for track in tracks:
                current_tick = 0
                for msg in track:
                    current_tick += msg.time

                    if msg.type in ("note_on", "note_off"):
                        event_type = (
                            "note_off"
                            if (msg.type == "note_on" and msg.velocity == 0)
                            else msg.type
                        )
                        raw_events.append((current_tick, event_type, msg.note))
                    elif msg.type == "set_tempo":
                        tempo_events.append((current_tick, msg.tempo))

            tempo_events.sort(key=lambda x: x[0])
            raw_events.sort(key=lambda x: x[0])

            # --- 精确计算所有事件的绝对微秒时间 ---
            final_events_with_micros = []
            current_tempo = initial_tempo
            last_event_tick = 0
            last_event_micro = 0
            tempo_event_index = 0

            for event_tick, event_type, note in raw_events:
                while (
                    tempo_event_index < len(tempo_events)
                    and tempo_events[tempo_event_index][0] <= event_tick
                ):

                    tempo_tick, new_tempo = tempo_events[tempo_event_index]
                    ticks_since_last = tempo_tick - last_event_tick
                    micros_since_last = (
                        ticks_since_last * current_tempo
                    ) // self.ticks_per_beat
                    last_event_micro += micros_since_last

                    current_tempo = new_tempo
                    last_event_tick = tempo_tick
                    tempo_event_index += 1

                ticks_since_last = event_tick - last_event_tick
                micros_since_last = (
                    ticks_since_last * current_tempo
                ) // self.ticks_per_beat
                current_event_micro = last_event_micro + micros_since_last

                final_events_with_micros.append((current_event_micro, event_type, note))

                last_event_tick = event_tick
                last_event_micro = current_event_micro

            self.events = final_events_with_micros
            self.total_events = len(self.events)
            self.total_duration_us = self.midi.length * 1_000_000

            logger.debug(
                f"预处理完毕，总事件数: {self.total_events}，总时长: {self.total_duration_us / 1000:.2f} ms"
            )
            self.signal_play_duration.emit(self.total_duration_us // 1000)
            self.signal_correct_info_changed.emit(correct_radio_1base, octave_change)

    def _get_keys(self, note: int) -> List[str]:
        # (与上一版相同)
        if not self.note_to_key:
            return []
        notestr = MIDI_NOTE_MAP.get_note_by_midi(note)
        if notestr is None:
            return []
        if notestr not in self.note_to_key:
            return []
        value = self.note_to_key[notestr]
        if isinstance(value, str):
            return [value]
        elif isinstance(value, list):
            return [k for k in value if isinstance(k, str)]
        else:
            return []

    # 执行线程增加按键状态跟踪
    def _executor_thread(self):
        """执行线程：执行按键操作，并跟踪按键状态"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=0.1)
                event_type, keys = task
                key_press_and_up = cfg.get(cfg.player_play_key_press_and_up)

                if event_type == "note_on":
                    control_keys = [k for k in keys if k in CONTROL_KEY_MAP]
                    normal_keys = [k for k in keys if k not in CONTROL_KEY_MAP]
                    # 先按控制键

                    for c_k in control_keys:
                        pydirectinput.keyDown(c_k)
                    for key_to_press in normal_keys:
                        pydirectinput.keyDown(key_to_press)
                    for c_k in reversed(control_keys):
                        pydirectinput.keyUp(c_k)

                    if key_press_and_up:
                        for key_to_press in reversed(normal_keys):
                            pydirectinput.keyUp(key_to_press)
                    else:
                        # 使用锁保护 self.pressed_keys
                        with self.keys_lock:
                            self.pressed_keys.update(normal_keys)
                else:
                    normal_keys = [k for k in keys if k not in CONTROL_KEY_MAP]
                    for key_to_release in normal_keys:
                        with self.keys_lock:
                            (
                                pydirectinput.keyUp(key_to_release)
                                if key_to_release in self.pressed_keys
                                else None
                            )
                            self.pressed_keys.discard(key_to_release)
                    # logger.debug(f"释放键: {key_to_press}") # 调试时开启

                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"按键执行出错: {e}")
                self.task_queue.task_done()

        # 线程退出前，释放所有按键，防止卡键
        logger.debug("执行线程退出，释放所有按键...")
        for key_str in list(self.pressed_keys):
            key_to_release = KEY_MAP.get(key_str, key_str)
            pydirectinput.keyUp(key_to_release)

    ### 核心优化：高精度混合调度器 ###
    def _scheduler_thread(self):
        """调度线程：基于状态机的混合精度时钟"""

        while self.running:
            # 清除唤醒标志
            self.wake_up_event.clear()

            tmp_start_flag = False
            with self.clock_lock:
                tmp_start_flag = self.start_flag
            if tmp_start_flag:
                self.play_delay_event.clear()
                self.play_delay_event.wait(timeout=cfg.get(cfg.player_play_delay_time))
                with self.clock_lock:
                    self.start_flag = False
                    self.last_real_time_ns = 0

            spin_wait = False  # 是否进入自旋模式
            target_real_time_ns = 0  # 自旋模式的目标时间
            wait_timeout_sec = None  # 响应模式的等待时间 (None=无限)

            with self.clock_lock:
                # --- 状态检查与时钟推进 ---
                if self.state == QMidiPlayer.PlayState.PLAYING:
                    current_real_time_ns = time.time_ns()

                    # 仅当 last_real_time_ns > 0 (非暂停后刚恢复) 才推进时钟
                    if self.last_real_time_ns > 0:
                        real_time_delta_ns = (
                            current_real_time_ns - self.last_real_time_ns
                        )
                        virtual_time_delta_us = (
                            real_time_delta_ns // 1000
                        ) * self.playback_speed
                        self.current_playback_time_us += virtual_time_delta_us

                    # 锚定当前真实时间
                    self.last_real_time_ns = current_real_time_ns

                    # --- 事件派发 ---
                    while self.event_index < self.total_events:
                        event_time_us = self.events[self.event_index][0]

                        if event_time_us <= self.current_playback_time_us:
                            # 时间到，推入队列
                            _, event_type, note = self.events[self.event_index]
                            keys = self._get_keys(note)
                            self.task_queue.put((event_type, keys))
                            self.event_index += 1
                        else:
                            # 此事件在未来，停止检查
                            break

                    # --- 计算下一次等待策略 ---
                    if (
                        self.event_index >= self.total_events
                        and self.current_playback_time_us > self.total_duration_us
                    ):
                        # 播放完毕
                        logger.debug("播放完毕。")
                        self.state = QMidiPlayer.PlayState.IDLE
                        self.signal_state.emit(self.state)
                        self.signal_media_done.emit(True)
                        self.current_playback_time_us = 0
                        self.event_index = 0
                        self.last_real_time_ns = 0  # 重置时钟锚
                        wait_timeout_sec = None  # 进入无限等待
                    else:
                        # 计算到下一个事件的“真实”微秒
                        if self.event_index < self.total_events:
                            next_event_time_us = self.events[self.event_index][0]
                            wait_micros = (
                                next_event_time_us - self.current_playback_time_us
                            ) / self.playback_speed
                        else:
                            # 此时在静默播放，已经没有任务了. 让他不要自旋就行
                            wait_micros = max(
                                self.RESPONSIVE_LOOP_TIME_NS,
                                self.SPIN_WAIT_THRESHOLD_NS + 1,
                            )

                        if wait_micros <= 1:  # (<= 1us 视为立即执行)
                            # 已经迟了或即将到时，不睡眠，立即循环
                            wait_timeout_sec = 0

                        elif wait_micros <= self.SPIN_WAIT_THRESHOLD_NS:
                            # 【精度模式】
                            # 时间极短，准备自旋
                            spin_wait = True
                            target_real_time_ns = current_real_time_ns + int(
                                wait_micros * 1000
                            )
                            # (此时 wait_timeout_sec 保持 None，因为我们将不使用 wake_up_event.wait)

                        else:
                            # 【响应模式】
                            # 时间较长，计算一个安全的、可响应的睡眠时间
                            responsive_wait_us = self.RESPONSIVE_LOOP_TIME_NS * 1000

                            # 睡眠时间 = min(到下个音符的时间, 5ms的响应时间)
                            sleep_micros = min(wait_micros, responsive_wait_us)
                            wait_timeout_sec = sleep_micros / 1_000_000

                elif (
                    self.state == QMidiPlayer.PlayState.PAUSED
                    or self.state == QMidiPlayer.PlayState.IDLE
                ):
                    # 暂停或空闲时，重置时钟锚，无限期等待
                    self.last_real_time_ns = 0
                    wait_timeout_sec = None

            # --- 锁已释放 ---

            # --- 执行等待策略 ---
            if spin_wait:
                # 【精度模式】
                # 忙碌-等待（自旋），不响应UI
                # 这是你要求的 "忽略响应ui"
                while time.time_ns() < target_real_time_ns:
                    pass
                # 自旋结束后，将立即进入下一轮循环，获取锁并派发事件

            else:
                # 【响应模式】
                # 带超时的等待
                # 1. state='playing': 等待 wait_timeout_sec (例如 0ms 或 5ms)
                # 2. state='paused'/'idle': 等待 None (无限期)
                # 3. 任何 `wake_up_event.set()` 都会立即唤醒它
                self.wake_up_event.wait(timeout=wait_timeout_sec)

        logger.debug("调度线程已退出。")

    def start_player(self):
        """启动后台线程。"""
        if self.scheduler_thread:
            logger.debug("线程已在运行。")
            return

        logger.debug("启动播放器线程...")
        self.running = True

        # 启动执行线程
        self.executor_thread = threading.Thread(target=self._executor_thread)
        self.executor_thread.start()

        # 启动调度线程
        self.scheduler_thread = threading.Thread(target=self._scheduler_thread)
        self.scheduler_thread.start()

    def stop_player(self):
        with self.clock_lock:
            self.running = False
            self.state = QMidiPlayer.PlayState.IDLE

        self.wake_up_event.set()  # 唤醒调度器，让它看到 self.running=False 并退出
        self.play_delay_event.set()

        self.position_timer.stop()
        if self.scheduler_thread:
            self.scheduler_thread.join()
        if self.executor_thread:
            self.executor_thread.join()

        self.scheduler_thread = None
        self.executor_thread = None
        logger.debug("播放器线程已停止")

    def play(self):
        """开始或恢复播放。"""
        if not self.scheduler_thread:
            logger.debug("线程未启动，请先调用 start_player()")
            return

        if not self.midi:
            logger.debug("未加载midi，请先调用 prepare(...)")
            return

        with self.clock_lock:
            last_state = self.state
            if last_state == QMidiPlayer.PlayState.PLAYING:
                return  # 已经在播放

            logger.debug("开始播放...")
            self.state = QMidiPlayer.PlayState.PLAYING
            self.signal_state.emit(self.state)
            self.last_real_time_ns = 0

            # 如果是从头开始
            if last_state == QMidiPlayer.PlayState.IDLE:
                self.current_playback_time_us = 0
                logger.debug("从头播放")
                self.start_flag = True

        self.position_timer.start()
        # 唤醒调度器线程
        self.wake_up_event.set()

    def pause(self):
        """暂停播放。"""
        with self.clock_lock:
            if self.state != QMidiPlayer.PlayState.PLAYING:
                return
            logger.debug("暂停播放。")
            self.state = QMidiPlayer.PlayState.PAUSED
            self.signal_state.emit(self.state)

        # 释放队列按键以及按下的按键
        self._release_keyup_all_task_and_pressed_keys()

        # 唤醒调度器，让它进入 'paused' 的等待状态
        self.position_timer.stop()
        self.wake_up_event.set()

    def stop(self):
        # 1. 先锁时钟，改变状态
        with self.clock_lock:
            if self.state == QMidiPlayer.PlayState.IDLE:
                return
            logger.debug("正在停止播放...")
            self.state = QMidiPlayer.PlayState.IDLE
            self.signal_state.emit(self.state)
            self.event_index = 0
            self.current_playback_time_us = 0
            self.last_real_time_ns = 0

        # 2. 释放队列按键以及按下的按键
        self._release_keyup_all_task_and_pressed_keys()

        self.signal_play_position.emit(0)
        self.position_timer.stop()
        self.wake_up_event.set()  # 唤醒调度器

    def seek(self, time_ms: int):
        """跳转到指定毫秒。"""
        time_us = time_ms * 1000
        if time_us < 0:
            time_us = 0
        if time_us > self.total_duration_us:
            time_us = self.total_duration_us

        logger.debug(f"跳转到 {time_ms} ms...")

        with self.clock_lock:
            # 1. 暂停调度器
            was_playing = self.state == QMidiPlayer.PlayState.PLAYING
            self.state = QMidiPlayer.PlayState.PAUSED
            self.signal_state.emit(self.state)
            self.current_playback_time_us = time_us
            self.event_index = self._find_event_index_for_time(time_us)

        # 2. 释放队列按键以及按下的按键
        self._release_keyup_all_task_and_pressed_keys()

        # 3. 如果之前在播放，则恢复播放
        if was_playing:
            with self.clock_lock:
                self.state = QMidiPlayer.PlayState.PLAYING
                self.signal_state.emit(self.state)
                self.last_real_time_ns = time.time_ns()

        # 唤醒调度器
        self.wake_up_event.set()

    def _release_keyup_all_task_and_pressed_keys(self):
        # 清空队列 (在锁外)
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
            self.task_queue.task_done()

        # 锁按键状态，准备释放
        with self.keys_lock:
            keys_to_release = list(self.pressed_keys)
            # 注意：这里不清空pressed_keys，让executor来清

        # 提交释放任务 (在锁外)
        for key_str in keys_to_release:
            self.task_queue.put(("note_off", [key_str]))  # 修复：传列表

    def _find_event_index_for_time(self, time_us: int) -> int:
        """(辅助函数) 使用二分查找快速定位时间戳"""
        # 查找第一个时间戳 >= time_us 的事件
        l, r = 0, self.total_events - 1
        target_index = self.total_events

        while l <= r:
            mid = (l + r) // 2
            if self.events[mid][0] >= time_us:
                target_index = mid
                r = mid - 1
            else:
                l = mid + 1
        return target_index

    def set_speed(self, speed: float):
        """设置播放速度（例如 1.0, 1.5, 0.5）。"""
        if speed <= 0:
            speed = 0.1  # 防止负数或0

        with self.clock_lock:
            logger.debug(f"播放速度设置为: {speed}x")
            self.playback_speed = speed
        # 无需唤醒线程，它会在下一次循环自动使用新速度

    def get_playback_info(self) -> dict:
        """获取当前播放信息（用于时间条）。"""
        with self.clock_lock:
            return {
                "current_time_ms": self.current_playback_time_us // 1000,
                "total_time_ms": self.total_duration_us // 1000,
                "state": self.state,
                "speed": self.playback_speed,
            }

    def get_playback_state(self) -> PlayState:
        with self.clock_lock:
            return self.state
