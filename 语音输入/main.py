#!/usr/bin/env python3
"""语音输入 — 🎤 点击录音 → 自动识别 → 粘贴

状态机：IDLE ⇄ RECORDING → PROCESSING → DONE → IDLE
处理中不可再点击，防止状态混乱。
"""

import sys
import time
import threading
from pathlib import Path

# 修复 Windows GBK 编码 — windowed 模式下 stdout 可能为 None
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 在 Qt 之前设置 DPI 感知，避免 PyInstaller 打包后报
# "SetProcessDpiAwarenessContext() failed: 拒绝访问"
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

sys.path.insert(0, str(Path(__file__).parent))

from src.recorder import VoiceRecorder
from src.stt_engine import STTEngine
from src.overlay import (
    OverlayApp, STATE_IDLE, STATE_RECORDING,
    STATE_PROCESSING, STATE_DONE,
)

import pyperclip
import pyautogui


class VoiceInputApp(QObject):
    _result_signal = pyqtSignal(str)
    _error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.overlay = OverlayApp()
        self.engine = STTEngine()
        self.recorder = VoiceRecorder()

        self._result_signal.connect(self._paste)
        self._error_signal.connect(self._on_error)

        self.overlay.mic_button.clicked.connect(self._on_click)

        self._model_ok = False
        self._current_state = STATE_IDLE

    # ── 状态管理 ──

    def _set_state(self, state):
        self._current_state = state
        self.overlay.set_state(state)

    # ── 点击处理 ──

    def _on_click(self):
        """按钮点击 → 根据当前状态执行动作"""
        s = self._current_state

        if s == STATE_IDLE:
            self._start_recording()

        elif s == STATE_RECORDING:
            self._stop_and_transcribe()

        elif s == STATE_PROCESSING:
            # 识别中，忽略点击（防止状态混乱）
            pass

        elif s == STATE_DONE:
            # 完成态点击 = 开始新的录音
            self._start_recording()

    def _start_recording(self):
        if not self._model_ok:
            return
        ok = self.recorder.start()
        if ok:
            self._set_state(STATE_RECORDING)
        else:
            self._set_state(STATE_IDLE)

    def _stop_and_transcribe(self):
        recording = self.recorder.stop()
        if recording is None:
            self._set_state(STATE_IDLE)
            return

        self._set_state(STATE_PROCESSING)
        threading.Thread(
            target=self._run_transcribe,
            args=(recording.wav_path,),
            daemon=True,
        ).start()

    # ── 后台识别 ──

    def _run_transcribe(self, wav_path):
        try:
            result = self.engine.transcribe(wav_path)
        except Exception as e:
            self._error_signal.emit(f"识别异常: {e}")
            return
        finally:
            try:
                wav_path.unlink()
            except OSError:
                pass

        if "error" in result:
            self._error_signal.emit(result["error"])
            return

        text = result.get("text", "").strip()
        if text:
            self._result_signal.emit(text)
        else:
            self._error_signal.emit("未检测到语音")

    # ── 主线程回调 ──

    def _paste(self, text):
        print(f"[识别] → {text}")
        pyperclip.copy(text)
        time.sleep(0.03)
        try:
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pass
        self._set_state(STATE_DONE)
        # 1.5秒后回到 IDLE，准备下一次录音
        QTimer.singleShot(1500, self._reset_to_idle)

    def _on_error(self, msg):
        print(f"[错误] {msg}")
        self._set_state(STATE_IDLE)

    def _reset_to_idle(self):
        """DONE → IDLE，但要避免和用户点击冲突"""
        if self._current_state == STATE_DONE:
            self._set_state(STATE_IDLE)

    # ── 启动 ──

    def start(self):
        self.overlay.mic_button.show()
        self._set_state(STATE_IDLE)
        self.overlay.tray.show()

        def load_model():
            try:
                self.engine.load_model()
                self._model_ok = True
                print("[系统] 模型就绪 (small, int8)")
            except Exception as e:
                print(f"[系统] 模型失败: {e}")

        threading.Thread(target=load_model, daemon=True).start()
        print("[系统] 语音输入已启动 — 点击按钮开始录音")

    def stop(self):
        self.overlay.mic_button.hide()
        print("[系统] 已退出")


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("语音输入")

    voice = VoiceInputApp()
    voice.start()

    voice.overlay.tray.quit_requested.connect(app.quit)
    exit_code = app.exec()
    voice.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
