"""
历史粘贴板 — 主入口
Windows 剪贴板历史管理软件
"""

import sys
import os
import ctypes
from database import ClipboardDatabase
from settings import AppSettings
from clipboard_monitor import ClipboardMonitor


def check_single_instance() -> bool:
    """
    检查是否已有实例在运行
    使用 Windows mutex 机制防止重复打开
    """
    try:
        mutex_name = "Global\\ClipHistoryApp_SingleInstance"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
        return True
    except Exception:
        # 非 Windows 或获取失败时允许运行
        return True


def main():
    """主函数"""
    # 1. 单实例检查
    if not check_single_instance():
        ctypes.windll.user32.MessageBoxW(
            0, "软件已在运行中！\n请查看任务栏。", "历史粘贴板", 0x40
        )
        sys.exit(0)

    # 2. 初始化数据层
    db = ClipboardDatabase()
    settings = AppSettings()
    print(f"[启动] 数据库: {db.db_path}")
    print(f"[启动] 保留期限: {settings.get_retention_label()}")

    # 3. 启动时清理过期记录
    if settings.retention_days > 0:
        db.cleanup_expired(settings.retention_days)

    # 4. 启动剪贴板监听
    monitor = ClipboardMonitor(db, poll_interval=0.5)
    monitor.start()
    print("[启动] 剪贴板监听已启动")

    # 5. 启动 UI（这会阻塞主线程直到窗口关闭）
    from main_window import MainWindow
    app = MainWindow(db, settings, monitor)
    app.mainloop()

    print("[退出] 历史粘贴板已关闭")


if __name__ == "__main__":
    main()
