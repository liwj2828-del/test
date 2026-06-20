"""音频录制模块

纯录音逻辑，不涉及热键。由外部（main.py）控制录制启停。
"""

import time
import wave
import threading
import tempfile
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

import sounddevice as sd
import numpy as np


@dataclass
class Recording:
    """一次录音的结果"""
    wav_path: Path
    duration_seconds: float
    sample_count: int


class VoiceRecorder:
    """语音录制器"""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels

        self._recording_data: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._is_recording = False

        # 回调
        self.on_start: Optional[Callable[[], None]] = None
        self.on_stop: Optional[Callable[[Recording], None]] = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """sounddevice 音频回调"""
        if status:
            print(f"[录音] 警告: {status}")
        self._recording_data.append(indata.copy())

    def start(self) -> bool:
        """开始录音，返回是否成功"""
        with self._lock:
            if self._is_recording:
                return False
            self._recording_data = []
            self._is_recording = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                dtype="int16",
            )
            self._stream.start()
        except Exception as e:
            print(f"[录音] 启动麦克风失败: {e}")
            self._is_recording = False
            return False

        if self.on_start:
            try:
                self.on_start()
            except Exception:
                pass

        return True

    def stop(self) -> Optional[Recording]:
        """停止录音，返回 Recording 对象"""
        with self._lock:
            if not self._is_recording:
                return None
            self._is_recording = False

        # 停止流
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # 合并数据
        if not self._recording_data:
            return None

        audio = np.concatenate(self._recording_data, axis=0)
        duration = len(audio) / self.sample_rate

        # 静音检测
        if np.abs(audio).mean() < 30:
            return None

        # 保存 WAV
        temp_dir = Path(tempfile.gettempdir()) / "voice-input"
        temp_dir.mkdir(exist_ok=True)
        wav_path = temp_dir / f"record_{int(time.time() * 1000)}.wav"

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

        recording = Recording(
            wav_path=wav_path,
            duration_seconds=round(duration, 2),
            sample_count=len(audio),
        )

        if self.on_stop:
            try:
                self.on_stop(recording)
            except Exception:
                pass

        return recording

    def cancel(self) -> None:
        """取消录音（不保存）"""
        self._recording_data = []
        self._is_recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
