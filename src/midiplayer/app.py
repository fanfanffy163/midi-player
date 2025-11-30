import os
import shutil
import sys
import time

from loguru import logger
from PySide6.QtWidgets import QApplication

from midiplayer.core.component.main_window import MainWindow
from midiplayer.core.utils.utils import Utils


# 定义全局异常处理函数
def handle_exception(exc_type, exc_value, exc_traceback):
    # 忽略键盘中断（Ctrl+C）
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # 将异常信息记录到日志，opt(exception=...) 允许传入异常元组
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
        "发生未捕获的全局异常！程序即将崩溃。"
    )


def main():
    # 全局异常捕获
    sys.excepthook = handle_exception

    # 日志
    logger.remove()
    if sys.stderr:
        logger.add(
            sys.stderr,
            level="DEBUG",
            diagnose=True,
        )
    logger.add(
        Utils.user_path("log") / "{time}.log",
        rotation="20 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        level="INFO",
    )
    logger.info("app starting...")
    logger.info(f"应用启动参数 {sys.argv}")
    if len(sys.argv) >= 3:
        cmd = sys.argv[1]
        temp_path = sys.argv[2]
        if cmd == "update complete" and os.path.exists(temp_path):
            time.sleep(1)
            try:
                logger.info(f"删除更新临时文件夹 {temp_path}")
                shutil.rmtree(temp_path)
            except Exception as e:
                logger.opt(exception=e).error("删除更新文件夹出错")

    # 窗口
    app = QApplication(sys.argv)
    logger.info("MainWindow creating")
    window = MainWindow()
    logger.info("MainWindow created")
    window.show()
    sys.exit(app.exec())
