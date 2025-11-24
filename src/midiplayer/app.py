import sys

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
    logger.add(
        sys.stderr,
        level="DEBUG",
        diagnose=True,
    )
    logger.add(
        Utils.app_root_path("log") / "{time}.log",
        rotation="20 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        level="INFO",
    )
    logger.info("app starting...")

    # 窗口
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
