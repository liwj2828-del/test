"""Windows 原生热键管理

使用 RegisterHotKey / UnregisterHotKey API，
不需要管理员权限，不阻塞键盘输入。
"""

import ctypes
from ctypes import wintypes
from typing import Callable, Optional

# Windows API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 修饰键常量
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# 虚拟键码
VK_CODES = {chr(i): i for i in range(0x41, 0x5B)}  # A-Z
VK_CODES.update({
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "space": 0x20, "tab": 0x09, "enter": 0x0D,
    "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "insert": 0x2D,
    "capslock": 0x14,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "printscreen": 0x2C,
    "pause": 0x13,
})
# 兼容大写
for k, v in list(VK_CODES.items()):
    if len(k) == 1 and k.isalpha():
        VK_CODES[k.lower()] = v

MOD_MAP = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt": MOD_ALT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """解析热键字符串为 (modifiers, vk_code)

    例: "ctrl+shift+r" → (MOD_CONTROL | MOD_SHIFT, 0x52)
    """
    parts = [p.strip() for p in hotkey_str.lower().split("+")]
    modifiers = 0
    vk = None

    for p in parts:
        if p in MOD_MAP:
            modifiers |= MOD_MAP[p]
        elif p in VK_CODES:
            vk = VK_CODES[p]
        else:
            raise ValueError(f"无法识别的按键: '{p}'")

    if vk is None:
        raise ValueError(f"热键中缺少主键: '{hotkey_str}'")

    return modifiers, vk


def register_hotkey(hwnd: int, hotkey_id: int, hotkey_str: str) -> bool:
    """注册全局热键

    Args:
        hwnd: 窗口句柄（接收 WM_HOTKEY 消息）
        hotkey_id: 热键唯一 ID
        hotkey_str: 热键字符串，如 "ctrl+shift+r"

    Returns:
        True 成功，False 失败（通常是被其他程序占用）
    """
    modifiers, vk = parse_hotkey(hotkey_str)
    result = user32.RegisterHotKey(hwnd, hotkey_id, modifiers, vk)
    if result == 0:
        err = kernel32.GetLastError()
        print(f"[热键] RegisterHotKey 失败: {hotkey_str} (错误码: {err})")
        return False
    print(f"[热键] 已注册: {hotkey_str} (id={hotkey_id})")
    return True


def unregister_hotkey(hwnd: int, hotkey_id: int) -> bool:
    """注销全局热键"""
    result = user32.UnregisterHotKey(hwnd, hotkey_id)
    return result != 0


def is_key_pressed(vk_code: int) -> bool:
    """检查指定虚拟键是否正在被按住"""
    return (user32.GetAsyncKeyState(vk_code) & 0x8000) != 0


def are_all_modifiers_pressed(modifiers: int) -> bool:
    """检查所有修饰键是否都被按住"""
    checks = [
        (MOD_CONTROL, 0x11),  # VK_CONTROL
        (MOD_SHIFT, 0x10),    # VK_SHIFT
        (MOD_ALT, 0x12),      # VK_MENU
        (MOD_WIN, 0x5B),      # VK_LWIN
    ]
    for mod_flag, vk in checks:
        if (modifiers & mod_flag) and not is_key_pressed(vk):
            return False
    return True
