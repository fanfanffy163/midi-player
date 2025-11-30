import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Optional

import requests
from loguru import logger
from packaging.version import parse
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, MessageBox, NavigationItemPosition

from midiplayer.core.component.common.update_info_dialog import UpdateProgressDialog
from midiplayer.core.component.pages.editor_page import EditorPage
from midiplayer.core.component.pages.music_play_page import MusicPlayPage
from midiplayer.core.component.pages.omr_page import OMRInterface
from midiplayer.core.component.pages.present_page import PresentPage
from midiplayer.core.component.pages.setting_page import SettingPage
from midiplayer.core.utils.db_manager import DBManager
from midiplayer.core.utils.utils import Utils


class CheckUpdateThread(QThread):
    """检查更新线程"""

    check_finished = Signal(dict)  # {success: bool, data: dict, msg: str}

    def __init__(self, current_version, repo_owner, repo_name):
        super().__init__()
        self.current_version = current_version
        self.api_url = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        )

    def run(self):
        try:
            # 5秒超时
            resp = requests.get(self.api_url, timeout=5)
            if resp.status_code != 200:
                self.check_finished.emit(
                    {"success": False, "msg": f"HTTP {resp.status_code}"}
                )
                return

            data = resp.json()
            remote_ver = data.get("tag_name", "").lstrip("v")

            if parse(remote_ver) > parse(self.current_version):
                self.check_finished.emit(
                    {
                        "success": True,
                        "data": data,
                        "new_version": remote_ver,
                        "is_lastest": False,
                    }
                )
            else:
                self.check_finished.emit(
                    {"success": True, "msg": "已是最新版本", "is_lastest": True}
                )

        except Exception as e:
            self.check_finished.emit({"success": False, "msg": str(e)})


class DownloadThread(QThread):
    """下载线程"""

    progress_val = Signal(int)  # 0-100
    download_finished = Signal(str)  # 成功返回文件路径
    error_occurred = Signal(str)  # 失败返回错误信息

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        final_url = self.url
        try:
            with requests.get(
                final_url,
                stream=True,
                timeout=30,
                verify=False,
            ) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))

                with open(self.save_path, "wb") as f:
                    if total_size == 0:
                        f.write(r.content)
                        self.progress_val.emit(100)
                    else:
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                # 计算百分比
                                progress = int((downloaded / total_size) * 100)
                                self.progress_val.emit(progress)

            self.download_finished.emit(self.save_path)

        except Exception as e:
            # 下载失败清理垃圾
            if os.path.exists(self.save_path):
                os.remove(self.save_path)
            self.error_occurred.emit(str(e))


# --- 主窗口 ---
class MainWindow(FluentWindow):

    def __init__(self):
        super().__init__()
        app_name, version, author = Utils.get_app_info()
        self.app_name = app_name
        self.app_version = version
        self.app_author = author
        self.setWindowTitle(f"MIDI按键播放器(v{version})")
        self.setWindowIcon(QIcon(FluentIcon.MUSIC.path()))

        self.resize(1000, 800)
        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # 跟踪当前加载的预设
        self.current_preset_name: Optional[str] = None

        # 1. 初始化数据库管理器
        self.db = DBManager()

        # 2. 初始化UI页面
        self.editor_page = EditorPage(self.db, self)
        self.present_page = PresentPage(self.db, self)
        self.music_play_page = MusicPlayPage(self.db, self)
        self.omr_page = OMRInterface(self)
        self.setting_page = SettingPage(self)
        self.editor_page.signal_save_preset.connect(self.on_preset_changed)
        self.present_page.signal_load_present.connect(self.on_load_preset)
        self.present_page.signal_change_present.connect(self.on_preset_changed)

        # 3. 添加导航项
        self.addSubInterface(self.editor_page, FluentIcon.EDIT, "按键编辑器")
        self.addSubInterface(self.present_page, FluentIcon.BOOK_SHELF, "按键预设管理")
        self.addSubInterface(self.music_play_page, FluentIcon.MUSIC, "Midi播放")
        self.addSubInterface(self.omr_page, FluentIcon.UPDATE, "乐谱转Midi")

        self.navigationInterface.addItem(
            routeKey="update",
            icon=FluentIcon.INFO,
            text="检查更新",
            onClick=self.check_update,
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.setting_page, FluentIcon.SETTING, "设置", NavigationItemPosition.BOTTOM
        )

    def on_load_preset(self, name, mappings: Optional[dict]):
        """从预设页面加载预设"""
        if mappings is not None:
            self.editor_page.set_all_mappings(mappings)
            self.editor_page.set_editor_title(name)
            self.switchTo(self.editor_page)

    def on_preset_changed(self, success: bool):
        """处理预设保存后的操作"""
        if success:
            self.present_page.refresh_preset_list()
            self.music_play_page.refresh_preset_list()

    def closeEvent(self, event):
        """处理窗口关闭事件，确保播放器正确关闭"""
        self.music_play_page.stop_play()
        super().closeEvent(event)

    def check_update(self):
        Utils.show_info_infobar(self, "提示", "正在连接 GitHub 检查更新信息...")
        self.check_thread = CheckUpdateThread(
            self.app_version, self.app_author, self.app_name
        )
        self.check_thread.check_finished.connect(self.on_check_finished)
        self.check_thread.start()

    def on_check_finished(self, res):
        if not res["success"]:
            Utils.show_error_infobar(self, "错误", res["msg"])
            return

        if res["is_lastest"]:
            Utils.show_success_infobar(self, "提示", "已经是最新版本")
            return

        # 发现新版本，弹出确认框
        data = res["data"]
        new_ver = res["new_version"]
        body = data.get("body", "无更新日志")

        msg_box = MessageBox(
            f"发现新版本 {new_ver}", f"更新内容:\n{body}\n\n是否立即更新？", self
        )
        if msg_box.exec():
            # 获取 zip 下载链接
            assets = data.get("assets", [])
            zip_url = next(
                (
                    a["browser_download_url"]
                    for a in assets
                    if a["name"].endswith(".zip")
                ),
                None,
            )

            if zip_url:
                self.start_download(zip_url)
            else:
                Utils.show_error_infobar(self, "错误", "未找到 .zip 格式的更新包")

    def start_download(self, url):
        # 1. 准备临时文件路径
        temp_dir = tempfile.gettempdir()
        unique_id = str(uuid.uuid4())
        target_dir = os.path.join(temp_dir, self.app_name + "_" + unique_id)
        os.makedirs(target_dir, exist_ok=True)
        save_path = os.path.join(target_dir, "update_pkg.zip")

        # 2. 显示进度弹窗
        self.progress_dlg = UpdateProgressDialog(self)
        self.progress_dlg.show()

        # 3. 启动下载线程
        self.dl_thread = DownloadThread(url, save_path)
        self.dl_thread.progress_val.connect(self.progress_dlg.set_progress)
        self.dl_thread.download_finished.connect(self.on_download_complete)
        self.dl_thread.error_occurred.connect(self.on_download_error)

        # 绑定取消按钮关闭线程（简单处理）
        self.progress_dlg.cancelButton.clicked.connect(self.dl_thread.terminate)

        self.dl_thread.start()

    def on_download_error(self, msg):
        self.progress_dlg.close()
        Utils.show_error_infobar(self, "错误", f"下载失败: {msg}")

    def on_download_complete(self, zip_path):
        self.progress_dlg.close()
        # 下载完成，启动外部更新器
        self.launch_updater_and_quit(zip_path)

    def launch_updater_and_quit(self, zip_path):
        """核心：准备环境，启动 updater.exe，自杀"""
        try:
            # 寻找 updater.exe (开发环境/打包环境兼容)

            updater_src = str(Utils.app_root_path("updater.exe"))

            if not os.path.exists(updater_src):
                Utils.show_error_infobar(self, "错误", "丢失 updater.exe 文件！")
                return

            # 复制 updater 到临时目录 (防止被锁)
            temp_updater = os.path.join(
                os.path.dirname(zip_path), "updater_installer.exe"
            )
            shutil.copy(updater_src, temp_updater)

            # 准备参数
            # 1. updater路径 2. zip包路径 3. 安装目录 4. 主程序exe名 5. 主程序PID
            install_dir = (
                os.path.dirname(sys.executable)
                if getattr(sys, "frozen", False)
                else os.getcwd()
            )
            exe_name = os.path.basename(sys.executable)
            pid = str(os.getpid())

            cmd = [temp_updater, zip_path, install_dir, exe_name, pid]

            logger.info(f"准备启动更新，参数{cmd}")
            # 启动
            subprocess.Popen(cmd)

            # 退出主程序
            QApplication.quit()

        except Exception as e:
            Utils.show_error_infobar(self, "错误", f"启动安装程序失败: {e}")
