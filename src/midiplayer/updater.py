import ctypes
import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import zipfile
from tkinter import ttk


# ----------------- 工具函数 -----------------
def is_pid_running(pid):
    """检查 PID 是否存活"""
    if pid <= 0:
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        process = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if process != 0:
            kernel32.CloseHandle(process)
            return True
        return False
    except:
        return False


def log(msg):
    # 调试用，实际可去掉
    with open(os.path.join(tempfile.gettempdir(), "updater_log.txt"), "a") as f:
        f.write(f"{msg}\n")


# ----------------- UI 和 业务逻辑 -----------------
def install_and_restart(zip_path, install_dir, main_exe, wait_pid):
    root = tk.Tk()
    root.title("更新程序")

    # 屏幕居中
    w, h = 300, 120
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws / 2) - (w / 2)
    y = (hs / 2) - (h / 2)
    root.geometry("%dx%d+%d+%d" % (w, h, x, y))
    root.resizable(False, False)

    lbl_status = tk.Label(root, text="正在等待程序关闭...", font=("Arial", 10))
    lbl_status.pack(pady=15)

    progress = ttk.Progressbar(root, length=250, mode="indeterminate")
    progress.pack(pady=5)
    progress.start(15)

    def task():
        try:
            # 1. 死等 PID 消失 (最多等 10秒)
            timeout = 20
            while is_pid_running(wait_pid) and timeout > 0:
                time.sleep(0.5)
                timeout -= 1

            if is_pid_running(wait_pid):
                lbl_status.config(text="错误：主程序无法退出，更新取消")
                root.after(3000, root.destroy)
                return

            # 2. 解压覆盖
            lbl_status.config(text="正在安装更新...")
            root.update()

            if not os.path.exists(zip_path):
                lbl_status.config(text="错误：找不到更新包")
                root.after(3000, root.destroy)
                return

            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(install_dir)
            except Exception as e:
                lbl_status.config(text=f"解压失败: {str(e)[:15]}...")
                root.after(3000, root.destroy)
                return

            # 3. 清理 Zip
            try:
                os.remove(zip_path)
            except:
                pass

            # 4. 重启主程序
            lbl_status.config(text="更新完成，正在启动...")
            root.update()
            time.sleep(1)

            target_exe = os.path.join(install_dir, main_exe)
            if os.path.exists(target_exe):
                subprocess.Popen([target_exe])

            root.destroy()

        except Exception as e:
            lbl_status.config(text=f"未知错误: {e}")

    # 100ms 后开始执行任务
    root.after(100, task)
    root.mainloop()


if __name__ == "__main__":
    # 参数顺序: script.py [zip_path] [install_dir] [main_exe] [pid]
    if len(sys.argv) >= 5:
        _zip_path = sys.argv[1]
        _install_dir = sys.argv[2]
        _main_exe = sys.argv[3]
        _pid = int(sys.argv[4])

        install_and_restart(_zip_path, _install_dir, _main_exe, _pid)
