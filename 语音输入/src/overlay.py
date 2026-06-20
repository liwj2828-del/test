"""浮动按钮 + 托盘 — emoji 纯色版"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QLabel,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QRect
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QBrush, QAction, QFont, QRegion,
)

STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_PROCESSING = "processing"
STATE_DONE = "done"

EMOJI = {
    STATE_IDLE: "🎤",
    STATE_RECORDING: "🔴",
    STATE_PROCESSING: "⏳",
    STATE_DONE: "✅",
}

COLORS_BG = {
    STATE_IDLE: "#4a4a4a",
    STATE_RECORDING: "#dc2828",
    STATE_PROCESSING: "#dcaa1e",
    STATE_DONE: "#28b44c",
}

TOOLTIP = {
    STATE_IDLE: "点击开始录音 🎤",
    STATE_RECORDING: "录音中...点击停止 🔴",
    STATE_PROCESSING: "识别中... ⏳",
    STATE_DONE: "完成! ✅",
}


def _tray_icon(size=64):
    """画一个简单的麦克风图标"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(60, 60, 60)))
    p.setPen(Qt.PenStyle.NoPen)
    cx, cy = size // 2, size // 2
    p.drawRoundedRect(cx - 12, cy - 19, 24, 29, 8, 8)
    p.drawRoundedRect(cx - 18, cy + 4, 36, 13, 5, 5)
    p.drawRect(cx - 20, cy + 17, 40, 6)
    p.end()
    return QIcon(pixmap)


class MicButton(QWidget):
    """浮动圆形按钮 — emoji + 纯色背景，不用半透明"""
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # ❌ 不用 WA_TranslucentBackground —— Windows 上某些显卡/驱动会渲染异常
        self.setFixedSize(100, 100)

        # 圆形遮罩（真正裁切为圆形）
        mask = QRegion(QRect(0, 0, 100, 100), QRegion.RegionType.Ellipse)
        self.setMask(mask)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Emoji 标签
        self._label = QLabel(EMOJI[STATE_IDLE], self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI", 38)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self._label.setFont(font)
        self._label.setFixedSize(100, 100)
        self._label.setStyleSheet("background: transparent;")

        self._current_state = STATE_IDLE
        self._apply_style(STATE_IDLE)
        self.setGeometry(100, 100, 100, 100)

    def _apply_style(self, state):
        color = COLORS_BG.get(state, COLORS_BG[STATE_IDLE])
        # 纯色 background-color + 边框，不用 rgba 半透明
        self.setStyleSheet(
            f"MicButton {{ background-color: {color}; border: 2px solid #888; }}"
        )

    def set_state(self, state):
        self._current_state = state
        self._label.setText(EMOJI.get(state, EMOJI[STATE_IDLE]))
        self._apply_style(state)
        self.setToolTip(TOOLTIP.get(state, ""))
        self.show()
        self.raise_()  # 确保在最上层

        if state == STATE_DONE:
            QTimer.singleShot(1500, lambda: self.set_state(STATE_IDLE))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            QApplication.quit()


class SystemTray(QSystemTrayIcon):
    quit_requested = pyqtSignal()

    def __init__(self):
        super().__init__(_tray_icon())
        self.setToolTip("语音输入")
        menu = QMenu()
        self._status = QAction("🎤 就绪")
        self._status.setEnabled(False)
        menu.addAction(self._status)
        menu.addSeparator()
        menu.addAction("❌ 退出", self._on_quit)
        self.setContextMenu(menu)
        self.show()

    def _on_quit(self):
        self.quit_requested.emit()

    def update_status(self, state):
        labels = {
            STATE_IDLE: "🎤 就绪",
            STATE_RECORDING: "🔴 录音中",
            STATE_PROCESSING: "⏳ 识别中",
            STATE_DONE: "✅ 完成",
        }
        self._status.setText(labels.get(state, "🎤 就绪"))
        self.setToolTip(labels.get(state, "语音输入"))


class OverlayApp(QObject):
    state_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.mic_button = MicButton()
        self.tray = SystemTray()
        self.tray.quit_requested.connect(self._quit)

    def set_state(self, state):
        self.mic_button.set_state(state)
        self.tray.update_status(state)
        self.state_changed.emit(state)

    @property
    def state(self):
        return self._state if hasattr(self, '_state') else STATE_IDLE

    def _quit(self):
        self.mic_button.hide()
        QApplication.quit()
