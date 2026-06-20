"""
设置模块 — 管理用户配置的读写
配置存储在 %APPDATA%/ClipHistory/settings.json
"""

import json
import os


class AppSettings:
    """应用设置管理类"""

    def __init__(self):
        self.data_dir = os.path.join(os.getenv("APPDATA"), "ClipHistory")
        self.settings_path = os.path.join(self.data_dir, "settings.json")
        os.makedirs(self.data_dir, exist_ok=True)

        # 默认设置
        self._defaults = {
            "retention_days": 3,  # 默认保留3天
        }

        # 加载或初始化
        self._data = self._load()

    def _load(self) -> dict:
        """从文件加载设置，不存在则用默认值"""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 合并默认值（保证新字段也有默认值）
                return {**self._defaults, **data}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(self._defaults)

    def save(self):
        """保存设置到文件"""
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ---- 属性访问 ----

    @property
    def retention_days(self) -> int:
        """保留天数：1/3/5/0（0=不限）"""
        return self._data.get("retention_days", 3)

    @retention_days.setter
    def retention_days(self, value: int):
        allowed = [0, 1, 3, 5]
        if value in allowed:
            self._data["retention_days"] = value
            self.save()
        else:
            raise ValueError(f"保留天数必须是 {allowed} 之一，收到: {value}")

    def get_retention_label(self) -> str:
        """获取保留期限的显示文字"""
        mapping = {0: "不限", 1: "1 天", 3: "3 天", 5: "5 天"}
        return mapping.get(self.retention_days, "3 天")


# 模块级自测
if __name__ == "__main__":
    s = AppSettings()
    print(f"设置文件: {s.settings_path}")
    print(f"当前保留天数: {s.retention_days} ({s.get_retention_label()})")

    # 测试修改
    s.retention_days = 5
    print(f"修改后: {s.retention_days} 天")

    # 恢复默认
    s.retention_days = 3
    print(f"恢复默认: {s.retention_days} 天")
    print("\n设置模块自测通过！")
