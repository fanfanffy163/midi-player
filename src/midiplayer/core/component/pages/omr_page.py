import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, CardWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    MessageBox,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    SpinBox,
    StateToolTip,
    StrongBodyLabel,
    SubtitleLabel,
    TextEdit,
    TransparentToolButton,
)

from midiplayer.core.utils.config import cfg
from midiplayer.core.utils.utils import Utils


# ==========================================
# 1. 后台工作线程 (处理 CLI 调用)
# ==========================================
class ConversionWorker(QThread):
    """
    在后台运行 Audiveris CLI，通过信号实时传递日志
    """

    log_signal = Signal(str)  # 实时日志信号
    finish_signal = Signal(bool, str)  # 完成信号 (是否成功, 结果信息/错误信息)

    def __init__(self, audiveris_path, input_file, output_dir, target_bpm=None):
        super().__init__()
        self.audiveris_path = audiveris_path
        self.input_file = input_file
        self.output_dir = output_dir
        self.target_bpm = target_bpm

    def run(self):
        self.log_signal.emit(f"🚀 开始处理文件: {self.input_file}")
        self.log_signal.emit(f"⚙️ 引擎路径: {self.audiveris_path}")

        # 构造命令
        cmd = [
            str(self.audiveris_path),
            "-batch",  # 无头模式
            "-export",  # 导出模式
            "-output",
            str(self.output_dir),  # 输出目录
            str(self.input_file),  # 输入文件
        ]

        try:
            # 启动子进程，实时捕获输出
            # Windows下隐藏CMD窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将错误重定向到标准输出
                text=True,
                encoding="utf-8",  # 注意编码，Windows有时可能需要 'gbk'
                errors="replace",
                startupinfo=startupinfo,
            )

            # 实时读取日志
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.log_signal.emit(line.strip())

            return_code = process.poll()

            if return_code == 0:
                # 假设 Audiveris 成功并在同目录下生成了 .mxl (需要额外转 midi) 或直接生成了 midi
                # 这里模拟一个成功信息
                self.log_signal.emit("✅ Audiveris 处理完成。")
                self.finish_signal.emit(True, str(Path(self.output_dir)))
            else:
                self.finish_signal.emit(False, f"CLI 返回错误代码: {return_code}")

            # --- 寻找 .mxl 文件 ---
            # 我们递归搜索 output_dir 下所有新生成的 .mxl 文件
            found_mxl = list(Path(self.output_dir).rglob("*.mxl"))

            if not found_mxl:
                self.finish_signal.emit(False, "未找到生成的 .mxl 文件，识别可能失败。")
                return

            # 取第一个找到的 mxl 文件 (通常只有一个)
            mxl_path = found_mxl[0]
            self.log_signal.emit(f"📄 找到乐谱文件: {mxl_path.name}")

            # --- 步骤 3: 使用 music21 转 MIDI ---
            self.log_signal.emit(f"🎹 正在利用 music21 生成 MIDI...")

            midi_filename = mxl_path.stem + ".mid"
            midi_path = Path(cfg.get(cfg.midi_folder)) / midi_filename

            from music21 import converter, midi, tempo

            try:
                # 解析 mxl
                score = converter.parse(str(mxl_path))
                # 创建速度标记对象
                mm = tempo.MetronomeMark(number=self.target_bpm)
                for part in score.parts:
                    part.insert(0, mm)

                # 转换为 midi 文件对象
                mf = midi.translate.music21ObjectToMidiFile(score)

                # 写入磁盘
                mf.open(str(midi_path), "wb")
                mf.write()
                mf.close()

                self.log_signal.emit(f"✅ MIDI 转换成功！")
                self.log_signal.emit(f"💾 已保存: {midi_path}")

                # 发送成功信号，返回 MIDI 文件的路径
                self.finish_signal.emit(True, str(midi_path))

            except Exception as e:
                self.log_signal.emit(f"❌ music21 转换失败: {e}")
                self.finish_signal.emit(False, f"MIDI 转换阶段失败: {e}")

        except Exception as e:
            self.finish_signal.emit(False, f"执行异常: {str(e)}")


# ==========================================
# 2. 自定义拖拽上传控件
# ==========================================
class DragDropWidget(CardWidget):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(
            FIF.ACCEPT.icon(color=QColor(96, 96, 96)).pixmap(64, 64)
        )
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.text_label = SubtitleLabel("拖拽 PDF/PNG 文件到此处")
        self.sub_text = CaptionLabel("或者点击此处选择文件")
        self.sub_text.setTextColor(QColor(158, 158, 158), QColor(158, 158, 158))

        layout.addStretch(1)
        layout.addWidget(self.icon_label)
        layout.addSpacing(10)
        layout.addWidget(self.text_label, 0, Qt.AlignCenter)
        layout.addWidget(self.sub_text, 0, Qt.AlignCenter)
        layout.addStretch(1)

        self.setStyleSheet(
            """
            DragDropWidget {
                border: 2px dashed #e0e0e0;
                border-radius: 10px;
                background-color: transparent;
            }
            DragDropWidget:hover {
                background-color: rgba(0, 0, 0, 0.03);
                border-color: #009faa;
            }
        """
        )

    def set_file_selected(self, filename):
        """选中文件后的视觉反馈"""
        self.text_label.setText(Utils.truncate_middle(f"已选择: {filename}", 30))
        self.sub_text.setText("点击或拖拽可更换文件")
        self.icon_label.setPixmap(
            FIF.DOCUMENT.icon(color=QColor(0, 159, 170)).pixmap(64, 64)
        )
        self.setStyleSheet(
            """
            DragDropWidget {
                border: 2px solid #009faa;
                border-radius: 10px;
                background-color: rgba(0, 159, 170, 0.05);
            }
        """
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择乐谱文件", "", "Score Files (*.pdf *.png *.jpg *.bmp)"
            )
            if file_path:
                self.file_dropped.emit(file_path)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in [".pdf", ".png", ".jpg", ".jpeg", ".bmp"]:
                self.file_dropped.emit(f)
                return

        Utils.show_warning_infobar(
            self=self, title="文件格式错误", content="仅支持 PDF 或 图片格式。"
        )


# ==========================================
# 3. 主界面 (SubInterface)
# ==========================================
class OMRInterface(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OMRInterface")

        # 数据状态
        self.audiveris_path = None
        self.selected_file_path = None  # 存储当前选择的文件路径
        self.current_worker = None

        self._init_ui()
        self._check_environment()

    def _init_ui(self):
        # === 整体布局 ===
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 20, 15, 20)
        self.main_layout.setSpacing(10)

        # ----------------------------------
        # Part 1: 顶部基础信息栏 (CardWidget) - 仅保留环境检测
        # ----------------------------------
        self.top_card = CardWidget(self)
        self.top_layout = QHBoxLayout(self.top_card)

        self.status_icon = QLabel()
        self.status_icon.setPixmap(
            FIF.QUESTION.icon(color=QColor(255, 170, 0)).pixmap(24, 24)
        )

        info_layout = QVBoxLayout()
        self.lbl_status_title = StrongBodyLabel("正在检测 Audiveris 环境...")
        self.lbl_current_path = CaptionLabel("路径: 未知")
        self.lbl_current_path.setTextColor(QColor(150, 150, 150), QColor(150, 150, 150))
        info_layout.addWidget(self.lbl_status_title)
        info_layout.addWidget(self.lbl_current_path)

        self.btn_info = TransparentToolButton(FIF.INFO, self)
        self.btn_info.setToolTip("界面信息")
        self.btn_info.clicked.connect(self._show_intro_dialog)

        self.btn_refresh = TransparentToolButton(FIF.SYNC, self)
        self.btn_refresh.setToolTip("刷新环境检测")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)

        self.btn_select_path = PushButton("手动选择路径", self, FIF.FOLDER)
        self.btn_select_path.clicked.connect(self._manual_select_path)
        self.btn_jump_download = PushButton("去下载 Audiveris", self, FIF.DOWNLOAD)
        self.btn_jump_download.clicked.connect(self._jump_download)

        # 顶部进度条 (初始化时隐藏)
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.progress_bar.setFixedHeight(4)

        self.top_layout.addWidget(self.status_icon)
        self.top_layout.addSpacing(10)
        self.top_layout.addLayout(info_layout)
        self.top_layout.addStretch(1)

        self.top_layout.addWidget(self.btn_info)
        self.top_layout.addWidget(self.btn_refresh)
        self.top_layout.addSpacing(10)

        self.top_layout.addWidget(self.btn_jump_download)
        self.top_layout.addSpacing(10)
        self.top_layout.addWidget(self.btn_select_path)

        # 进度条放在顶部卡片下方或内部，这里为了布局简单，不单独占位，
        # 真正忙碌时可以放在最底部或者作为一个 Modal 遮罩，这里暂时先不放在 TopLayout 里

        # ----------------------------------
        # Part 2: 中间区域 (左右分栏)
        # ----------------------------------
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(20)

        # === 左侧：拖拽区 ===
        left_layout = QVBoxLayout()
        self.lbl_drop_title = SubtitleLabel("1. 上传乐谱")
        self.drop_area = DragDropWidget(self)
        # 连接信号：文件选中后，不直接转换，而是保存路径
        self.drop_area.file_dropped.connect(self._on_file_selected)

        left_layout.addWidget(self.lbl_drop_title)
        left_layout.addWidget(self.drop_area)

        # === 右侧：设置与日志区 ===
        right_layout = QVBoxLayout()

        self.settings_layout = QVBoxLayout()
        # 标题
        settings_title = SubtitleLabel("2. 转换设置")

        # BPM 设置行
        setting_card = CardWidget()
        card_layout = QVBoxLayout(setting_card)
        bpm_layout = QHBoxLayout()
        self.lbl_bpm = BodyLabel("目标速度 (BPM):")
        self.bpm_spinBox = SpinBox()
        self.bpm_spinBox.setRange(40, 400)
        self.bpm_spinBox.setValue(120)
        self.lbl_bpm_hint = CaptionLabel('每分钟节拍数，一般位于乐谱开头类似"♩=120"')
        self.lbl_bpm_hint.setTextColor(QColor(150, 150, 150), QColor(150, 150, 150))

        bpm_layout.addWidget(self.lbl_bpm)
        bpm_layout.addSpacing(10)
        bpm_layout.addWidget(self.bpm_spinBox)
        bpm_layout.addSpacing(5)
        bpm_layout.addWidget(self.lbl_bpm_hint)
        bpm_layout.addStretch(1)

        card_layout.addLayout(bpm_layout)

        self.settings_layout.addWidget(settings_title)
        self.settings_layout.addWidget(setting_card)

        # [新增] 右下：日志区
        convert_layout = QHBoxLayout()
        self.lbl_log_title = SubtitleLabel("3. 转换日志")

        self.btn_start = PrimaryPushButton("开始转换", self, FIF.PLAY)
        self.btn_start.setEnabled(False)  # 默认禁用，直到选择文件
        self.btn_start.clicked.connect(self._start_conversion_process)
        convert_layout.addWidget(self.lbl_log_title)
        convert_layout.addStretch(1)
        convert_layout.addWidget(self.btn_start)

        self.console_log = TextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setPlaceholderText("等待任务开始...")
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPixelSize(14)  # 稍微调小一点字体
        self.console_log.setFont(font)

        right_layout.addLayout(self.settings_layout)
        right_layout.addSpacing(15)
        right_layout.addLayout(convert_layout)
        right_layout.addWidget(self.console_log)

        # 设置左右比例 (左 4 : 右 6)
        self.content_layout.addLayout(left_layout, 4)
        self.content_layout.addLayout(right_layout, 6)

        # 下侧 结果展示区 (CardWidget 嵌入)
        self.result_card = CardWidget()
        self.result_card.hide()
        self.result_layout = QVBoxLayout(self.result_card)
        self.lbl_midi_info = StrongBodyLabel("转换成功！")
        self.lbl_midi_detail = CaptionLabel("MIDI信息解析中...")
        self.result_layout.addWidget(self.lbl_midi_info)
        self.result_layout.addWidget(self.lbl_midi_detail)

        # 组装主布局
        self.main_layout.addWidget(self.top_card)
        # 进度条插入在顶部卡片和内容之间
        self.main_layout.addWidget(self.progress_bar)
        self.main_layout.addLayout(self.content_layout)
        self.main_layout.addWidget(self.result_card)

    # ================= 逻辑控制 =================

    def _show_intro_dialog(self):
        """显示功能介绍弹窗"""
        title = "关于乐谱识别 (OMR)"
        content = (
            "本功能利用 OMR (Optical Music Recognition) 技术，将图片或 PDF 格式的乐谱转换为 MIDI 文件。\n\n"
            "核心引擎：Audiveris (开源 OMR 引擎)\n"
            "工作流程：\n"
            "1. 拖入乐谱图片或 PDF。\n"
            "2. 调用 Audiveris 进行后台识别，导出 MusicXML。\n"
            "3. 自动将 MusicXML 转换为 MIDI 并在播放器中可用。\n\n"
            "注意：识别效果取决于乐谱清晰度，复杂乐谱可能需要人工修正。"
        )
        w = MessageBox(title, content, self.window())
        w.exec()

    def _on_refresh_clicked(self):
        """手动刷新环境检测"""
        self.lbl_status_title.setText("正在重新检测...")
        # 为了视觉反馈，这里可以短暂 disable 按钮
        self.btn_refresh.setEnabled(False)
        self._check_environment()
        # 恢复按钮并提示
        self.btn_refresh.setEnabled(True)

        if self.audiveris_path:
            Utils.show_success_infobar(self, "检测完成", "已成功找到 Audiveris。")
        else:
            Utils.show_warning_infobar(
                self, "检测完成", "未能在默认路径找到 Audiveris，请尝试手动选择。"
            )

    def _check_environment(self):
        """检测环境"""
        found_path = Utils.get_audiveris_by_file_omr_ext()
        if found_path:
            self._update_env_status(True, found_path)
        else:
            self._update_env_status(False)

    def _update_env_status(self, found, path=None):
        if found:
            self.audiveris_path = path
            self.lbl_status_title.setText("Audiveris 环境就绪")
            self.lbl_current_path.setText(f"路径: {path}")
            self.status_icon.setPixmap(
                FIF.ACCEPT.icon(color=QColor(0, 159, 170)).pixmap(24, 24)
            )
            self.drop_area.setEnabled(True)
            # 如果此时已经有文件（比如重新检测后），则启用按钮
            if self.selected_file_path:
                self.btn_start.setEnabled(True)
        else:
            self.audiveris_path = None
            self.lbl_status_title.setText("未找到 Audiveris")
            self.lbl_current_path.setText("请手动指定 Audiveris.exe 位置")
            self.status_icon.setPixmap(
                FIF.CANCEL.icon(color=QColor(255, 50, 50)).pixmap(24, 24)
            )
            self.drop_area.setEnabled(False)
            self.btn_start.setEnabled(False)

    def _manual_select_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 Audiveris.exe", "C:/", "Executable (*.exe)"
        )
        if file_path:
            self._update_env_status(True, file_path)

    def _jump_download(self):
        import webbrowser

        webbrowser.open("https://github.com/Audiveris/audiveris")

    def _on_file_selected(self, file_path):
        """文件选择后的回调"""
        self.selected_file_path = file_path
        # 更新拖拽区的视觉
        self.drop_area.set_file_selected(Path(file_path).name)
        # 启用开始按钮 (如果环境也OK)
        if self.audiveris_path:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("开始转换")

        # 清空之前的日志和结果
        self.console_log.clear()
        self.console_log.setPlaceholderText("文件已就绪，请点击右上角“开始转换”...")
        self.result_card.hide()

    def _start_conversion_process(self):
        """点击按钮后触发的真实转换逻辑"""
        if not self.audiveris_path or not self.selected_file_path:
            return

        # 1. UI 状态更新
        self.drop_area.setEnabled(False)
        self.btn_select_path.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_start.setText("正在转换...")
        self.bpm_spinBox.setEnabled(False)  # 锁定参数

        self.progress_bar.show()
        self.console_log.clear()
        self.result_card.hide()

        self.stateTooltip = StateToolTip(
            "正在转换中...", "请稍候，这可能需要几分钟", self.window()
        )
        self.stateTooltip.move(self.stateTooltip.getSuitablePos())
        self.stateTooltip.show()

        # 2. 准备参数
        input_path = Path(self.selected_file_path)
        output_dir = input_path.parent / "midi_output"
        output_dir.mkdir(exist_ok=True)
        user_bpm = self.bpm_spinBox.value()

        # 3. 启动线程
        self.current_worker = ConversionWorker(
            self.audiveris_path, input_path, output_dir, user_bpm
        )
        self.current_worker.log_signal.connect(self._append_log)
        self.current_worker.finish_signal.connect(self._on_conversion_finished)
        self.current_worker.start()

    def _append_log(self, text):
        self.console_log.append(text)
        scrollbar = self.console_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_conversion_finished(self, success, message):
        self.progress_bar.hide()
        self.drop_area.setEnabled(True)
        self.btn_select_path.setEnabled(True)
        self.bpm_spinBox.setEnabled(True)

        # 恢复按钮状态，允许再次转换
        self.btn_start.setEnabled(True)
        self.btn_start.setText("再次转换")

        if self.stateTooltip:
            self.stateTooltip.setContent("任务结束" if success else "任务失败")
            self.stateTooltip.setState(True)
            self.stateTooltip = None

        if success:
            self.result_card.show()
            self.lbl_midi_info.setText(f"输出目录: {message}")
            self.lbl_midi_detail.setText("请检查输出目录下的 .mxl 或 .mid 文件")

            Utils.show_success_infobar(
                self=self, title="转换完成", content=f"文件已保存至: {message}"
            )
        else:
            Utils.show_error_infobar(self=self, title="发生错误", content=message)
