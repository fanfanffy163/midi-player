import json
import os
from pathlib import Path

import mido
from loguru import logger

# --- 依赖 ---
from pypinyin import Style, pinyin
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    PrimaryPushButton,
    ScrollArea,
    SearchLineEdit,
    StrongBodyLabel,
    ThemeColor,
)
from whoosh import query
from whoosh.fields import ID, NGRAM, Schema
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import MultifieldParser, OrGroup

from ...player.type import SONG_CHANGE_ACTIONS
from ...utils.config import cfg
from ...utils.utils import Utils


# --- 1. 自定义 CardWidget ---
# (与您提供的版本完全相同，无需更改)
class MidiCard(CardWidget):
    """
    一个自定义的CardWidget，用于显示单个MIDI文件的信息。
    """

    signal_clicked = Signal(object)  # 发出自身作为参数

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self.path_str = str(path)
        self.midi_name = path.name
        self.duration = -1.0
        self.is_loaded = False

        # UI 元素
        self.name_label = StrongBodyLabel(Utils.truncate_middle(self.midi_name))
        self.duration_label = BodyLabel("时长: 正在加载中...")
        self.path_label = CaptionLabel(Utils.truncate_middle(self.path_str))
        self.status_label = BodyLabel("状态: 排队中")  # <-- 初始状态

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

        self.setFixedHeight(80)  # 固定卡片大小
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
        self.setStyleSheet("MidiCard { border: 1px solid red; }")


# --- 2. 异步任务定义 ---


class WorkerSignals(QObject):
    """
    定义所有 QRunnable 任务可以发出的信号。
    """

    # 信号: (索引是否成功)
    index_ready = Signal(bool)
    # 信号: (过滤后的路径列表)
    search_complete = Signal(list)

    # --- 修改：单个加载 ---
    # 信号: (路径str, 状态'ok'|'error', 数据 float|str)
    single_load_complete = Signal(str, str, object)


# --- 3. Whoosh FTS (全文搜索) 任务 ---

# --- 3a. Whoosh Schema (索引结构) ---
SCHEMA = Schema(
    path=ID(stored=True, unique=True),
    name_ngram=NGRAM(minsize=1, maxsize=10, stored=False),
    pinyin_full_ngram=NGRAM(minsize=2, maxsize=10, stored=False),
    pinyin_initial_ngram=NGRAM(minsize=1, maxsize=10, stored=False),
)


# --- 3b. 索引构建器 (无修改) ---
class IndexBuilderTask(QRunnable):
    """
    后台任务：使用 Whoosh 创建 FTS 索引，并写入一个 .meta 清单文件
    """

    def __init__(self, dir_path: Path, index_dir: Path):
        super().__init__()
        self.dir_path = dir_path
        self.index_dir = index_dir
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            if not os.path.exists(self.index_dir):
                os.makedirs(self.index_dir)

            ix = create_in(self.index_dir, SCHEMA)
            writer = ix.writer(limitmb=256, procs=max(1, os.cpu_count() // 2))

            paths = list(self.dir_path.rglob("*.mid"))
            paths.extend(list(self.dir_path.rglob("*.midi")))

            total_count = 0
            for path in paths:
                name = path.name
                try:
                    pinyin_full_list = pinyin(name, style=Style.NORMAL)
                    pinyin_full = "".join([item[0] for item in pinyin_full_list])
                    pinyin_initial_list = pinyin(name, style=Style.FIRST_LETTER)
                    pinyin_initial = "".join([item[0] for item in pinyin_initial_list])
                except Exception:
                    pinyin_full = ""
                    pinyin_initial = ""

                writer.add_document(
                    path=str(path),
                    name_ngram=name.lower(),
                    pinyin_full_ngram=pinyin_full,
                    pinyin_initial_ngram=pinyin_initial,
                )
                total_count += 1

            logger.debug(f"Whoosh: 正在提交 {total_count} 个文件...")
            writer.commit()
            logger.debug("Whoosh: 索引构建完毕。")

            try:
                source_mtime = os.path.getmtime(self.dir_path)
                meta_data = {
                    "source_path": os.path.normpath(str(self.dir_path)),
                    "source_mtime": source_mtime,
                    "file_count": total_count,
                }
                meta_path = self.index_dir / "index.meta"
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f)
                logger.debug(f"元数据已写入: {meta_path}")
            except Exception as meta_e:
                logger.opt(exception=meta_e).error(
                    f"警告：索引 .meta 文件写入失败: {meta_e}"
                )

            self.signals.index_ready.emit(True)

        except Exception as e:
            logger.opt(exception=e).error(f"创建 Whoosh 索引失败: {e}")
            self.signals.index_ready.emit(False)


# --- 3c. 搜索器 (无修改) ---
class SearchTask(QRunnable):
    """
    后台任务：使用 Whoosh 索引和查询词进行毫秒级过滤。
    """

    def __init__(self, index_dir: Path, search_text: str):
        super().__init__()
        self.index_dir = index_dir
        self.search_text = search_text
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            ix = open_dir(self.index_dir)

            if not self.search_text:
                q = query.Every()  # 空搜索 = 匹配所有
            else:
                parser = MultifieldParser(
                    ["name_ngram", "pinyin_full_ngram", "pinyin_initial_ngram"],
                    schema=ix.schema,
                    group=OrGroup,
                )
                query_text = f"{self.search_text.lower()}*"
                q = parser.parse(query_text)

            filtered_paths = []
            with ix.searcher() as searcher:
                results = searcher.search(q, limit=None)
                for r in results:
                    filtered_paths.append(Path(r["path"]))
            filtered_paths = Utils.sort_path_list_by_name(filtered_paths)

            self.signals.search_complete.emit(filtered_paths)
        except Exception as e:
            logger.debug(f"Whoosh 搜索出错: {e}")
            self.signals.search_complete.emit([])


# --- 3d. (新) 单个加载器 ---
class SingleLoaderTask(QRunnable):
    """
    一个 QRunnable 任务，用于在子线程中加载 *单个* MIDI 文件。
    """

    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.path_str = str(path)
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            mid = mido.MidiFile(self.path)
            duration = mid.length
            # 发出信号: (路径, 状态, 数据)
            self.signals.single_load_complete.emit(self.path_str, "ok", duration)
        except Exception as e:
            error_str = str(e)
            # 发出信号: (路径, 状态, 数据)
            self.signals.single_load_complete.emit(self.path_str, "error", error_str)


# --- 4. 主窗口 (重构版) ---


class MidiCards(QWidget):

    signal_card_clicked = Signal(Path)
    ITEMS_PER_PAGE = 50
    INDEX_DIR = Path(Utils.user_path("midi_index_whoosh"))

    # (移除 MAX_DISPATCH_TASKS，不再需要)

    def __init__(self, parent):
        super().__init__(parent=parent)
        # 1. 数据模型
        self.all_midi_paths = []
        self.midi_data_cache = {}
        self.selected_path_str: str | None = None

        # 2. 状态
        self.is_index_ready = False
        self.threadpool = QThreadPool()
        # 我们可以使用更多线程，因为任务（加载单个MIDI）非常轻量
        self.threadpool.setMaxThreadCount(1)

        self.current_page = 0
        self.total_pages = 0
        self.current_filter_text = ""
        self.current_filtered_paths = []

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(200)

        # --- 移除: 批量任务收集器 ---
        # self.batch_collector = {}

        # 3. UI
        self.main_layout = QVBoxLayout(self)

        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("搜索 (支持名称, 全拼, 首字母)...")

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.card_layout = QVBoxLayout(self.scroll_content)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_content.setObjectName("ScrollContent")

        self.page_layout = QHBoxLayout()
        self.prev_button = PrimaryPushButton("上一页")
        self.next_button = PrimaryPushButton("下一页")
        self.page_label = BodyLabel("第 0 / 0 页")
        self.page_layout.addStretch()
        self.page_layout.addWidget(self.prev_button)
        self.page_layout.addWidget(self.page_label)
        self.page_layout.addWidget(self.next_button)
        self.page_layout.addStretch()

        self.main_layout.addWidget(self.search_box)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addLayout(self.page_layout)

        self.connect_signals()
        self.load_index_and_directory(cfg.get(cfg.midi_folder))

        self._update_stylesheet(None)
        cfg.themeColorChanged.connect(self._update_stylesheet)

    def _generate_stylesheet(self, color) -> str:
        primary_color = (
            ThemeColor.PRIMARY.color().name() if color == None else color.name()
        )
        return f"""
        MidiCard[selected="true"] {{
            border: 2px solid {primary_color};
        }}
        """

    @Slot()
    def _update_stylesheet(self, color):
        style = self._generate_stylesheet(color)
        self.setStyleSheet(style)

    def connect_signals(self):
        """连接所有信号和槽"""
        self.search_box.textChanged.connect(self.on_search)
        self.search_timer.timeout.connect(self._trigger_search)
        self.prev_button.clicked.connect(self.prev_page)
        self.next_button.clicked.connect(self.next_page)
        cfg.midi_folder.valueChanged.connect(self._on_folder_change)

    @Slot(Path)
    def _on_folder_change(self, path: Path):
        self.load_index_and_directory(str(path), force_rebuild=True)

    # --- 智能索引加载 (无修改) ---
    def load_index_and_directory(self, dir_path_str: str, force_rebuild: bool = False):
        dir_path = Path(dir_path_str)
        meta_path = self.INDEX_DIR / "index.meta"
        needs_rebuild = False
        rebuild_reason = ""

        if force_rebuild:
            needs_rebuild = True
            rebuild_reason = "用户强制重建"

        elif not exists_in(self.INDEX_DIR):
            needs_rebuild = True
            rebuild_reason = "索引目录不存在"

        elif not meta_path.exists():
            needs_rebuild = True
            rebuild_reason = "索引元文件 (index.meta) 丢失"

        else:
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)

                meta_path_str = meta_data.get("source_path")
                meta_mtime = meta_data.get("source_mtime")

                norm_meta_path = (
                    os.path.normpath(meta_path_str) if meta_path_str else ""
                )
                norm_current_path = os.path.normpath(dir_path_str)

                if norm_meta_path != norm_current_path:
                    needs_rebuild = True
                    rebuild_reason = (
                        f"配置路径已更改 (原: {meta_path_str}, " f"现: {dir_path_str})"
                    )
                else:
                    current_mtime = os.path.getmtime(dir_path_str)
                    if current_mtime != meta_mtime:
                        needs_rebuild = True
                        rebuild_reason = (
                            f"文件夹内容已更改 "
                            f"(mtime: {meta_mtime} -> {current_mtime})"
                        )

            except Exception as e:
                needs_rebuild = True
                rebuild_reason = f"索引元文件 (index.meta) 损坏: {e}"

        if needs_rebuild:
            logger.debug(f"需要重建索引。原因: {rebuild_reason}")
            self.is_index_ready = False
            self.search_box.setEnabled(False)
            self.search_box.setText("正在构建索引，请稍候...")
            self.all_midi_paths.clear()
            self.current_filtered_paths.clear()

            self.clear_layout(self.card_layout)
            task = IndexBuilderTask(dir_path, self.INDEX_DIR)
            task.signals.index_ready.connect(self.on_index_ready)
            self.threadpool.start(task)
        else:
            logger.debug("Whoosh 索引已是最新，直接使用。")
            self.on_index_ready(True)

    @Slot(bool)
    def on_index_ready(self, success: bool):
        # (无修改)
        if not success:
            logger.debug("索引构建失败。")
            self.search_box.setText("索引构建失败！")
            return

        logger.debug("索引已就绪。")
        self.is_index_ready = True
        self.search_box.setEnabled(True)
        self.search_box.setText("")
        self.search_box.setPlaceholderText("搜索 (支持名称, 全拼, 首字母)...")

        self._trigger_search(get_all_paths=True)

    def on_search(self, text: str):
        # (无修改)
        if not self.is_index_ready:
            return
        self.current_filter_text = text.lower()
        self.search_timer.start()

    @Slot()
    def _trigger_search(self, get_all_paths: bool = False):
        # (无修改)
        if not self.is_index_ready:
            return

        search_text = "" if get_all_paths else self.current_filter_text
        logger.debug(f"Whoosh 搜索: '{search_text}'")

        task = SearchTask(self.INDEX_DIR, search_text)

        if get_all_paths:
            task.signals.search_complete.connect(self._on_all_paths_loaded)
        else:
            task.signals.search_complete.connect(self.on_search_results)

        self.current_page = 0
        self.threadpool.start(task)

    @Slot(list)
    def _on_all_paths_loaded(self, all_paths: list):
        # (无修改)
        logger.debug(f"已加载所有路径: {len(all_paths)}")
        all_paths = Utils.sort_path_list_by_name(all_paths)
        self.all_midi_paths = all_paths
        self.on_search_results(all_paths)

    # --- (重构) 层级 1：渲染与分发 ---
    @Slot(list)
    def on_search_results(self, filtered_paths: list):
        """
        (重构：渲染-然后-更新)
        当 SearchTask 完成时调用 (主线程)
        """
        self.current_filtered_paths = filtered_paths

        total_items = len(self.current_filtered_paths)
        self.total_pages = max(
            1, (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        )
        self.current_page = max(0, min(self.current_page, self.total_pages - 1))

        self.page_label.setText(
            f"第 {self.current_page + 1} / {self.total_pages} 页 (共 {total_items} 项)"
        )
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < self.total_pages - 1)

        start_index = self.current_page * self.ITEMS_PER_PAGE
        end_index = start_index + self.ITEMS_PER_PAGE
        paths_to_display = self.current_filtered_paths[start_index:end_index]

        self.clear_layout(self.card_layout)

        # --- 新逻辑：立即渲染，异步加载 ---

        if not paths_to_display:
            # (如果列表为空，在此处返回)
            return

        logger.debug(f"正在渲染 {len(paths_to_display)} 个卡片，并异步派发加载任务...")

        for path in paths_to_display:
            path_str = str(path)

            # 1. 立即创建并添加 Card
            card = MidiCard(path)
            self.card_layout.addWidget(card)
            card.signal_clicked.connect(self.on_card_clicked)

            if path_str == self.selected_path_str:
                card.set_selected(True)

            # 2. 检查缓存
            cached_data = self.midi_data_cache.get(path_str)

            if cached_data is not None:
                # 缓存命中，立即更新UI
                if isinstance(cached_data, float):
                    card.update_info(cached_data)  # data is duration
                else:
                    card.set_error(str(cached_data))  # data is error string
            else:
                # 3. 缓存未命中，设置加载中并派发任务
                card.set_loading()  # 设置为 "⏳ 加载中..."

                task = SingleLoaderTask(path)
                # 关键: 连接到新的槽
                task.signals.single_load_complete.connect(self._on_single_load_complete)
                self.threadpool.start(task)

    # --- (新增) 异步更新槽 ---
    @Slot(str, str, object)
    def _on_single_load_complete(self, path_str: str, status: str, data: object):
        """
        (新) 当一个 SingleLoaderTask 完成时调用 (主线程)
        """
        # 1. 无论如何，先缓存结果
        # (注意：我们缓存成功(float)和失败(str))
        self.midi_data_cache[path_str] = data

        # 2. 查找对应的卡片
        card = self.find_visible_card(path_str)

        # 3. 如果卡片*仍然*在屏幕上，则更新它
        if card:
            if status == "ok":
                card.update_info(data)  # data is duration
            else:
                card.set_error(str(data))  # data is error string
        # else:
        #   卡片已不在视图中 (用户翻页或新搜索)
        #   无需执行任何操作，数据已缓存。

    # --- 辅助函数 ---

    def prev_page(self):
        """切换到上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self.on_search_results(self.current_filtered_paths)

    def next_page(self):
        """切换到下一页"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.on_search_results(self.current_filtered_paths)

    def clear_layout(self, layout):
        """清空布局中的所有小部件"""
        # (移除了 self.batch_collector = {})
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    @Slot(object)
    def on_card_clicked(self, clicked_card: MidiCard | None, path_str: str = ""):
        # (无修改)
        if clicked_card and self.selected_path_str == clicked_card.path_str:
            return

        if self.selected_path_str:
            old_card = self.find_visible_card(self.selected_path_str)
            if old_card:
                old_card.set_selected(False)

        if clicked_card:
            clicked_card.set_selected(True)
            self.selected_path_str = clicked_card.path_str
        else:
            self.selected_path_str = path_str
            new_card = self.find_visible_card(self.selected_path_str)
            if new_card:
                new_card.set_selected(True)

        self.signal_card_clicked.emit(Path(self.selected_path_str))

    def find_visible_card(self, path_str: str) -> MidiCard | None:
        """在当前显示的卡片中查找匹配的卡片"""
        # (无修改)
        for i in range(self.card_layout.count()):
            widget = self.card_layout.itemAt(i).widget()
            if isinstance(widget, MidiCard) and widget.path_str == path_str:
                return widget
        return None

    def get_card_and_select(self, action: SONG_CHANGE_ACTIONS) -> Path | None:
        # (无修改，此逻辑依赖于 self.midi_data_cache，新架构依然维护此缓存)
        all_paths = self.all_midi_paths
        if not all_paths:
            return None

        [current_idx] = [
            i for i, p in enumerate(all_paths) if str(p) == self.selected_path_str
        ] or [-1]

        if current_idx == -1 and all_paths:
            current_idx = 0
        elif current_idx == -1:
            return None

        total_len = len(all_paths)
        max_times = total_len
        current_times = 0
        next_path = None

        while max_times > current_times:
            if action == SONG_CHANGE_ACTIONS.NEXT_SONG:
                next_idx = (current_idx + 1) % total_len
            elif action == SONG_CHANGE_ACTIONS.PREVIOUS_SONG:
                next_idx = (current_idx - 1 + total_len) % total_len
            else:
                return None

            next_path = all_paths[next_idx]
            this_midi = self.midi_data_cache.get(str(next_path), None)
            # (此检查确保我们只切换到已成功加载的MIDI)
            if this_midi and isinstance(this_midi, float):
                break

            current_idx = next_idx
            current_times += 1

        if next_path:
            self.on_card_clicked(None, str(next_path))

            card = self.find_visible_card(str(next_path))
            if not card:
                try:
                    full_idx = self.current_filtered_paths.index(next_path)
                    target_page = full_idx // self.ITEMS_PER_PAGE
                    if target_page != self.current_page:
                        self.current_page = target_page
                        # 触发重新渲染
                        self.on_search_results(self.current_filtered_paths)
                        # 渲染后高亮 (需要延迟)
                        QTimer.singleShot(
                            50, lambda: self.on_card_clicked(None, str(next_path))
                        )
                except ValueError:
                    pass

        return next_path
