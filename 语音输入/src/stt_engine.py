"""语音识别引擎 — 速度优化版

基于 faster-whisper，将 WAV 音频转换为文字。
- beam_size=1 贪婪搜索
- VAD 跳过静音
- 不生成时间戳
"""

import os
import threading
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from .config import load_config


class STTEngine:
    """语音转文字引擎"""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        language: Optional[str] = None,
    ):
        config = load_config()
        self.model_size = model_size or config["model_size"]
        self.device = device or config["device"]
        self.compute_type = compute_type or config["compute_type"]
        lang = language or config["language"]
        self.language = lang if lang else None  # "" → None 自动检测

        self._model: Optional[WhisperModel] = None
        self._lock = threading.Lock()
        self._loaded = False

    def load_model(self) -> None:
        """加载模型（常驻内存）"""
        with self._lock:
            if self._loaded:
                return
            print(f"[识别] 加载 {self.model_size} 模型 (cpu, {self.compute_type})...")

            # int8_float16 比纯 int8 更快（利用 CPU 的 float16 指令）
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=0,       # 自动使用所有 CPU 核心
                num_workers=1,
            )
            self._loaded = True
            print("[识别] 模型就绪")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def transcribe(self, audio_path: Path) -> dict:
        """识别音频，返回 {text, language, confidence, duration_ms}"""
        if not self._loaded:
            self.load_model()

        if not audio_path.exists():
            return {"text": "", "error": f"文件不存在: {audio_path}"}

        try:
            segments, info = self._model.transcribe(
                str(audio_path),
                language=self.language,
                # ── 速度关键参数 ──
                beam_size=1,                        # 贪婪搜索（最快）
                best_of=1,                          # 单候选
                vad_filter=True,                    # 跳过静音
                condition_on_previous_text=False,   # 不依赖上下文
                without_timestamps=True,            # 不生成时间戳
                # ── 加速辅助 ──
                temperature=0.0,                    # 确定性输出
                compression_ratio_threshold=2.4,    # 标准值
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,            # 标准值
            )

            text_parts = []
            total_confidence = 0.0
            segment_count = 0

            for seg in segments:
                text_parts.append(seg.text.strip())
                total_confidence += seg.avg_logprob
                segment_count += 1

            text = " ".join(text_parts)
            avg_confidence = total_confidence / segment_count if segment_count else 0.0

            return {
                "text": text,
                "language": info.language,
                "confidence": round(avg_confidence, 3),
                "duration_ms": round(info.duration * 1000),
            }
        except Exception as e:
            return {"text": "", "error": str(e)}

    def unload(self) -> None:
        """卸载模型"""
        self._model = None
        self._loaded = False
