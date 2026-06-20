"""
UI 主界面模块 — 使用 customtkinter 构建整个用户界面
设计目标：轻量插件感，不干扰日常使用
"""

import customtkinter as ctk
import pyperclip
import os
from datetime import datetime
from PIL import Image


# ========== 设计规范色彩常量 ==========
COLOR_PRIMARY = "#A8D8EA"
COLOR_PRIMARY_DARK = "#7CB8D0"
COLOR_PINNED_BG = "#D6EEF5"
COLOR_CARD_BG = "#FFFFFF"
COLOR_WINDOW_BG = "#F0F5F8"
COLOR_TEXT_MAIN = "#333333"
COLOR_TEXT_SECONDARY = "#888888"
COLOR_BORDER = "#E0E0E0"
COLOR_DELETE = "#FF6B6B"

# ========== 尺寸常量（缩小版） ==========
WINDOW_WIDTH = 360
WINDOW_HEIGHT = 480
WINDOW_MIN_WIDTH = 300
WINDOW_MIN_HEIGHT = 350
CARD_PADDING = 8
CARD_GAP = 5
CARD_RADIUS = 8
HEADER_HEIGHT = 32
IMAGE_THUMB_WIDTH = 90
IMAGE_THUMB_HEIGHT = 60
TEXT_PREVIEW_MAX = 50


class ToastNotification(ctk.CTkToplevel):
    """独立置顶弹窗提示 — 始终在最前，2秒后自动消失"""

    def __init__(self, parent, message: str, duration: int = 1800):
        super().__init__(parent)
        self.overrideredirect(True)  # 无边框
        self.attributes("-topmost", True)

        # 半透明深色背景
        self.configure(fg_color=COLOR_TEXT_MAIN)
        self.attributes("-alpha", 0.92)

        label = ctk.CTkLabel(
            self, text=message, text_color="#FFFFFF",
            font=ctk.CTkFont(size=12)
        )
        label.pack(padx=14, pady=7)

        # 定位于父窗口底部居中
        self.after(30, lambda: self._position(parent))
        self.after(duration, self.destroy)

    def _position(self, parent):
        """定位到父窗口底部居中"""
        try:
            pw = parent.winfo_width()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            ph = parent.winfo_height()
            self.update_idletasks()
            w = self.winfo_reqwidth()
            h = self.winfo_reqheight()
            x = px + (pw - w) // 2
            y = py + ph - h - 40
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass


class HistoryCard(ctk.CTkFrame):
    """单条历史记录卡片 — 悬停显示操作按钮"""

    def __init__(self, parent, record: dict, on_click=None, on_pin=None, on_delete=None):
        super().__init__(
            parent,
            fg_color=COLOR_PINNED_BG if record["pinned"] else COLOR_CARD_BG,
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.record = record
        self._on_click = on_click
        self._on_pin = on_pin
        self._on_delete = on_delete
        self._hovering = False

        self._build_ui()

        # 鼠标悬停事件
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", lambda e: self._handle_click())
        self.bind("<Double-Button-1>", lambda e: self._handle_double_click())

    def _build_ui(self):
        """构建卡片内部布局（更紧凑）"""
        # 主体横向容器
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=CARD_PADDING, pady=CARD_PADDING)

        # 左侧内容
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        if self.record["content_type"] == "image":
            self._build_image_preview(left)
        else:
            self._build_text_preview(left)

        # 时间戳
        ts = self._format_time(self.record["timestamp"])
        ctk.CTkLabel(
            left, text=ts, text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=10), anchor="w"
        ).pack(anchor="w", pady=(1, 0))

        # 右侧按钮区（默认隐藏，悬停显示）
        self.btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.btn_frame.pack(side="right", fill="y")

        pin_char = "📌" if self.record["pinned"] else "📍"
        self.pin_btn = ctk.CTkButton(
            self.btn_frame, text=pin_char, width=24, height=24,
            fg_color="transparent", hover_color=COLOR_PRIMARY,
            text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(size=10),
            command=self._handle_pin
        )
        self.pin_btn.pack(pady=(0, 2))

        self.del_btn = ctk.CTkButton(
            self.btn_frame, text="✕", width=24, height=24,
            fg_color="transparent", hover_color=COLOR_DELETE,
            text_color=COLOR_TEXT_SECONDARY, font=ctk.CTkFont(size=11),
            command=self._handle_delete
        )
        self.del_btn.pack()

        # 初始隐藏按钮
        self._hide_buttons()

    def _build_text_preview(self, parent):
        text = (self.record.get("text_content", "") or "").replace("\n", " ")
        if len(text) > TEXT_PREVIEW_MAX:
            text = text[:TEXT_PREVIEW_MAX] + "…"

        lbl = ctk.CTkLabel(
            parent, text=text, text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(size=12), anchor="w", justify="left",
            wraplength=240
        )
        lbl.pack(anchor="w", fill="x")
        lbl.bind("<Button-1>", lambda e: self._handle_click())
        lbl.bind("<Double-Button-1>", lambda e: self._handle_double_click())

    def _build_image_preview(self, parent):
        path = self.record.get("image_path", "")
        placeholder = ctk.CTkLabel(
            parent, text="🖼 图片", text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=12), anchor="w"
        )
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                img.thumbnail((IMAGE_THUMB_WIDTH, IMAGE_THUMB_HEIGHT), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img,
                                       size=(img.width, img.height))
                il = ctk.CTkLabel(parent, image=ctk_img, text="")
                il.pack(anchor="w")
                il.bind("<Button-1>", lambda e: self._handle_click())
                il.bind("<Double-Button-1>", lambda e: self._handle_double_click())
                return
            except Exception:
                pass
        placeholder.pack(anchor="w")
        placeholder.bind("<Button-1>", lambda e: self._handle_click())

    def _show_buttons(self):
        for w in self.btn_frame.winfo_children():
            w.pack()
        self.pin_btn.pack(pady=(0, 2))
        self.del_btn.pack()

    def _hide_buttons(self):
        for w in self.btn_frame.winfo_children():
            w.pack_forget()

    def _on_enter(self, _e):
        self._hovering = True
        self._show_buttons()

    def _on_leave(self, _e):
        self._hovering = False
        self._hide_buttons()

    def _handle_click(self):
        if self._on_click:
            self._on_click(self.record)

    def _handle_double_click(self):
        if self._on_click:
            self._on_click(self.record, minimize=True)

    def _handle_pin(self):
        if self._on_pin:
            self._on_pin(self.record)

    def _handle_delete(self):
        if self._on_delete:
            self._on_delete(self.record)

    @staticmethod
    def _format_time(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str)
            diff = datetime.now() - dt
            s = diff.total_seconds()
            if s < 60:  return "刚刚"
            if s < 3600: return f"{int(s // 60)}分前"
            if s < 86400: return f"{int(s // 3600)}时前"
            if dt.date() == datetime.now().date(): return f"今天 {dt:%H:%M}"
            if (datetime.now() - diff).days <= 1: return f"昨天 {dt:%H:%M}"
            return dt.strftime("%m-%d %H:%M")
        except Exception:
            return iso_str


class SettingsDialog(ctk.CTkToplevel):
    """设置弹窗"""

    def __init__(self, parent, settings, on_save=None, on_clear_all=None):
        super().__init__(parent)
        self.title("设置")
        self.geometry("300x250")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._settings = settings
        self._on_save = on_save
        self._on_clear_all = on_clear_all

        self.after(30, lambda: self._center(parent))
        self._build_ui()

    def _center(self, parent):
        try:
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            self.update_idletasks()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        except Exception:
            pass

    def _build_ui(self):
        ctk.CTkLabel(self, text="设置", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=COLOR_TEXT_MAIN).pack(pady=(16, 10))

        # 保留期限
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        ctk.CTkLabel(row, text="保留期限：", font=ctk.CTkFont(size=12),
                     text_color=COLOR_TEXT_MAIN).pack(side="left", padx=(0, 8))

        options = ["1 天", "3 天", "5 天", "不限"]
        values = [1, 3, 5, 0]
        cur = self._settings.retention_days
        idx = values.index(cur) if cur in values else 1
        self.retention_var = ctk.StringVar(value=options[idx])
        ctk.CTkOptionMenu(
            row, values=options, variable=self.retention_var,
            fg_color=COLOR_PRIMARY, button_color=COLOR_PRIMARY_DARK,
            button_hover_color=COLOR_PRIMARY_DARK,
            text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(size=12), width=80
        ).pack(side="left")

        # 保存
        ctk.CTkButton(
            self, text="保存设置", command=self._save,
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_DARK,
            text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(size=12), width=100
        ).pack(pady=(14, 4))

        # 分隔线 + 清空按钮
        sep = ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", padx=30, pady=(8, 4))

        ctk.CTkButton(
            self, text="清空全部历史", command=self._confirm_clear,
            fg_color="transparent", border_width=1, border_color=COLOR_DELETE,
            hover_color="#FFF0F0", text_color=COLOR_DELETE,
            font=ctk.CTkFont(size=12), width=130
        ).pack(pady=(2, 10))

    def _save(self):
        mapping = {"1 天": 1, "3 天": 3, "5 天": 5, "不限": 0}
        self._settings.retention_days = mapping.get(self.retention_var.get(), 3)
        if self._on_save:
            self._on_save(self._settings.retention_days)
        self.destroy()

    def _confirm_clear(self):
        ConfirmDialog(
            self, "清空全部", "确定要删除所有历史记录吗？\n此操作不可恢复！",
            on_confirm=lambda: self._do_clear()
        )

    def _do_clear(self):
        if self._on_clear_all:
            self._on_clear_all()
        self.destroy()


class ConfirmDialog(ctk.CTkToplevel):
    """确认对话框"""

    def __init__(self, parent, title: str, message: str, on_confirm=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("280x140")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.after(30, lambda: self._center(parent))

        ctk.CTkLabel(self, text=message, font=ctk.CTkFont(size=13),
                     text_color=COLOR_TEXT_MAIN, wraplength=250
                     ).pack(pady=(24, 12))

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack()
        ctk.CTkButton(bf, text="取消", command=self.destroy,
                      fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(size=12), width=80
                      ).pack(side="left", padx=(0, 12))
        ctk.CTkButton(bf, text="确认", command=lambda: self._fire(on_confirm),
                      fg_color=COLOR_DELETE, hover_color="#E05555",
                      text_color="#FFFFFF", font=ctk.CTkFont(size=12), width=80
                      ).pack(side="left")

    def _center(self, parent):
        try:
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            self.update_idletasks()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        except Exception:
            pass

    def _fire(self, cb):
        if cb:
            cb()
        self.destroy()


# ====================================================================
#  主窗口
# ====================================================================

class MainWindow(ctk.CTk):
    """主窗口 — 轻量插件风格"""

    def __init__(self, database, settings, monitor):
        super().__init__()
        self.db = database
        self.settings = settings
        self.monitor = monitor
        self.monitor.on_new_record = self._on_new_record

        self._cards: list[HistoryCard] = []
        self._search_var = ctk.StringVar()
        self._always_on_top = False

        self._setup_window()
        self._build_ui()
        self._bind_keys()
        self._load_records()

        # 自动聚焦搜索框
        self.after(150, lambda: self.search_entry.focus_set())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ====== 窗口设置 ======

    def _setup_window(self):
        self.title("历史粘贴板")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLOR_WINDOW_BG)
        self.after(30, self._center_window)

    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # 偏右上角，不挡屏幕中心
        x = sw - w - 60
        y = (sh - h) // 3
        self.geometry(f"+{x}+{y}")

    def _bind_keys(self):
        """键盘快捷键"""
        self.bind("<Escape>", lambda e: self.iconify())         # Esc → 最小化
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())  # Ctrl+F → 搜索
        self.bind("<Control-l>", lambda e: self.search_entry.focus_set())  # Ctrl+L → 搜索

    # ====== UI 构建 ======

    def _build_ui(self):
        # ---- 顶栏 ----
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 3))

        # 窗口置顶切换按钮
        self.pin_win_btn = ctk.CTkButton(
            top, text="📌", width=HEADER_HEIGHT, height=HEADER_HEIGHT,
            fg_color="transparent", hover_color=COLOR_PRIMARY,
            text_color=COLOR_TEXT_SECONDARY, font=ctk.CTkFont(size=13),
            command=self._toggle_always_on_top
        )
        self.pin_win_btn.pack(side="left", padx=(0, 4))

        # 搜索框
        self.search_entry = ctk.CTkEntry(
            top, placeholder_text="搜索...",
            height=HEADER_HEIGHT, corner_radius=6,
            border_color=COLOR_BORDER, fg_color=COLOR_CARD_BG,
            text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(size=12),
            textvariable=self._search_var
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._search_var.trace_add("write", lambda *a: self._on_search())

        # 设置按钮
        ctk.CTkButton(
            top, text="⚙", width=HEADER_HEIGHT, height=HEADER_HEIGHT,
            fg_color="transparent", hover_color=COLOR_PRIMARY,
            text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(size=15),
            command=self._open_settings
        ).pack(side="right")

        # ---- 卡片区 ----
        self.card_container = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLOR_PRIMARY,
            scrollbar_button_hover_color=COLOR_PRIMARY_DARK
        )
        self.card_container.pack(fill="both", expand=True, padx=8, pady=(0, 3))

        self.empty_label = ctk.CTkLabel(
            self.card_container,
            text="暂无记录\nCtrl+C 复制内容试试",
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=13), justify="center"
        )

        # ---- 底栏 ----
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            bottom, text="共 0 条", text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=10)
        )
        self.status_label.pack(side="left")

        ctk.CTkButton(
            bottom, text="清空", width=40, height=20,
            fg_color="transparent", hover_color="#FFF0F0",
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(size=10),
            command=self._clear_all
        ).pack(side="right")

    # ====== 数据加载 ======

    def _load_records(self, search_query: str = ""):
        for card in self._cards:
            try:
                card.destroy()
            except Exception:
                pass
        self._cards.clear()

        records = self.db.get_records(search_query)

        if not records:
            self.empty_label.pack(expand=True)
        else:
            self.empty_label.pack_forget()
            for r in records:
                card = HistoryCard(
                    self.card_container, r,
                    on_click=self._on_card_click,
                    on_pin=self._on_card_pin,
                    on_delete=self._on_card_delete
                )
                card.pack(fill="x", pady=(0, CARD_GAP))
                self._cards.append(card)

        self._update_status(search_query)

    def _update_status(self, query: str = ""):
        total = self.db.get_count()
        shown = len(self._cards)
        if query:
            self.status_label.configure(text=f"{shown} / {total} 条匹配")
        else:
            self.status_label.configure(text=f"共 {total} 条")

    def _on_new_record(self):
        self.after(0, lambda: self._load_records(self._search_var.get()))

    def _on_search(self):
        self._load_records(self._search_var.get())

    # ====== 卡片操作 ======

    def _on_card_click(self, record: dict, minimize: bool = False):
        if record["content_type"] == "text":
            pyperclip.copy(record.get("text_content", ""))
            ToastNotification(self, "已复制 ✓")
        elif record["content_type"] == "image":
            path = record.get("image_path", "")
            if path and os.path.exists(path):
                ok = self._copy_image(path)
                ToastNotification(self, "图片已复制 ✓" if ok else "复制失败")
        if minimize:
            self.after(200, self.iconify)

    def _copy_image(self, image_path: str) -> bool:
        """Windows API 复制图片到剪贴板"""
        try:
            import ctypes
            from io import BytesIO

            img = Image.open(image_path).convert("RGB")
            buf = BytesIO()
            img.save(buf, format="BMP")
            dib = buf.getvalue()[14:]
            buf.close()

            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32

            if not u32.OpenClipboard(0):
                return False
            u32.EmptyClipboard()

            size = len(dib)
            hmem = k32.GlobalAlloc(0x0002, size)
            if hmem:
                ptr = k32.GlobalLock(hmem)
                ctypes.memmove(ptr, dib, size)
                k32.GlobalUnlock(hmem)
                u32.SetClipboardData(8, hmem)  # CF_DIB
            u32.CloseClipboard()
            return True
        except Exception as e:
            print(f"[图片复制] {e}")
            return False

    def _on_card_pin(self, record: dict):
        self.db.toggle_pin(record["id"])
        ToastNotification(self, "已置顶" if not record["pinned"] else "已取消置顶")
        self._load_records(self._search_var.get())

    def _on_card_delete(self, record: dict):
        ConfirmDialog(self, "确认删除", "确定删除这条记录吗？",
                      on_confirm=lambda: self._do_delete(record["id"]))

    def _do_delete(self, rid: int):
        self.db.delete_record(rid)
        self._load_records(self._search_var.get())
        ToastNotification(self, "已删除")

    def _clear_all(self):
        ConfirmDialog(self, "清空全部", "确定删除所有历史记录吗？",
                      on_confirm=self._do_clear_all)

    def _do_clear_all(self):
        records = self.db.get_records()
        for r in records:
            self.db.delete_record(r["id"])
        self._load_records()
        ToastNotification(self, "已全部清空")

    # ====== 设置 ======

    def _open_settings(self):
        SettingsDialog(
            self, self.settings,
            on_save=lambda d: self._on_settings_saved(d),
            on_clear_all=self._do_clear_all
        )

    def _on_settings_saved(self, retention_days: int):
        if retention_days > 0:
            self.db.cleanup_expired(retention_days)
        self._load_records(self._search_var.get())
        ToastNotification(self, f"已保存（保留 {self.settings.get_retention_label()}）")

    # ====== 窗口置顶 ======

    def _toggle_always_on_top(self):
        self._always_on_top = not self._always_on_top
        self.attributes("-topmost", self._always_on_top)
        color = COLOR_PRIMARY if self._always_on_top else COLOR_TEXT_SECONDARY
        self.pin_win_btn.configure(text_color=color)
        ToastNotification(self, "窗口置顶" if self._always_on_top else "取消置顶")

    # ====== 关闭 ======

    def _on_close(self):
        if self.settings.retention_days > 0:
            self.db.cleanup_expired(self.settings.retention_days)
        self.monitor.stop()
        self.destroy()
