import json
import os
import shlex
import sys
import winreg
from pathlib import Path

import platformdirs
from loguru import logger
from pypinyin import Style, pinyin
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition


class Utils:
    # --- 信息栏辅助函数 ---
    @staticmethod
    def show_success_infobar(self: QWidget, title: str, content: str, duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.success(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,  # vertical layout
            duration=duration,
            parent=parent,
        ).show()

    @staticmethod
    def show_error_infobar(self: QWidget, title: str, content: str, duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.error(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,  # vertical layout
            duration=duration,
            parent=parent,
        ).show()

    @staticmethod
    def show_warning_infobar(self: QWidget, title: str, content: str, duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.warning(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,  # vertical layout
            duration=duration,
            parent=parent,
        ).show()

    @staticmethod
    def show_info_infobar(self: QWidget, title: str, content: str, duration=2000):
        parent = self.window() if self.window() else self
        InfoBar.info(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            orient=Qt.Orientation.Vertical,  # vertical layout
            duration=duration,
            parent=parent,
        ).show()

    @staticmethod
    def truncate_middle(text, max_len=40):
        """超过max_len时，中间显示省略号"""
        if len(text) <= max_len:
            return text
        # 首尾各保留一半长度（预留3个字符给...）
        half = (max_len - 3) // 2
        return f"{text[:half]}...{text[-half:]}"

    @staticmethod
    def isWin11():
        return sys.platform == "win32" and sys.getwindowsversion().build >= 22000

    @staticmethod
    def user_path(relative_path):
        """
        获取用户文件
        """
        app_name, _, author_name = Utils.get_app_info()
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller 打包后的路径
            data_dir = Path(platformdirs.user_data_dir(app_name, author_name))
        else:
            current_script_path = Path(__file__).resolve()
            data_dir = Path.joinpath(current_script_path.parent.parent.parent, "user")
        data_dir.mkdir(parents=True, exist_ok=True)
        return Path.joinpath(data_dir, relative_path)

    @staticmethod
    def app_root_path(relative_path=""):
        """
        获取程序的【安装根目录】（即 exe 所在的文件夹）。
        用于寻找 updater.exe、配置文件等放在外部的文件。
        """
        if getattr(sys, "frozen", False):
            # 【打包环境】
            base_path = Path(sys.executable).parent
        else:
            # 【开发环境】
            base_path = Path(__file__).resolve().parent.parent.parent

        return Path(base_path).joinpath(relative_path)

    @staticmethod
    def resource_path(relative_path):
        """
        获取app的绝对路径，无论是在开发环境还是在 PyInstaller 打包后。
        """
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller 打包后的路径
            # sys._MEIPASS 是 PyInstaller 在运行时创建的临时文件夹
            base_path = Path(sys._MEIPASS)
        else:
            # 1. 获取当前脚本（main.py）的绝对路径
            current_script_path = Path(__file__).resolve()  # resolve() 确保是绝对路径
            base_path = current_script_path.parent.parent.parent
        return Path.joinpath(base_path, relative_path)

    @staticmethod
    def right_elide_label(label: QLabel) -> None:
        ori_text = label.text()
        wrap_text = label.fontMetrics().elidedText(
            ori_text, Qt.TextElideMode.ElideRight, label.width()
        )
        label.setText(wrap_text)
        label.setProperty("ori_text", ori_text)

    @staticmethod
    def elide_label_handle_resize(label: QLabel) -> None:
        ori_text = label.property("ori_text")
        wrap_text = label.fontMetrics().elidedText(
            ori_text, Qt.TextElideMode.ElideRight, label.width()
        )
        label.setText(wrap_text)

    @staticmethod
    # --- 新增：排序键获取方法 ---
    def _get_path_sort_key(path: Path) -> str:
        """
        获取用于排序的键：
        - 中文：返回第一个字的拼音首字母 (小写)
        - 英文/其他：返回文件名的第一个字符 (小写)
        """
        name = path.name
        if not name:
            return ""

        first_char = name[0]

        # 检查是否为中文字符 (基本范围)
        if "\u4e00" <= first_char <= "\u9fff":
            try:
                # 获取拼音
                pinyin_list = pinyin(first_char, style=Style.FIRST_LETTER)
                if pinyin_list:
                    return pinyin_list[0][0].lower()
                else:
                    return first_char.lower()  # 罕见情况回退
            except Exception:
                return first_char.lower()  # 异常时回退
        else:
            # 非中文，直接用首字母小写
            return first_char.lower()

    @staticmethod
    def sort_path_list_by_name(paths: list[Path]) -> list[Path]:
        return sorted(paths, key=Utils._get_path_sort_key)

    @staticmethod
    def get_app_info():
        try:
            with open(
                Utils.resource_path("resources/app_info.json"), encoding="utf-8"
            ) as f:
                app_info = json.load(f)
        except:
            app_info = {}
        app_info = app_info if isinstance(app_info, dict) else {}
        version = app_info.get("version", "1.0.0")
        author = app_info.get("author", "fanfanffy163")
        app_name = app_info.get("app_name", "midi-player")
        return app_name, version, author

    @staticmethod
    def get_install_path_by_name(target_name):
        """
        全范围扫描注册表（包含当前用户 HKCU 和 系统 HKLM）寻找软件安装路径。

        :param target_name: 软件名称关键词
        :return: 安装目录绝对路径 (str) 或 None
        """
        target_name_lower = target_name.lower()

        # 定义要扫描的 (根键, 路径) 组合列表
        # 优先级：先扫当前用户(HKCU)，再扫系统(HKLM)，最后扫兼容层
        search_scope = [
            # 1. 当前用户 (HKEY_CURRENT_USER)
            # 很多选择 "Only for me" 安装的软件都在这里
            (
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
            # 2. 系统范围 (HKEY_LOCAL_MACHINE) - 64位视图
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
            # 3. 系统范围 (HKEY_LOCAL_MACHINE) - 32位视图 (WOW6432Node)
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ),
        ]

        found_path = None

        for root_key, sub_path in search_scope:
            try:
                # 打开指定的注册表路径
                # 关键：OpenKey 的第一个参数是 root_key (HKCU 或 HKLM)
                key = winreg.OpenKey(root_key, sub_path)

                # 获取子键数量
                key_count = winreg.QueryInfoKey(key)[0]

                for i in range(key_count):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        full_subkey_path = sub_path + "\\" + subkey_name

                        subkey = winreg.OpenKey(root_key, full_subkey_path)

                        try:
                            # 1. 匹配 DisplayName
                            display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")

                            if target_name_lower in display_name.lower():
                                # 2. 尝试获取 InstallLocation
                                # 注意：有些软件（如 Steam 游戏）可能不写 InstallLocation，
                                # 只写 UninstallString，这种情况比较复杂，暂不处理。
                                try:
                                    install_loc, _ = winreg.QueryValueEx(
                                        subkey, "InstallLocation"
                                    )

                                    # 清理路径中的引号 (有些安装包会写成 "C:\Path")
                                    clean_path = install_loc.strip('"').strip()

                                    if clean_path and Path.exists(clean_path):
                                        found_path = clean_path
                                        # 打印调试信息，让你知道是在哪里找到的
                                        hive_name = (
                                            "HKCU"
                                            if root_key == winreg.HKEY_CURRENT_USER
                                            else "HKLM"
                                        )
                                        logger.debug(
                                            f"✅ 在 [{hive_name}] 中命中: {display_name}"
                                        )
                                        break
                                except FileNotFoundError:
                                    pass  # 没写安装路径

                        except FileNotFoundError:
                            pass  # 没写显示名称
                        finally:
                            winreg.CloseKey(subkey)

                    except Exception:
                        continue

                winreg.CloseKey(key)

                if found_path:
                    break  # 找到了就停止所有扫描

            except Exception as e:
                # 某些键可能不存在（比如干净的系统可能没有 WOW6432Node 里的某些项），忽略错误
                continue

        return found_path

    @staticmethod
    def get_audiveris_by_file_omr_ext():
        try:
            # 1. 查 .omr 对应什么类型 (ProgID)
            # 路径: HKCR\.omr
            key_ext = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".omr")
            prog_id = winreg.QueryValue(key_ext, None)  # 读取默认值
            winreg.CloseKey(key_ext)

            if prog_id:
                # 2. 查 ProgID 对应的打开命令
                # 路径: HKCR\<ProgID>\shell\open\command
                cmd_path = f"{prog_id}\\shell\\open\\command"
                key_cmd = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, cmd_path)
                command_str = winreg.QueryValue(key_cmd, None)
                winreg.CloseKey(key_cmd)

                # shlex.split 可以正确处理引号，比如 "C:\Program Files\..."
                parts = shlex.split(command_str)
                if parts:
                    exe_path = parts[0]  # 第一个部分通常是 exe 路径
                    if "Audiveris" in exe_path and os.path.exists(exe_path):
                        logger.debug(f"✅ 通过文件关联找到: {exe_path}")
                        return exe_path
        except Exception as e:
            logger.debug(f"文件关联搜索未命中: {e}")
