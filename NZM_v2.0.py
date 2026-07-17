import tkinter as tk
import pyautogui
import threading
from pynput import mouse, keyboard
import time
import gc

# ===================== 全局前置优化：PyAutoGUI 底层降噪（必加） =====================
# 关闭角落安全触发（后台运行必备，减少检测开销）
pyautogui.FAILSAFE = False
# 关闭 PyAutoGUI 默认按键延时，由代码手动控制节奏（减少无效等待）
pyautogui.PAUSE = 0
# 关闭 PyAutoGUI 日志输出、截图缓存（大幅降低内存）
pyautogui.useImageNotFoundException = False


class AutoInputApp:

    def __init__(self, root):
        # 主窗口
        self.root = root
        self.root.title("键鼠自动化")
        self.root.geometry("300x100")
        self.root.resizable(False, False)  # 禁止窗口缩放，减少GUI重绘开销
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        # -------------------------- 状态标记（精简变量，无冗余） --------------------------
        # 三大任务运行标记
        self.attack_running = False
        self.walk_running = False

        # 鼠标全局状态（防 mouseDown/mouseUp 冲突，核心保留）
        # self.mouse_left_down = False
        # 新增：定时任务时间戳（记录每个任务的开始/结束时间）
        self.task_pause_time = 0.0
        # 线程安全锁（全局唯一，缩小锁作用域）
        self.thread_lock = threading.Lock()

        # -------------------------- 常驻线程（核心优化：启动时一次性创建，全程复用） --------------------------
        # 攻击常驻线程
        self.attack_thread = threading.Thread(target=self._attack_loop, daemon=True)
        # 移动常驻线程
        self.walk_thread = threading.Thread(target=self._walk_loop, daemon=True)

        # 启动所有常驻工作线程（只启动一次）
        self.attack_thread.start()
        self.walk_thread.start()

        # -------------------------- 键鼠监听（pynput 轻量化配置） --------------------------
        # 鼠标监听
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.mouse_listener.start()


        # -------------------------- GUI 轻量化布局（精简组件） --------------------------
        tk.Label(root, text="鼠标侧键1=攻击 | 鼠标侧键2=滑铲跳", font=("微软雅黑", 12), fg="green").pack(pady=(20, 5))
        # tk.Label(root, text="键盘 F9=普攻任务", font=("微软雅黑", 12), fg="blue").pack(pady=(0, 20))
        tk.Button(root, text="关闭程序", command=self.close_app, bg="red", fg="white", font=("微软雅黑", 11)).pack()

    # ==============================================================================
    # 通用鼠标安全方法（全局唯一入口，防按压冲突，无冗余逻辑）
    # ==============================================================================
    # def safe_mouse_down(self):
    #     while self.mouse_left_down:
    #         continue
    #     pyautogui.mouseDown()
    #     self.mouse_left_down = True
    #
    # def safe_mouse_up(self):
    #     if self.mouse_left_down:
    #         pyautogui.mouseUp()
    #         self.mouse_left_down = False

    # ==============================================================================
    # 键鼠监听回调（轻量化，精简判断、减少耗时调用）
    # ==============================================================================
    def _on_mouse_click(self, x, y, button, pressed):
        if not pressed:
            return

        if button == mouse.Button.x1:
            self.toggle_attack()
        elif button == mouse.Button.x2:
            self.toggle_walk()

    # ==============================================================================
    # 【常驻线程循环】三大任务核心逻辑（局部变量优化，降低属性查找开销）
    # 特点：线程永不销毁，仅靠 running 标记启停
    # ==============================================================================
    def _attack_loop(self):
        """攻击常驻循环（线程只创建一次）"""
        while True:
            if self.attack_running:
                pyautogui.press('1')
                while self.attack_running:
                    pyautogui.mouseDown()
                    time.sleep(0.5)
                    pyautogui.mouseUp()
                    if not self.attack_running:
                        break
                    time.sleep(0.05)
                    pyautogui.mouseDown(button = 'right')
                    time.sleep(0.2)
                    pyautogui.mouseUp(button = 'right')
                    if not self.attack_running:
                        break
                    time.sleep(0.4)
                    if not self.attack_running:
                        break
                    pyautogui.press('2')
                    time.sleep(0.05)
                    pyautogui.press('1')
                    time.sleep(0.1)
            # 空闲时低功耗休眠（避免空转占CPU）
            time.sleep(0.2)

    def _walk_loop(self):
        """移动常驻循环（线程只创建一次）"""
        while True:
            if self.walk_running:
                pyautogui.press('3')
                pyautogui.keyDown('w')
                time.sleep(0.3)
                while self.walk_running:
                    pyautogui.press('ctrl')
                    time.sleep(0.08)
                    if not self.walk_running:
                        break
                    pyautogui.press('space',2,0.75)
                    if not self.walk_running:
                        break
                    pyautogui.keyDown('w')
                    time.sleep(0.45)
            time.sleep(0.2)


    # ==============================================================================
    # 任务开关（互斥逻辑保留 + 缩小锁范围，减少线程竞争）
    # 功能：切换任务时自动停止其他所有任务，保证键鼠不冲突
    # ==============================================================================
    def toggle_attack(self):
        with self.thread_lock:
            # 互斥：停止另外两个任务
            self.walk_running = False
            # 切换当前任务状态
            self.attack_running = not self.attack_running

    def toggle_walk(self):
        with self.thread_lock:
            self.attack_running = False
            self.walk_running = not self.walk_running



    # ==============================================================================
    # 程序关闭（资源彻底释放 + 仅最后一次GC）
    # ==============================================================================
    def close_app(self):
        # 1. 终止所有任务
        with self.thread_lock:
            self.attack_running = False
            self.walk_running = False


        # 2. 兜底释放w
        pyautogui.keyUp('w')
        pyautogui.mouseUp()
        # 3. 停止鼠标监听线程，防止后台残留
        self.mouse_listener.stop()
        # 4. 销毁GUI窗口
        self.root.quit()
        self.root.destroy()

        # 5. 最后执行一次垃圾回收（仅退出时调用，全程仅此一处）
        gc.collect()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoInputApp(root)
    root.mainloop()