import mido
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout
)
from PyQt6.QtCore import (
    Qt, 
    QObject, 
    pyqtSignal, 
    QRunnable, 
    QThreadPool, 
    pyqtSlot
)
from qfluentwidgets import (
    CardWidget, 
    SearchLineEdit, 
    BodyLabel,
    CaptionLabel, 
    StrongBodyLabel, 
    ScrollArea, 
    PrimaryPushButton, 
    ThemeColor,
    qconfig
)
from ...player.type import SONG_CHANGE_ACTIONS

# --- 1. 自定义 CardWidget ---
# 用于显示MIDI信息的卡片

class MidiCard(CardWidget):
    """
    一个自定义的CardWidget，用于显示单个MIDI文件的信息。
    """
    signal_clicked = pyqtSignal(object)  # 发出自身作为参数

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self.path_str = str(path)
        self.midi_name = path.name
        self.duration = -1.0
        self.is_loaded = False

        # UI 元素
        self.name_label = StrongBodyLabel(self.midi_name)
        self.duration_label = BodyLabel("时长: 正在加载中...")
        self.path_label = CaptionLabel(self.path_str)
        self.status_label = BodyLabel("状态: 排队中")

        # 布局
        layout = QVBoxLayout(self)
        left_layout = QHBoxLayout()
        left_layout.addWidget(self.name_label)
        left_layout.addWidget(self.duration_label)
        right_layout = QHBoxLayout()
        right_layout.addWidget(self.path_label)
        right_layout.addWidget(self.status_label)
        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        
        self.setFixedHeight(80) # 固定卡片大小
        self.setClickEnabled(True)

    def mousePressEvent(self, e):
        self.signal_clicked.emit(self)
        super().mousePressEvent(e)

    def set_selected(self, selected: bool):
        """设置卡片的选中状态"""
        if selected:
            self.setProperty("selected", True)
        else:
            self.setProperty("selected", None)
        self.style().polish(self)
        self.update()

    def update_info(self, duration: float):
        """加载成功后更新UI"""
        self.duration = duration
        self.is_loaded = True
        self.duration_label.setText(f"时长: {duration:.2f} 秒")
        self.status_label.setText("状态: ✅ 已加载")

    def set_loading(self):
        """设置UI为加载中状态"""
        self.status_label.setText("状态: ⏳ 加载中...")

    def set_error(self, error_msg: str):
        """加载失败时更新UI"""
        self.is_loaded = False
        self.duration_label.setText("时长: 加载失败")
        self.status_label.setText(f"状态: ❌ 错误")
        # 添加样式以突出显示错误
        self.setStyleSheet("MidiCard { border: 1px solid red; }")


# --- 2. 异步加载器 (QRunnable) ---
# 使用 QThreadPool 在后台线程中解析MIDI文件

class WorkerSignals(QObject):
    """
    定义 QRunnable 任务可以发出的信号。
    QRunnable 本身不是 QObject，所以需要一个辅助类。
    """
    # 信号: (文件路径字符串, 时长)
    result = pyqtSignal(str, float)
    # 信号: (文件路径字符串, 错误信息)
    error = pyqtSignal(str, str)

class MidiLoaderTask(QRunnable):
    """
    一个 QRunnable 任务，用于在后台加载和解析MIDI文件。
    """
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.path_str = str(path)
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """任务执行的入口点"""
        try:
            mid = mido.MidiFile(self.path)
            duration = mid.length
            # 任务成功，发出 result 信号
            self.signals.result.emit(self.path_str, duration)
        except Exception as e:
            # 任务失败，发出 error 信号
            self.signals.error.emit(self.path_str, str(e))


# --- 3. 主窗口 ---

class MidiCards(QWidget):
    
    signal_card_clicked = pyqtSignal(Path)  # 发出被点击的 MidiCard 对象
    ITEMS_PER_PAGE = 50 # 每页显示50个

    def __init__(self, parent, path):
        super().__init__(parent=parent)
        # 1. 数据模型
        self.all_midi_paths = []    # 存储所有扫描到的MIDI文件路径 (Path对象)
        self.midi_data_cache = {}   # 缓存已加载的MIDI数据 (时长或错误)
        self.selected_path_str: str | None = None
        
        # 2. 状态
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(min(QThreadPool.globalInstance().maxThreadCount(), 2))
        
        self.current_page = 0
        self.total_pages = 0
        self.current_filter_text = ""
        self.current_filtered_paths = [] # 当前过滤+分页后的路径
        
        # 3. UI
        self.main_layout = QVBoxLayout(self)
        
        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("按MIDI名称搜索...")
        
        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.card_layout = QVBoxLayout(self.scroll_content) # 卡片将放在这里
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)

        # 分页控件
        self.page_layout = QHBoxLayout()
        self.prev_button = PrimaryPushButton("上一页")
        self.next_button = PrimaryPushButton("下一页")
        self.page_label = BodyLabel("第 0 / 0 页")
        self.page_layout.addStretch()
        self.page_layout.addWidget(self.prev_button)
        self.page_layout.addWidget(self.page_label)
        self.page_layout.addWidget(self.next_button)
        self.page_layout.addStretch()

        # 组装主布局
        self.main_layout.addWidget(self.search_box)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addLayout(self.page_layout)
        
        # 连接信号
        self.connect_signals()
        
        # 启动
        self.load_directory(path)
        # 4. 连接 qconfig 信号，以便在主题更改时自动更新
        self._update_stylesheet()
        qconfig.themeChanged.connect(self._update_stylesheet)

    def _generate_stylesheet(self) -> str:
        """根据当前主题动态生成 QSS 字符串"""
        
        # 1. 获取当前的主题色
        # .color() 返回 QColor, .name() 返回 "#RRGGBB"
        primary_color = ThemeColor.PRIMARY.color().name() 
        return f"""
        MidiCard {{
            /* 默认状态：2px的透明边框，用于占位，防止选中时跳动 */
            border: 2px solid transparent; 
            border-radius: 6px;
        }}

        MidiCard[selected="true"] {{
            /* 选中状态：当前的主题色边框 */
            border: 2px solid {primary_color};
        }}
        """

    @pyqtSlot()
    def _update_stylesheet(self):
        """
        应用或更新样式表。
        这会在初始化时被调用一次，
        并在每次主题更改时再次被调用。
        """
        style = self._generate_stylesheet()
        self.setStyleSheet(style)

    def connect_signals(self):
        """连接所有信号和槽"""
        self.search_box.textChanged.connect(self.on_search)
        self.prev_button.clicked.connect(self.prev_page)
        self.next_button.clicked.connect(self.next_page)

    def load_directory(self, dir_path: str):
        """
        扫描文件夹以查找所有MIDI文件。
        这是一个快速操作，所以可以在主线程中完成。
        """
        print(f"正在扫描: {dir_path}")
        self.all_midi_paths.clear()
        self.midi_data_cache.clear()
        
        try:
            # 使用 rglob 递归搜索 .mid 和 .midi 文件
            path = Path(dir_path)
            self.all_midi_paths.extend(path.rglob('*.mid'))
            self.all_midi_paths.extend(path.rglob('*.midi'))
            
            # 排序
            self.all_midi_paths.sort()
            
            print(f"找到了 {len(self.all_midi_paths)} 个MIDI文件。")
            
            # 重置分页并显示第一页
            self.current_page = 0
            self.update_ui()
            
        except Exception as e:
            print(f"扫描文件夹时出错: {e}")

    def on_search(self, text: str):
        """搜索框文本更改时的槽函数"""
        self.current_filter_text = text.lower()
        self.current_page = 0  # 每次新搜索都重置到第一页
        self.update_ui()

    def prev_page(self):
        """切换到上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_ui()

    def next_page(self):
        """切换到下一页"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_ui()
            
    def clear_layout(self, layout):
        """清空布局中的所有小部件"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_ui(self):
        """
        核心函数：根据当前搜索和分页，更新显示的卡片。
        """
        # 1. 过滤: 根据搜索词过滤所有路径
        if self.current_filter_text:
            self.current_filtered_paths = [
                p for p in self.all_midi_paths 
                if self.current_filter_text in p.name.lower()
            ]
        else:
            self.current_filtered_paths = self.all_midi_paths[:]
            
        # 2. 计算分页
        total_items = len(self.current_filtered_paths)
        self.total_pages = max(1, (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.current_page = max(0, min(self.current_page, self.total_pages - 1))
        
        self.page_label.setText(f"第 {self.current_page + 1} / {self.total_pages} 页 (共 {total_items} 项)")
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < self.total_pages - 1)

        # 3. 获取当前页的路径
        start_index = self.current_page * self.ITEMS_PER_PAGE
        end_index = start_index + self.ITEMS_PER_PAGE
        paths_to_display = self.current_filtered_paths[start_index:end_index]
        
        # 4. 清空旧卡片
        self.clear_layout(self.card_layout)
        
        # 5. 创建新卡片
        for path in paths_to_display:
            path_str = str(path)
            card = MidiCard(path)
            self.card_layout.addWidget(card)

            # --- 新增：连接点击信号 ---
            card.signal_clicked.connect(self.on_card_clicked)
            
            # --- 新增：检查此卡片是否是之前选中的卡片 ---
            if path_str == self.selected_path_str:
                card.set_selected(True)
            
            # 6. 检查缓存
            if path_str in self.midi_data_cache:
                cached_data = self.midi_data_cache[path_str]
                if isinstance(cached_data, float):
                    card.update_info(cached_data)
                else: # 是一个错误
                    card.set_error(cached_data)
            else:
                # 7. 启动异步加载
                card.set_loading()
                task = MidiLoaderTask(path)
                # 连接此特定任务的信号
                task.signals.result.connect(self.on_midi_loaded)
                task.signals.error.connect(self.on_midi_error)
                self.threadpool.start(task)

    @pyqtSlot(object)
    def on_card_clicked(self, clicked_card: MidiCard | None, path_str: str = ""):
        """当一个MidiCard被点击时调用"""
        
        # 如果点击的已经是选中的卡片，则什么也不做
        if clicked_card and self.selected_path_str == clicked_card.path_str:
            return

        # 1. 取消选中旧卡片 (如果它还可见)
        if self.selected_path_str:
            old_card = self.find_visible_card(self.selected_path_str)
            if old_card:
                old_card.set_selected(False)

        # 2. 选中新卡片
        if clicked_card:
            clicked_card.set_selected(True)
            self.selected_path_str = clicked_card.path_str # 存储新选中的路径
        else:
            self.selected_path_str = path_str
        self.signal_card_clicked.emit(self.get_selected_midi_path())

    @pyqtSlot(str, float)
    def on_midi_loaded(self, path_str: str, duration: float):
        """
        MIDI文件加载成功时的槽函数 (来自后台线程)
        """
        # 缓存结果
        self.midi_data_cache[path_str] = duration
        
        # 查找当前是否显示了这个卡片
        card = self.find_visible_card(path_str)
        if card:
            card.update_info(duration)

    @pyqtSlot(str, str)
    def on_midi_error(self, path_str: str, error_msg: str):
        """
        MIDI文件加载失败时的槽函数 (来自后台线程)
        """
        # 缓存错误信息
        self.midi_data_cache[path_str] = error_msg
        print(f"加载 {path_str} 出错: {error_msg}")
        
        # 查找当前是否显示了这个卡片
        card = self.find_visible_card(path_str)
        if card:
            card.set_error(error_msg)
            
    def find_visible_card(self, path_str: str) -> MidiCard | None:
        """在当前显示的卡片中查找匹配的卡片"""
        for i in range(self.card_layout.count()):
            widget = self.card_layout.itemAt(i).widget()
            if isinstance(widget, MidiCard) and widget.path_str == path_str:
                return widget
        return None
    
    def get_selected_midi_path(self) -> Path | None:
        picked = [x for x in self.all_midi_paths if str(x) == self.selected_path_str]
        if picked:
            return picked[0]
        else:
            return None
              
    def get_card_and_select(self, action: SONG_CHANGE_ACTIONS) -> Path | None:
        """获取下一个MIDI文件路径并选中它"""
        all_paths = self.all_midi_paths
        [current_idx] = [i for i, p in enumerate(all_paths) if str(p) == self.selected_path_str] or [-1]
        if current_idx == -1:
            current_idx = 0
        total_len = len(all_paths)
        max_times = total_len  # 防止死循环
        current_times = 0
        next_path = None
        while max_times > current_times: 
            if action == SONG_CHANGE_ACTIONS.NEXT_SONG:
                next_idx = current_idx + 1 if current_idx < total_len - 1 else 0
            elif action == SONG_CHANGE_ACTIONS.PREVIOUS_SONG:
                next_idx = current_idx - 1 if current_idx > 0 else total_len - 1
            else:
                return None
            next_path = all_paths[next_idx]
            this_midi = self.midi_data_cache.get(str(next_path), None)
            if this_midi and isinstance(this_midi, float):
                break
            current_idx = next_idx
            current_times += 1
        
        if next_path:
            self.on_card_clicked(self.find_visible_card(str(next_path)), str(next_path))
        return next_path

    