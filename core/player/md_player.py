import threading
import queue
import time
from typing import List, Set  # 用于类型提示
from pynput.keyboard import Controller  

from ..player.type import MdPlaybackParam,MIDI_NOTE_MAP,KEY_MAP
from PyQt6 import QtCore
from enum import Enum
import json
import mido

class QMidiPlayer(QtCore.QObject):
    class PlayState(Enum):
        IDLE    = 1
        PLAYING = 2
        PAUSED  = 3

    signal_state = QtCore.pyqtSignal(PlayState)
    signal_play_position = QtCore.pyqtSignal(int)
    signal_play_duration = QtCore.pyqtSignal(int)
    signal_media_done = QtCore.pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        # config
        self.midi = None
        self.note_to_key = {}

        self.keyboard = Controller()
        self.task_queue = queue.Queue()
        self.events = []  # (绝对微秒, 事件类型, 音符)
        
        self.ticks_per_beat = None
        self.total_duration_us = 0
        self.total_events = 0

        # 播放状态
        self.state = QMidiPlayer.PlayState.IDLE  # 'idle', 'playing', 'paused'
        
        # 线程控制
        self.running = True
        self.lock = threading.Lock() 
        self.wake_up_event = threading.Event()
        self.position_update_event = threading.Event()
        self.scheduler_thread = None
        self.executor_thread = None
        self.position_update_thread = None

        # 播放时钟（虚拟时钟）
        self.current_playback_time_us = 0 
        self.last_real_time_ns = 0        
        self.playback_speed = 1.0         
        
        self.event_index = 0
        self.pressed_keys: Set[str] = set()

        #引入混合调度阈值
        
        # 自旋等待阈值（微秒）：当距下个事件小于此值，线程自旋以保证最高精度
        # 5000us = 5ms
        self.SPIN_WAIT_THRESHOLD_US = 5000 
        
        # 响应式轮询时间（毫秒）：当距下个事件较远时，以此间隔苏醒以检查UI响应
        # 5ms
        self.RESPONSIVE_LOOP_TIME_MS = 5

    def prepare(self, md_playback_param: MdPlaybackParam):
        self.stop()
        
        with self.lock:
            print("开始预处理MIDI...")
            try:
                with open(md_playback_param.note_to_key_path, 'r', encoding='utf-8') as f:
                    self.note_to_key = json.load(f)
            except Exception as e:
                print(f"解析音符转键盘配置发生错误：{e}")
                raise

            self.midi = mido.MidiFile(md_playback_param.midi_path)
            self.ticks_per_beat = self.midi.ticks_per_beat
            
            raw_events = [] # (tick, type, note)
            tempo_events = [] # (tick, tempo)
            
            # 初始 tempo
            initial_tempo = 500000

            for track in self.midi.tracks:
                current_tick = 0
                for msg in track:
                    current_tick += msg.time

                    if msg.type in ('note_on', 'note_off'):
                        event_type = 'note_off' if (msg.type == 'note_on' and msg.velocity == 0) else msg.type
                        raw_events.append((current_tick, event_type, msg.note))
                    elif msg.type == 'set_tempo':
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
                while (tempo_event_index < len(tempo_events) and 
                    tempo_events[tempo_event_index][0] <= event_tick):
                    
                    tempo_tick, new_tempo = tempo_events[tempo_event_index]
                    ticks_since_last = tempo_tick - last_event_tick
                    micros_since_last = (ticks_since_last * current_tempo) // self.ticks_per_beat
                    last_event_micro += micros_since_last
                    
                    current_tempo = new_tempo
                    last_event_tick = tempo_tick
                    tempo_event_index += 1

                ticks_since_last = event_tick - last_event_tick
                micros_since_last = (ticks_since_last * current_tempo) // self.ticks_per_beat
                current_event_micro = last_event_micro + micros_since_last

                final_events_with_micros.append((current_event_micro, event_type, note))
                
                last_event_tick = event_tick
                last_event_micro = current_event_micro

            self.events = final_events_with_micros
            self.total_events = len(self.events)
            if self.total_events > 0:
                self.total_duration_us = self.events[-1][0] # 最后一个事件的时间戳

            print(f"预处理完毕，总事件数: {self.total_events}，总时长: {self.total_duration_us / 1000:.2f} ms")
            self.signal_play_duration.emit(self.total_duration_us // 1000)


    def _get_keys(self, note: int) -> List[str]:
        # (与上一版相同)
        if not self.note_to_key: return []
        notestr = MIDI_NOTE_MAP.get_note_by_midi(note)
        if notestr is None: return []
        if notestr not in self.note_to_key: return []
        value = self.note_to_key[notestr]
        if isinstance(value, str): return [value]
        elif isinstance(value, list): return [k for k in value if isinstance(k, str)]
        else: return []

    def _position_update_thread(self):
        while self.running:
            self.position_update_event.clear()
            with self.lock:
                tmp_state = self.state
            if tmp_state == QMidiPlayer.PlayState.PLAYING:
                # 1s回告一次
                time.sleep(1)
                self.signal_play_position.emit(int(self.current_playback_time_us // 1000))
            else:
                self.position_update_event.wait(None)
        print("position_update 线程退出")
    
    #执行线程增加按键状态跟踪
    def _executor_thread(self):
        """执行线程：执行按键操作，并跟踪按键状态"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=0.1)
                event_type, key_str = task

                key_to_press = KEY_MAP.get(key_str, key_str)
                
                if event_type == 'note_on':
                    self.keyboard.press(key_to_press)
                    # 使用锁保护 self.pressed_keys
                    with self.lock:
                        self.pressed_keys.add(key_str)
                    # print(f"按下键: {key_to_press}") # 调试时开启
                else:
                    self.keyboard.release(key_to_press)
                    with self.lock:
                        self.pressed_keys.discard(key_str)
                    # print(f"释放键: {key_to_press}") # 调试时开启
                
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"按键执行出错: {e}")
                self.task_queue.task_done()
        
        # 线程退出前，释放所有按键，防止卡键
        print("执行线程退出，释放所有按键...")
        for key_str in list(self.pressed_keys):
            key_to_release = KEY_MAP.get(key_str, key_str)
            self.keyboard.release(key_to_release)


    ### 核心优化：高精度混合调度器 ###
    def _scheduler_thread(self):
        """调度线程：基于状态机的混合精度时钟"""
        
        while self.running:
            # 清除唤醒标志
            self.wake_up_event.clear()
            
            spin_wait = False             # 是否进入自旋模式
            target_real_time_ns = 0       # 自旋模式的目标时间
            wait_timeout_sec = None       # 响应模式的等待时间 (None=无限)

            with self.lock:
                # --- 状态检查与时钟推进 ---
                if self.state == QMidiPlayer.PlayState.PLAYING:
                    current_real_time_ns = time.time_ns()
                    
                    # 仅当 last_real_time_ns > 0 (非暂停后刚恢复) 才推进时钟
                    if self.last_real_time_ns > 0:
                        real_time_delta_ns = current_real_time_ns - self.last_real_time_ns
                        virtual_time_delta_us = (real_time_delta_ns // 1000) * self.playback_speed
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
                            for key in keys:
                                self.task_queue.put((event_type, key))
                            self.event_index += 1
                        else:
                            # 此事件在未来，停止检查
                            break
                    
                    # --- 计算下一次等待策略 ---
                    if self.event_index >= self.total_events:
                        # 播放完毕
                        print("播放完毕。")
                        self.state = QMidiPlayer.PlayState.IDLE
                        self.signal_state.emit(self.state)
                        self.signal_media_done.emit(True)
                        self.current_playback_time_us = 0
                        self.event_index = 0
                        self.last_real_time_ns = 0 # 重置时钟锚
                        wait_timeout_sec = None # 进入无限等待
                    else:
                        # 计算到下一个事件的“真实”微秒
                        next_event_time_us = self.events[self.event_index][0]
                        wait_micros = (next_event_time_us - self.current_playback_time_us) / self.playback_speed
                        
                        if wait_micros <= 1: # (<= 1us 视为立即执行)
                            # 已经迟了或即将到时，不睡眠，立即循环
                            wait_timeout_sec = 0
                        
                        elif wait_micros <= self.SPIN_WAIT_THRESHOLD_US:
                            # 【精度模式】
                            # 时间极短，准备自旋
                            spin_wait = True
                            target_real_time_ns = current_real_time_ns + int(wait_micros * 1000)
                            # (此时 wait_timeout_sec 保持 None，因为我们将不使用 wake_up_event.wait)
                        
                        else:
                            # 【响应模式】
                            # 时间较长，计算一个安全的、可响应的睡眠时间
                            responsive_wait_us = self.RESPONSIVE_LOOP_TIME_MS * 1000
                            
                            # 睡眠时间 = min(到下个音符的时间, 5ms的响应时间)
                            sleep_micros = min(wait_micros, responsive_wait_us)
                            wait_timeout_sec = sleep_micros / 1_000_000

                elif self.state == QMidiPlayer.PlayState.PAUSED or self.state == QMidiPlayer.PlayState.IDLE:
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
        
        print("调度线程已退出。")

    def start_player(self):
        """启动后台线程。"""
        if self.scheduler_thread:
            print("线程已在运行。")
            return
            
        print("启动播放器线程...")
        self.running = True
        
        # 启动执行线程
        self.executor_thread = threading.Thread(target=self._executor_thread)
        self.executor_thread.start()

        # 启动调度线程
        self.scheduler_thread = threading.Thread(target=self._scheduler_thread)
        self.scheduler_thread.start()

        # 启动播放位置上报线程
        self.position_update_thread = threading.Thread(target=self._position_update_thread)
        self.position_update_thread.start()

    def stop(self):       
        with self.lock:
            if self.state == QMidiPlayer.PlayState.IDLE:
                print("已停止播放")
                return

            print("正在停止播放...")
            self.state = QMidiPlayer.PlayState.IDLE
            self.signal_state.emit(self.state)
            #清空任务队列（防止旧的按键事件执行）
            while not self.task_queue.empty():
                try: self.task_queue.get_nowait()
                except queue.Empty: break
                self.task_queue.task_done()

            # 3. 释放所有当前按下的键
            keys_to_release = list(self.pressed_keys)
            for key_str in keys_to_release:
                self.task_queue.put(('note_off', key_str))
                
            self.event_index = 0
            self.current_playback_time_us = 0
            self.last_real_time_ns = 0
        
        self.wake_up_event.set() # 唤醒调度器
    
    def stop_player(self):
        self.stop()
        if not self.running:
            return
        self.running = False
        self.wake_up_event.set() # 唤醒调度器
        self.position_update_event.set()

        if self.scheduler_thread:
            self.scheduler_thread.join()
        if self.executor_thread:
            self.executor_thread.join()
        if self.position_update_thread:
            self.position_update_thread.join()
            
        self.scheduler_thread = None
        self.executor_thread = None
        self.position_update_thread = None
        print("播放器线程已停止")

    def play(self):
        """开始或恢复播放。"""
        if not self.scheduler_thread:
            print("线程未启动，请先调用 start_player()")
            return
        
        if not self.midi:
            print("未加载midi，请先调用 prepare(...)")
            return
            
        with self.lock:
            if self.state == QMidiPlayer.PlayState.PLAYING:
                return # 已经在播放
            
            print("开始播放...")
            self.state = QMidiPlayer.PlayState.PLAYING
            self.signal_state.emit(self.state)
            # 重置真实时钟，防止因暂停导致的时间跳跃
            self.last_real_time_ns = time.time_ns()
            
            # 如果是从头开始
            if self.event_index == 0:
                 self.current_playback_time_us = 0
        
        # 唤醒调度器线程
        self.wake_up_event.set()
        self.position_update_event.set()

    def pause(self):
        """暂停播放。"""
        with self.lock:
            if self.state != QMidiPlayer.PlayState.PLAYING:
                return
            print("暂停播放。")
            self.state = QMidiPlayer.PlayState.PAUSED
            self.signal_state.emit(self.state)
        
        # 唤醒调度器，让它进入 'paused' 的等待状态
        self.wake_up_event.set()

    def seek(self, time_ms: int):
        """跳转到指定毫秒。"""
        time_us = time_ms * 1000
        if time_us < 0: time_us = 0
        if time_us > self.total_duration_us: 
            time_us = self.total_duration_us

        print(f"跳转到 {time_ms} ms...")
        
        with self.lock:
            # 1. 暂停调度器
            was_playing = (self.state == QMidiPlayer.PlayState.PLAYING)
            self.state = QMidiPlayer.PlayState.PAUSED
            self.signal_state.emit(self.state)

            # 2. 清空任务队列（防止旧的按键事件执行）
            while not self.task_queue.empty():
                try: self.task_queue.get_nowait()
                except queue.Empty: break
                self.task_queue.task_done()
                
            # 3. 释放所有当前按下的键
            keys_to_release = list(self.pressed_keys)
            for key_str in keys_to_release:
                self.task_queue.put(('note_off', key_str))
            # 注意：此时 self.pressed_keys 集合会在执行线程中被清空
            
            # 4. 更新时钟和索引
            self.current_playback_time_us = time_us
            self.event_index = self._find_event_index_for_time(time_us)
            
            # 5. [重要] 重建按键状态
            #    一个完美的 seek 会重新计算在 time_us 时刻哪些音符应该被按下
            #    这里我们做一个简化版：在跳转点之后，音符只有在 'note_on' 时才会按下
            #    （一个更复杂的实现会遍历 0 到 time_us 的所有事件来重建状态）

            # 6. 如果之前在播放，则恢复播放
            if was_playing:
                self.state = QMidiPlayer.PlayState.PLAYING
                self.signal_state.emit(self.state)
                self.last_real_time_ns = time.time_ns()
        
        # 唤醒调度器
        self.wake_up_event.set()

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
        if speed <= 0: speed = 0.1 # 防止负数或0
        
        with self.lock:
            print(f"播放速度设置为: {speed}x")
            self.playback_speed = speed
        # 无需唤醒线程，它会在下一次循环自动使用新速度

    def get_playback_info(self) -> dict:
        """获取当前播放信息（用于时间条）。"""
        with self.lock:
            return {
                'current_time_ms': self.current_playback_time_us // 1000,
                'total_time_ms': self.total_duration_us // 1000,
                'state': self.state,
                'speed': self.playback_speed
            }
        
    def duration(self) -> int:
        with self.lock:
            return self.total_duration_us // 1000
        
    def playbackState(self) -> PlayState:
        with self.lock:
            return self.state
