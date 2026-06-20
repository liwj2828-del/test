import webview
import os
import sys
import json
import ctypes
from ctypes import wintypes

# ── Win32 helpers ──────────────────────────────────────────────
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def get_screen_work_area():
    """Get the working area (excludes taskbar) of the primary monitor."""
    rect = RECT()
    # SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return {"left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom}


def _set_topmost(hwnd: int, top: bool) -> None:
    """Set or clear the WS_EX_TOPMOST style via SetWindowPos."""
    flag = HWND_TOPMOST if top else HWND_NOTOPMOST
    user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)


# ── Paths ──────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BASE_DIR

BALL_HTML_PATH = os.path.join(BASE_DIR, 'ball.html')
PANEL_HTML_PATH = os.path.join(BASE_DIR, 'app.html')
SETTINGS_FILE = os.path.join(EXE_DIR, 'todo_settings.json')


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'on_top': True, 'badge_count': 0,
                'ball_x': None, 'ball_y': None}


def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False)
    except Exception:
        pass


# ── API Classes ─────────────────────────────────────────────────

class BallAPI:
    """JS bridge for the floating ball window."""

    def __init__(self) -> None:
        self._ball: webview.Window | None = None
        self._panel: webview.Window | None = None
        self._settings: dict = {}

    def set_windows(self, ball: webview.Window, panel: webview.Window) -> None:
        self._ball = ball
        self._panel = panel

    def set_settings(self, settings: dict) -> None:
        self._settings = settings

    def expand(self) -> None:
        """Hide ball, position and show panel near ball."""
        if self._ball is None or self._panel is None:
            return

        ball_x = self._ball.x
        ball_y = self._ball.y
        ball_w = self._ball.width
        ball_h = self._ball.height

        panel_w = self._panel.width
        panel_h = self._panel.height

        gap = 8

        # Default: place panel right of ball, vertically centered
        panel_x = ball_x + ball_w + gap
        panel_y = ball_y + ball_h // 2 - panel_h // 2

        # Clamp to screen work area
        wa = get_screen_work_area()
        if panel_x + panel_w > wa['right']:
            panel_x = ball_x - panel_w - gap  # place left
        if panel_x < wa['left']:
            panel_x = wa['left'] + gap
        if panel_y < wa['top']:
            panel_y = wa['top'] + gap
        if panel_y + panel_h > wa['bottom']:
            panel_y = wa['bottom'] - panel_h - gap

        # Persist ball position before hiding
        self._settings['ball_x'] = ball_x
        self._settings['ball_y'] = ball_y

        self._ball.hide()
        self._panel.move(panel_x, panel_y)
        self._panel.show()

    def move_ball(self, x: int, y: int) -> None:
        """Move the ball window to the given screen coordinates."""
        if self._ball is not None:
            self._ball.move(int(x), int(y))

    def get_badge_count(self) -> int:
        """Return the incomplete task count (for ball init)."""
        return self._settings.get('badge_count', 0)


class PanelAPI:
    """JS bridge for the todo panel window."""

    def __init__(self) -> None:
        self._ball: webview.Window | None = None
        self._panel: webview.Window | None = None
        self._settings: dict = {}
        self._hwnd: int | None = None

    def set_windows(self, ball: webview.Window, panel: webview.Window) -> None:
        self._ball = ball
        self._panel = panel

    def set_settings(self, settings: dict) -> None:
        self._settings = settings

    def _ensure_hwnd(self) -> int | None:
        """Get panel HWND via pywebview's native handle."""
        if self._hwnd is None and self._panel is not None:
            try:
                self._hwnd = self._panel.native.Handle.ToInt32()
            except Exception:
                pass
        return self._hwnd

    def collapse(self) -> None:
        """Hide panel, show ball."""
        if self._panel:
            self._panel.hide()
        if self._ball:
            self._ball.show()

    def sync_badge_count(self, count: int) -> None:
        """Called from panel JS whenever tasks change.
        Stores count in settings and pushes to ball window."""
        if self._settings is not None:
            self._settings['badge_count'] = int(count)
        # Push to ball window via evaluate_js
        if self._ball is not None:
            try:
                self._ball.evaluate_js(f'setBadgeCount({int(count)})')
            except Exception:
                pass

    def toggle_on_top(self) -> bool:
        """Toggle always-on-top for the panel. Returns new state."""
        hwnd = self._ensure_hwnd()
        if hwnd is None:
            return self._settings.get('on_top', True)

        new_state = not self._settings.get('on_top', True)
        _set_topmost(hwnd, new_state)
        self._settings['on_top'] = new_state
        return new_state

    def get_on_top(self) -> bool:
        return self._settings.get('on_top', True)

    def minimize_window(self) -> None:
        """Minimize becomes collapse in dual-window mode."""
        self.collapse()

    def close_window(self) -> None:
        """Close both windows and exit."""
        save_settings(self._settings)
        if self._panel:
            self._panel.destroy()
        if self._ball:
            self._ball.destroy()


# ── Main ────────────────────────────────────────────────────────

def on_ball_closed():
    """Called when the ball window is closed by the user."""
    save_settings(load_settings())


def main() -> None:
    settings = load_settings()

    ball_api = BallAPI()
    panel_api = PanelAPI()

    ball_api.set_settings(settings)
    panel_api.set_settings(settings)

    # Initial ball position
    ball_start_x = settings.get('ball_x')
    ball_start_y = settings.get('ball_y')
    if ball_start_x is None or ball_start_y is None:
        # Default: near top-right corner of work area
        wa = get_screen_work_area()
        ball_start_x = wa['right'] - 80
        ball_start_y = wa['top'] + 40

    # ── Ball window (MASTER) ──
    ball_window = webview.create_window(
        title='待办事项-浮球',
        url=BALL_HTML_PATH,
        js_api=ball_api,
        width=60,
        height=60,
        x=ball_start_x,
        y=ball_start_y,
        frameless=True,
        easy_drag=False,
        transparent=True,
        on_top=True,
        resizable=False,
        text_select=False,
        shadow=False,
    )

    # ── Panel window (CHILD) ──
    panel_window = webview.create_window(
        title='待办事项',
        url=PANEL_HTML_PATH,
        js_api=panel_api,
        width=340,
        height=420,
        min_size=(300, 360),
        resizable=True,
        frameless=True,
        easy_drag=False,
        transparent=True,
        on_top=settings.get('on_top', True),
        text_select=False,
        shadow=False,
    )

    # Wire windows into APIs
    ball_api.set_windows(ball_window, panel_window)
    panel_api.set_windows(ball_window, panel_window)

    # Hide panel immediately after it's created
    def hide_panel():
        panel_window.hide()

    panel_window.events.shown += hide_panel

    # Save settings on close (ball is master, closes last)
    ball_window.events.closed += on_ball_closed

    webview.start(debug=False, private_mode=False)


if __name__ == '__main__':
    main()
