from pynput.keyboard import Controller, Key
import time

# 初始化键盘控制器
keyboard = Controller()

# 等待3秒，手动切换到目标应用（如记事本）
print("5秒后开始模拟按键...")
time.sleep(5)

# 1. 模拟输入字母（如 PyQt6 的 Qt.Key.Key_A）

with keyboard.pressed(Key.shift):
    keyboard.press(',')
    keyboard.release(',')  # 等价于 Qt.Key.Key_A + Shift

# # 2. 模拟功能键（如 F5，对应 PyQt6 的 Qt.Key.Key_F5）
# keyboard.press(';')
# keyboard.release(';')

# # 3. 模拟修饰键组合（如 Ctrl+C，对应 Qt.Key.Key_Control + Qt.Key.Key_C）
# with keyboard.pressed(Key.ctrl):
#     keyboard.press('c')
#     keyboard.release('c')

# # 4. 模拟方向键（如下箭头，对应 Qt.Key.Key_Down）
# keyboard.press(Key.down)
# keyboard.release(Key.down)

# # 5. 模拟特殊键（如 Enter，对应 Qt.Key.Key_Enter）
# keyboard.press(Key.enter)
# keyboard.release(Key.enter)
