"""
剪贴板监听模块 — 后台线程轮询剪贴板，自动记录文字和图片
"""

import threading
import time
import pyperclip
from PIL import ImageGrab


class ClipboardMonitor:
    """剪贴板监听器（后台线程）"""

    def __init__(self, database, poll_interval: float = 0.5):
        """
        database: ClipboardDatabase 实例
        poll_interval: 轮询间隔（秒），默认 0.5 秒
        """
        self.db = database
        self.poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None

        # 记录上次的内容，用于去重
        self._last_text: str | None = None
        self._last_image_hash: int | None = None

        # 回调：当新内容被记录时调用
        self.on_new_record: callable | None = None

    def start(self):
        """启动监听线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监听线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _poll_loop(self):
        """轮询主循环（运行在后台线程）"""
        while self._running:
            try:
                self._check_clipboard()
            except Exception as e:
                print(f"[监听] 轮询异常: {e}")
            time.sleep(self.poll_interval)

    def _check_clipboard(self):
        """检查剪贴板是否有新内容"""
        # 先检查图片（图片优先级高于文字）
        try:
            img = ImageGrab.grabclipboard()
            if img is not None and hasattr(img, "size"):
                # 计算图片哈希用于去重
                img_hash = hash(img.tobytes()[:1024])  # 取前1KB做哈希
                if img_hash != self._last_image_hash:
                    self._last_image_hash = img_hash
                    self.db.add_image(img)
                    self._notify()
                return  # 剪贴板是图片就不再检查文字
        except Exception:
            pass  # 没有图片或获取图片失败

        # 检查文字
        try:
            text = pyperclip.paste()
            if text and text.strip():
                text = text.strip()
                if text != self._last_text:
                    self._last_text = text
                    self.db.add_text(text)
                    self._notify()
        except Exception as e:
            print(f"[监听] 获取文字失败: {e}")

    def _notify(self):
        """通知 UI 有新记录（通过回调在主线程中刷新）"""
        if self.on_new_record:
            try:
                self.on_new_record()
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._running
