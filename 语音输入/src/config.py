"""语音输入系统全局配置"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".voice-input"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+r",
    "sample_rate": 16000,
    "channels": 1,
    "model_size": "small",       # base=150MB快速 / small=500MB更准（中文更优）
    "language": "",           # "" = 自动检测; "zh" = 仅中文; "en" = 仅英文
    "device": "cpu",
    "compute_type": "int8",        # CPU 推理最优选择
    "paste_mode": "clipboard",
    "start_on_boot": False,
}


def load_config() -> dict:
    """加载配置，不存在则创建默认"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # 合并默认值，确保新增配置项存在
        config = {**DEFAULT_CONFIG, **saved}
        return config
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """保存配置到文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
