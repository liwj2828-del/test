@echo off
chcp 65001 >nul
echo ========================================
echo   历史粘贴板 — PyInstaller 打包脚本
echo ========================================
echo.

REM 检查 PyInstaller 是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [提示] PyInstaller 未安装，正在安装...
    python -m pip install pyinstaller -i https://pypi.org/simple/
    echo.
)

echo [1/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/3] 开始打包...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "历史粘贴板" ^
    --add-data "requirements.txt;." ^
    --clean ^
    main.py

echo.
if exist "dist\历史粘贴板.exe" (
    echo [3/3] 打包成功！
    echo.
    echo 输出文件: dist\历史粘贴板.exe
    echo.
    REM 显示文件大小
    for %%A in ("dist\历史粘贴板.exe") do echo 文件大小: %%~zA 字节
) else (
    echo [错误] 打包失败，请检查上方错误信息
)

echo.
pause
