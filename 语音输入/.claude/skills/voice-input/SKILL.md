---
name: voice-input
description: |
  分阶段构建 Windows 本地语音输入系统。当用户提到语音输入、语音转文字、voice input、
  speech-to-text、说话转文字、或想在任何软件中用语音打字时使用此 skill。
  也用于继续之前中断的构建过程。
---

# 语音输入系统 — 分阶段构建 Skill

在 Windows 上构建一个完全本地离线运行的语音输入系统。按住全局快捷键说话，松开后自动识别为文字并粘贴到任意软件中。

## 技术栈

- **语音识别**: faster-whisper (Small 模型, 中英混合, CPU 推理)
- **全局热键**: keyboard 库
- **音频捕获**: sounddevice + numpy
- **桌面 UI**: PyQt6 (浮动指示器 + 系统托盘)
- **文字输出**: pyperclip (剪贴板) + pyautogui (Ctrl+V)
- **打包**: PyInstaller (单文件 .exe)

## 构建流程（6 阶段）

每个阶段独立运行，需要用户明确确认后才进入下一阶段。任何时候用户说"跳过"或"继续"即进入下一阶段。

### 阶段 1: 环境检查（只读，零风险）

**目标**: 确认所有必要工具已安装，不做任何修改。

**检查项**:
1. Python 版本 >= 3.10
2. pip 可用性
3. 默认麦克风设备存在且可访问
4. CUDA 可用性（可选，仅报告）
5. 磁盘空间 >= 5GB（模型 ~500MB + 依赖 ~1GB + 预留）

**执行方式**: 全部通过只读命令完成，不安装任何东西。

**完成后**: 打印环境报告。如有缺失项，列出具体修复建议（如 "请先安装 Python 3.10+"）。

---

### 阶段 2: 安装依赖 + 下载模型

**目标**: 搭建开发环境，下载 faster-whisper Small 模型。

**⚠️ 安全闸门 — 执行前必须**:
1. 列出所有将要 pip install 的包名和版本
2. 列出模型下载 URL 和目标大小（~500MB）
3. 明确要求用户确认后才执行

**操作**:
```bash
pip install faster-whisper sounddevice numpy keyboard pyperclip pyautogui PyQt6
```

模型在首次 `import faster_whisper` 并调用 `WhisperModel("small")` 时自动下载到 HuggingFace 缓存目录。

**回滚方式**: `pip uninstall faster-whisper sounddevice numpy keyboard pyperclip pyautogui PyQt6 -y`

---

### 阶段 3: 热键监听 + 音频录制模块

**目标**: 实现"按住录音，松开停止"的核心交互。

**文件**: `src/recorder.py`

**功能**:
1. 注册全局热键（默认 `Ctrl+Shift+R`，可配置）
2. 按下时开始录音（16kHz 采样率，单声道）
3. 松开时停止录音，保存为临时 WAV 文件
4. 提供 `on_record_start` 和 `on_record_stop` 回调钩子

**测试方式**: 运行后按热键说话 3 秒，确认生成有效 WAV 文件。

**核心库**: `keyboard`（全局钩子）、`sounddevice`（音频捕获）

**Windows 注意事项**:
- `keyboard` 库需要管理员权限才能拦截所有按键
- 录音设备索引通过 `sounddevice.query_devices()` 自动选择默认输入设备

---

### 阶段 4: 语音识别引擎

**目标**: 将录制的音频文件转换为文字。

**文件**: `src/stt_engine.py`

**功能**:
1. 加载 faster-whisper Small 模型（首次自动下载）
2. 接收 WAV 文件路径，返回识别文字
3. 支持中英混合识别（language 参数默认为 "zh"）
4. 返回置信度分数

**核心代码模式**:
```python
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.wav", language="zh")
text = " ".join(seg.text for seg in segments)
```

**测试方式**: 用阶段 3 录制的 WAV 文件喂入引擎，检查输出文字是否准确。

**注意事项**:
- CPU 推理使用 `int8` 量化，平衡速度与精度
- 短句（<3秒）通常 1-2 秒内完成识别
- 模型加载是慢操作，应常驻内存而非每次重新加载

---

### 阶段 5: 浮动 UI + 系统托盘

**目标**: 提供录音时的视觉反馈和系统托盘常驻。

**文件**: `src/overlay.py`

**功能**:
1. **浮动指示器**: 录音时在屏幕右下角显示半透明圆形窗口
   - 录音中：红色脉冲动画
   - 识别中：黄色旋转动画
   - 完成：绿色短暂闪烁后自动隐藏
2. **系统托盘**: 常驻托盘图标
   - 右键菜单：开始/停止、设置热键、开机自启、退出
   - 左键单击：切换录音状态

**核心库**: PyQt6 (QSystemTrayIcon + QWidget 无边框悬浮窗)

**注意事项**:
- 悬浮窗设置 `Qt.WindowStaysOnTopHint` 保持在最前
- 不获取焦点 (`Qt.Tool`)，避免干扰当前应用
- 托盘图标使用系统默认图标或内置 base64 图标

---

### 阶段 6: 集成 + 打包

**目标**: 将所有模块连接成完整程序，打包为独立 .exe。

**文件**: `main.py`

**集成逻辑**:
```
1. 启动 → 加载模型（常驻）→ 显示托盘图标
2. 用户按下热键 → recorder 开始录音 → overlay 显示红色动画
3. 用户松开热键 → recorder 停止 → overlay 显示黄色动画
4. stt_engine 识别 → 结果写入剪贴板 → 模拟 Ctrl+V
5. overlay 绿色闪烁 → 隐藏 → 等待下一次热键
```

**打包命令**:
```bash
pyinstaller --onefile --windowed --add-data "model:model" main.py
```

**验证方式**:
1. 打开记事本
2. 按热键说话
3. 确认文字出现在记事本中

---

## 安全原则

1. **阶段隔离**: 每个阶段完成后停下来，等用户确认再继续
2. **预演先行**: 每阶段执行前，先展示将要创建/修改的文件列表
3. **回滚可逆**: 每个阶段末尾说明如何撤销本阶段操作
4. **只读优先**: 阶段 1 完全只读，不做任何修改
5. **文件不覆盖**: 创建新文件前检查是否已存在，如存在则询问
6. **权限提示**: 需要管理员权限的操作（全局热键）要明确说明原因

## 交互指引

**首次启动**:
```
用户: /voice-input
Claude: [展示 6 个阶段概览，建议从阶段 1 开始]
```

**逐阶段推进**:
```
用户: 开始阶段 1
Claude: [执行只读检查，打印环境报告]

用户: 继续 / 下一步
Claude: [展示阶段 2 将要安装的包列表，请求确认]
```

**随时可用的命令**:
- "检查状态" — 查看当前进度
- "重做阶段 N" — 重新执行某个阶段
- "跳过阶段 N" — 跳过不需要的阶段
- "回滚阶段 N" — 撤销某个阶段的操作

## 项目文件结构

```
语音输入/
├── .claude/skills/voice-input/SKILL.md  ← 本文件
├── src/
│   ├── recorder.py       ← 阶段 3: 热键 + 录音
│   ├── stt_engine.py     ← 阶段 4: 语音识别
│   ├── overlay.py        ← 阶段 5: 浮动 UI
│   └── config.py         ← 配置文件（热键、语言等）
├── main.py               ← 阶段 6: 主入口
├── requirements.txt      ← 阶段 2: 依赖列表
└── build.bat             ← 阶段 6: 打包脚本
```
