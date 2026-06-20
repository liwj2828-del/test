@echo off
chcp 65001 >nul
echo ========================================
echo   语音输入系统 — PyInstaller 打包脚本
echo ========================================
echo.

REM 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] 安装 PyInstaller...
    python -m pip install pyinstaller
)

echo [2/4] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] 查找 faster_whisper assets 路径...
for /f "delims=" %%i in ('python -c "import faster_whisper, os; print(os.path.join(os.path.dirname(faster_whisper.__file__), 'assets'))"') do set "FW_ASSETS=%%i"
echo    找到: %FW_ASSETS%

echo [4/4] 开始打包...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "VoiceInput" ^
    --add-data "src;src" ^
    --add-data "%FW_ASSETS%;faster_whisper\assets" ^
    --hidden-import faster_whisper ^
    --hidden-import ctranslate2 ^
    --hidden-import sounddevice ^
    --hidden-import pyperclip ^
    --hidden-import pyautogui ^
    --hidden-import PyQt6 ^
    --hidden-import numpy ^
    --exclude-module keyboard ^
    --exclude-module tkinter ^
    --exclude-module PyQt5 ^
    main.py

echo.
echo ========================================
echo   打包完成！文件在 dist\VoiceInput.exe
echo ========================================
pause
