# -*- coding: utf-8 -*-
"""
=========================================================
 MouseClick - 鼠标连点器（模拟点击工具）
=========================================================
模仿经典「模拟」小工具：
   ☐ 模拟开关    热键: =/-
   间隔时长      50
   鼠标按键选择  ◉ 左键  ○ 中键  ○ 右键

功能说明：
  - 勾选「模拟开关」后，程序会按设定间隔在【当前鼠标位置】持续模拟点击
  - 全局热键：按 = 开启模拟，按 - 关闭模拟（程序在后台也能用）
  - 支持左键 / 中键 / 右键
  - 点击后端：优先使用 pynput（跨平台），否则使用 Windows 原生 mouse_event（零依赖）
  - 设置持久化（v1.1.0）：间隔时长 / 鼠标按键 / 窗口几何与最大化 实时自动保存到
    mouseclick_settings.json（防抖 500ms + 退出强制保存），下次启动自动沿用；
    模拟开关属运行状态，为安全不记忆（避免程序下次启动意外自动连点）
  - 可自定义快捷键（v1.2.0）：点「设置」可自定义 开始/关闭模拟 的快捷键，支持
    键盘（任意按键或组合键）或手柄按钮；主界面实时显示当前快捷键
    默认：- 开始模拟，= 关闭模拟

依赖：
  - PySide6 （GUI）
  - pynput  （可选，跨平台模拟点击；不装则 Windows 下用 ctypes 原生实现）
  - pygame  （可选，使用手柄按钮作为快捷键时）
"""

import sys
import os
import json
import base64
import queue
import threading
import time

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
    _WIN32 = True
else:
    _WIN32 = False

from PySide6.QtCore import Qt, QTimer, QObject, Signal, QAbstractNativeEventFilter, QKeyCombination, QRect
from PySide6.QtGui import QIcon, QKeySequence, QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QCheckBox,
    QLabel,
    QSpinBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QFrame,
    QPushButton,
    QComboBox,
    QDialog,
    QTabWidget,
    QFormLayout,
    QMessageBox,
    QDialogButtonBox,
    QKeySequenceEdit,
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
)

__version__ = "1.2.27"
APP_NAME = "鼠标连点器"


# 设置文件路径（程序目录，打包后为 exe 目录）
def settings_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "mouseclick_settings.json")


# 默认设置
DEFAULT_SETTINGS = {
    "interval": 50,
    "button": "left",
    "window_geometry": None,
    "window_maximized": False,
    "resizable": False,
    "auto_select": True,
    "progress_bar": True,
    "progress_theme": "马卡龙色系",
    "progress_height": 4,
    "test_enabled": False,       # 是否显示「调试中」单选（v1.2.21，调试用）
    "indicator_enabled": False,  # 平时是否显示指示灯（v1.2.22，反映模拟状态）
}


# =========================================================
# 进度条色系库（v1.2.6）：每个色系 4 个代表色（hex）
# =========================================================
COLOR_THEMES = {
    # ---- 现代/风格 ----
    "马卡龙色系": ["#FFB5C2", "#FFD3A5", "#B5EAD7", "#A5D8FF", "#FFC3D0", "#FFF0A8", "#C7CEEA", "#D6B8FF"],
    "莫兰迪色系": ["#C9B8A3", "#A8A49C", "#B0A8B9", "#9DA8A0", "#C4B0A0", "#B6A9A6", "#A09A92", "#B8AA9E"],
    "美拉德色系": ["#8B5A2B", "#A0522D", "#CD853F", "#D2691E", "#B8860B", "#6B4226", "#A67C52", "#C4874A"],
    "多巴胺色系": ["#FF4D6D", "#FFB703", "#06D6A0", "#118AB2", "#EF476F", "#8338EC", "#FF7F50", "#F4A261"],
    "赛博朋克色系": ["#00F5FF", "#FF00FF", "#00FF9F", "#FF2E63", "#7B00FF", "#00E5FF", "#FFB400", "#FF007F"],
    "孟菲斯色系": ["#FF3366", "#00C2A8", "#FFB400", "#7A5CFF", "#00A3FF", "#FF6B6B", "#FFD166", "#6C5CE7"],
    "侘寂色系": ["#A79C8E", "#C2B8A6", "#8E8271", "#D3C9B8", "#6E6457", "#B4A797", "#9A8B76", "#C6BBA6"],
    "大地色系": ["#8B5A2B", "#A0522D", "#6B4226", "#D2B48C", "#CD853F", "#8B4513", "#C08A4E", "#7B4A2A"],
    "奶油色系": ["#FFF5E1", "#FFE4C4", "#F5E6D3", "#FFF0DB", "#F7E7CE", "#FFF8E7", "#FFE8C8", "#FAEBD7"],
    "燕麦色系": ["#E8DCC4", "#D9C9A8", "#C9B896", "#DED3B8", "#EFE6D5", "#BFA980", "#D2C3A4", "#E5D9BF"],
    "奶茶色系": ["#C8A27A", "#B98E68", "#D4B48F", "#A67C52", "#C69C6D", "#8B5E3C", "#D8BC98", "#B08A60"],
    "糖果色系": ["#FFB5C2", "#FFD3A5", "#B5EAD7", "#A5D8FF", "#FF9AA2", "#C7CEEA", "#FFDAB9", "#B8F0D9"],
    "冰淇淋色系": ["#FFD1DC", "#FFF1A8", "#B5EAD7", "#C7CEEA", "#FFB3BA", "#A8E6CF", "#FFDAC1", "#D4F0F0"],
    "废土色系": ["#6B5B4A", "#8A7A6A", "#4A4238", "#7A6B58", "#5C5244", "#9A8B76", "#3A322C", "#857460"],
    "蒸汽波色系": ["#FF71CE", "#01CDFE", "#05FFA1", "#B967FF", "#FFFB96", "#01CDFE", "#F75990", "#E4FF1A"],
    "Y2K色系": ["#FFB6C1", "#E0FFFF", "#FFFACD", "#FFC0CB", "#98FB98", "#FF69B4", "#AFEEEE", "#FFE4B5"],
    "克莱因蓝色系": ["#002FA7", "#1A3FA8", "#001E62", "#2240A8", "#002FA7", "#3355B8", "#001B56", "#0A36A8"],
    "哥特色系": ["#1A1A2E", "#0F0F0F", "#2B2B3A", "#111111", "#1F1F2E", "#000000", "#33334A", "#0A0A1A"],
    "暗黑系": ["#000000", "#111111", "#1A1A1A", "#222222", "#2C2C2C", "#333333", "#0A0A0A", "#3D3D3D"],
    "极简色系": ["#FFFFFF", "#F5F5F5", "#EAEAEA", "#DDDDDD", "#CCCCCC", "#BBBBBB", "#F0F0F0", "#E0E0E0"],
    "北欧色系": ["#F5F1E8", "#D9E0DE", "#A3B8B0", "#E8DFD0", "#B5C4C0", "#F0EBE3", "#C8D2CE", "#DCD3C3"],
    "斯堪的纳维亚色系": ["#F5F5F5", "#D8D8D8", "#A9C9B8", "#E3E9E0", "#C0C9C0", "#F0F0F0", "#BDD2C5", "#EBEFEA"],
    "地中海色系": ["#3A7CA5", "#A8D8EA", "#F6D365", "#5FA8D3", "#E8F4F8", "#F7C873", "#2A6E9E", "#C8E8F5"],
    "摩洛哥色系": ["#C8334B", "#E8A33D", "#2A6E6E", "#7A4E6E", "#F2D5A8", "#A6596B", "#D95A6B", "#1A5A5A"],
    "波西米亚色系": ["#8B3A62", "#E07A5F", "#3D405B", "#81B29A", "#F2CC8F", "#5F4B8B", "#B05E7C", "#A8C8B0"],
    "复古色系": ["#8B7355", "#A67C52", "#C9A227", "#7B5B3A", "#A0522D", "#6B4226", "#C9A96E", "#7A5C3A"],
    "做旧色系": ["#9A8B76", "#B7A690", "#8A7A66", "#A6937C", "#7A6B58", "#C4B4A0", "#6E5F4E", "#B0A08C"],
    "褪色系": ["#D8C8B8", "#C0B0A0", "#B0A090", "#E0D0C0", "#C8B8A8", "#D0C0B0", "#A89888", "#E8D8C8"],
    "怀旧色系": ["#D2B48C", "#C8A27A", "#E8D5B8", "#B98E68", "#D4B48F", "#C9A96E", "#B0835A", "#DECBA8"],
    "未来主义色系": ["#00E5FF", "#A0F0FF", "#C0F0FF", "#7DF9FF", "#B0E0FF", "#E0FBFF", "#40E0D0", "#D0FFFF"],
    "太空色系": ["#0B1026", "#1B2A4A", "#3A4A6E", "#5A6A8E", "#0A0A1A", "#20253F", "#4A5A7E", "#2A3550"],
    "酸性色系": ["#CCFF00", "#00FF00", "#FF00FF", "#00FFFF", "#FFFF00", "#FF7F00", "#00FF80", "#FF00A0"],
    "迷幻色系": ["#FF00FF", "#00FFFF", "#FFFF00", "#FF00A0", "#00FF80", "#FF8000", "#CC00FF", "#00FFCC"],
    "霓虹色系": ["#FF00FF", "#00FF00", "#00FFFF", "#FFFF00", "#FF00A0", "#00FF80", "#FF6600", "#00CCFF"],
    "荧光色系": ["#CCFF00", "#FF00FF", "#00FF66", "#66FF00", "#FF0099", "#00CCFF", "#99FF00", "#FF00CC"],
    "镭射色系": ["#FF00CC", "#00CCFF", "#CC00FF", "#FFCC00", "#00FFCC", "#CCFF00", "#FF0099", "#00FF99"],
    "金属色系": ["#C0C0C0", "#A9A9A9", "#E5E4E2", "#B8B8B8", "#8C8C8C", "#D0D0D0", "#F5F5F5", "#A0A0A0"],
    "渐变系": ["#FF9A9E", "#FAD0C4", "#A18CD1", "#FBC2EB", "#84FAB0", "#8FD3F4", "#FFD1DC", "#B5EAD7"],
    # ---- 艺术流派 ----
    "蒙德里安色系": ["#C1000A", "#FFD700", "#003DA5", "#222222", "#FFFFFF", "#0066B3", "#E8E8E8", "#7A7A7A"],
    "洛可可色系": ["#E8C4C4", "#D9B8A0", "#C2A878", "#F0DCC8", "#B98E8E", "#D4B48F", "#F5E0D0", "#C8A878"],
    "印象派色系": ["#F2A65A", "#7BA3C9", "#A8C97B", "#E8D58A", "#C96F6F", "#88B8A8", "#E0B060", "#5A9AC0"],
    "波普色系": ["#FF007F", "#00E5FF", "#FFD700", "#FF4500", "#00FF7F", "#7A00FF", "#FF2E63", "#00C2FF"],
    "包豪斯色系": ["#E03A3E", "#F2A900", "#00A0B0", "#404040", "#EDC951", "#F5F5F5", "#2A3A4A", "#C0C0C0"],
    "浮世绘色系": ["#2A4D8F", "#E8A33D", "#7A4E6E", "#3E7A5E", "#D97B6C", "#1F3A5F", "#A8C8B0", "#C9A227"],
    "巴洛克色系": ["#8B0000", "#B8860B", "#2F1B0E", "#7B3F00", "#5C2E00", "#A0522D", "#4A2A10", "#8A5A20"],
    "文艺复兴色系": ["#7B3F00", "#8B0000", "#A0522D", "#C2A878", "#3A2E1A", "#B8860B", "#6B3A10", "#D0B080"],
    "浪漫主义色系": ["#B03A5B", "#C77DA0", "#F0A8B8", "#8E6E9E", "#D9A0B0", "#A05070", "#E0C0D0", "#7A4A6A"],
    "新古典主义色系": ["#E8E0D0", "#D0C8B8", "#B8B0A0", "#F0EAE0", "#C8C0B0", "#DCD4C4", "#A8A090", "#F5F0E8"],
    "野兽派色系": ["#FF4500", "#FFD700", "#00BFFF", "#FF1493", "#7CFC00", "#FF8C00", "#00FF7F", "#FF007F"],
    "立体派色系": ["#A0522D", "#8B7355", "#C0A080", "#6B5B4A", "#D2B48C", "#5C4033", "#9A8B76", "#4A3828"],
    "超现实主义色系": ["#FF69B4", "#00CED1", "#FFD700", "#8A2BE2", "#00FF7F", "#FF4500", "#7A6AF0", "#FFA000"],
    "抽象表现主义色系": ["#1B1B1B", "#8B0000", "#E8A33D", "#2A4D8F", "#D3D3D3", "#556B2F", "#C8334B", "#3A3A3A"],
    "极简主义色系": ["#FFFFFF", "#000000", "#F0F0F0", "#333333", "#E0E0E0", "#666666", "#CCCCCC", "#999999"],
    "维也纳分离派色系": ["#D4AF37", "#000000", "#F0E68C", "#8B7355", "#C8A060", "#2F2F2F", "#E8D8B8", "#5A5A5A"],
    "新艺术运动色系": ["#3E7A5E", "#8B5A2B", "#C9A227", "#5C4033", "#A67C52", "#6B4226", "#8A9A6A", "#D0B060"],
    "装饰艺术色系": ["#D4AF37", "#8B0000", "#1A1A2E", "#F5E6D3", "#A0522D", "#C8A060", "#2A4D8F", "#E8D0B0"],
    "荷兰画派色系": ["#5C4033", "#8B5A2B", "#A0522D", "#7B3F00", "#3A2E1A", "#C2A878", "#6B4226", "#B08050"],
    "威尼斯画派色系": ["#B03A2E", "#7B3F00", "#8B0000", "#C9A227", "#5C2E00", "#A0522D", "#D0B060", "#7A3A20"],
    # ---- 自然 ----
    "森林色系": ["#2D4A22", "#3E6B33", "#4F8A44", "#6BA85C", "#1F3A18", "#5E8C4A", "#7AB86A", "#3A5A2E"],
    "草木色系": ["#7CA65C", "#A8C97B", "#8FBF6A", "#C8DCA8", "#6BA85C", "#9ECB7A", "#B8E0A0", "#5E8E4A"],
    "海洋色系": ["#0A5C7A", "#1A7A9E", "#2A9AB8", "#4AB8D0", "#0A3A5A", "#3AA8C0", "#6AC8E0", "#1A6A8E"],
    "湖泊色系": ["#1A6A9E", "#3A8AB8", "#5AA8D0", "#7AC8E0", "#2A7AA8", "#4A9AC8", "#8AD8F0", "#1A5A8A"],
    "沙漠色系": ["#D2B48C", "#C8A27A", "#E0C9A0", "#B98E68", "#D4B48F", "#A67C52", "#F0D8B0", "#8B5E3C"],
    "暖阳色系": ["#FFD700", "#FFB347", "#FFA500", "#FF8C00", "#F4A460", "#FFC04C", "#FFE066", "#E88A00"],
    "日落色系": ["#FF7E5F", "#FEB47B", "#FF6B6B", "#FF9A56", "#F76B8A", "#FFB347", "#FF8C69", "#E85A5A"],
    "矿石色系": ["#6B5B8E", "#8A7AC8", "#5A4A7A", "#7A6AB0", "#4A3A6A", "#9680C0", "#A090D0", "#3A2A5A"],
    "宝石色系": ["#E0115F", "#0095B6", "#50C878", "#FFC72C", "#9966CC", "#FF7F50", "#00A0B0", "#FF4500"],
    "木材色系": ["#8B5A2B", "#A0522D", "#C68E4F", "#6B4226", "#D2A679", "#5C4033", "#B08060", "#7B4A2A"],
    "泥土色系": ["#6B4226", "#8B5A2B", "#5C4033", "#A0522D", "#7B4A2A", "#4A3018", "#9A6B48", "#3A2818"],
    "岩石色系": ["#8A8A8A", "#6E6E6E", "#A0A0A0", "#5C5C5C", "#B8B8B8", "#7A7A7A", "#909090", "#646464"],
    "苔藓色系": ["#6B8E5A", "#5E7A4A", "#8FBF6A", "#7A9E5C", "#4F6E3A", "#9EB87A", "#6A9A5A", "#B0C890"],
    "冰雪色系": ["#E0F0FF", "#C0E0FF", "#A0D0F0", "#FFFFFF", "#D8F0FF", "#B8E0FF", "#F0F8FF", "#C8E8FF"],
    "云雾色系": ["#E8E8E8", "#D0D0D0", "#F0F0F0", "#C0C0C0", "#E0E0E0", "#D8D8D8", "#B0B0B0", "#F8F8F8"],
    "天空色系": ["#87CEEB", "#4A90D9", "#6AB0E8", "#B0D8F0", "#2A7AB8", "#A0C8E8", "#5AA0E0", "#C0E0F8"],
    "星空色系": ["#0A0A2E", "#1A1A4A", "#2A2A6E", "#3A3A8E", "#101030", "#20205A", "#4A4AA0", "#1A1A3A"],
    "极光色系": ["#00FF87", "#00C2FF", "#7AFFC0", "#38FFB0", "#00A86B", "#5AFFD0", "#A0FFD8", "#00E0A0"],
    "珊瑚色系": ["#FF7F50", "#FF6B6B", "#FFA07A", "#FF8C69", "#E55B5B", "#FF9E80", "#FF6A5A", "#FFB090"],
    "贝壳色系": ["#FFE4D6", "#FFD8C0", "#F5D0C0", "#FFE0D0", "#F0C8B0", "#FFE8D8", "#E8C0A8", "#FFF0E4"],
    "珍珠色系": ["#F5F0E8", "#E8E0D8", "#FFF8F0", "#D8D0C8", "#F0E8E0", "#E0D8D0", "#F8F4EE", "#E8E4DC"],
    "琥珀色系": ["#FFBF00", "#FFA000", "#D4881E", "#FFC04C", "#B87333", "#E0A800", "#FFD060", "#C08818"],
    "玛瑙色系": ["#5A4A5A", "#7A5A6A", "#8A6A7A", "#4A3A4A", "#9A7A8A", "#3A2A3A", "#6A5A6A", "#8A7A8A"],
    "翡翠色系": ["#50C878", "#2E8B57", "#3CB371", "#66CDAA", "#1F7A4A", "#40B060", "#8FD8B0", "#2A9A60"],
    "孔雀色系": ["#00A0B0", "#008B8B", "#1A8A8A", "#2AA8A8", "#006A7A", "#0A9A9A", "#00C8C0", "#3AB8B8"],
    "蝴蝶色系": ["#FF69B4", "#FFB6C1", "#00BFFF", "#FFD700", "#FFA07A", "#7A6BF0", "#FF8FAB", "#A0D8FF"],
    "花卉色系": ["#FFB5C2", "#FF6B8A", "#F0A8B8", "#FF8FA0", "#E07890", "#FFC0CB", "#FFD0DC", "#D86880"],
    "果实色系": ["#FF4D6D", "#FF6B6B", "#E0115F", "#FF7F50", "#C81D4E", "#FF3366", "#FF9060", "#D04060"],
    "香料色系": ["#8B4513", "#CD853F", "#D2691E", "#B8860B", "#A0522D", "#C4874A", "#E8A060", "#7A3A10"],
    "谷物色系": ["#D2B48C", "#E8C9A0", "#C9A96E", "#F0D8B0", "#B98E5A", "#D9B883", "#E0C890", "#A87C4A"],
    # ---- 地域 ----
    "中国传统色系": ["#B03A2E", "#C9A227", "#2A6E8F", "#7A4E6E", "#3E7A5E", "#8B4513", "#E8D8B8", "#1F3A5F"],
    "和风色系": ["#B03A2E", "#E8A33D", "#2A4D8F", "#F0E8D8", "#7A4E6E", "#A8C8B0", "#C9A227", "#3E6E8A"],
    "日式色系": ["#C0C8C0", "#E8D8C8", "#B03A2E", "#3A6E5A", "#F0E8D8", "#7A6E8A", "#A8B0A0", "#C8334B"],
    "北非色系": ["#C8334B", "#E8A33D", "#2A6E6E", "#A67C52", "#D4B48F", "#7A4E3A", "#E0B060", "#4A2A2A"],
    "印度色系": ["#FF4D6D", "#FF9A00", "#008B8B", "#7A2E8A", "#FFD700", "#E0115F", "#FF7F50", "#00A86B"],
    "东南亚色系": ["#E08A3C", "#C8334B", "#2A7A5A", "#F2C14E", "#7A4E6E", "#00A0B0", "#FFD060", "#3A5A4A"],
    "非洲大地色系": ["#8B5A2B", "#A0522D", "#6B4226", "#D2691E", "#5C4033", "#CD853F", "#7A3A1A", "#B08050"],
    "南美热带色系": ["#FF7F00", "#00A0B0", "#C8334B", "#FFD700", "#2E8B57", "#FF69B4", "#00C2FF", "#FFA000"],
    "墨西哥色系": ["#FF4D6D", "#FF9A00", "#2E8B57", "#00A0B0", "#FFD700", "#7A2E8A", "#FF6A3A", "#00BFA0"],
    "希腊色系": ["#FFFFFF", "#3A7CA5", "#E8E0D0", "#2A4D8F", "#F5F0E8", "#A0B8D0", "#B03A2E", "#6A8AB0"],
    "托斯卡纳色系": ["#C8A27A", "#8B5A2B", "#B03A2E", "#D2B48C", "#6B8E5A", "#A67C52", "#E8D0B0", "#5C4033"],
    "普罗旺斯色系": ["#A8B8E8", "#B8A8D0", "#E8D8F0", "#C8B8E0", "#D8C8F0", "#B0A0D8", "#9888C8", "#E0D0F8"],
    "苏格兰色系": ["#2A4D8F", "#B03A2E", "#E8D8C8", "#3E6B33", "#7B3F00", "#5A7A9E", "#C9A227", "#8A5A3A"],
    "爱尔兰色系": ["#2E8B57", "#3E6B33", "#8B4513", "#C9A96E", "#5E7A4A", "#A8C87A", "#D2B48C", "#3A5A2E"],
    "北欧维京色系": ["#3A5A8A", "#7A5A3A", "#8B4513", "#2A3A5A", "#A67C52", "#6B8E5A", "#C0A878", "#4A3A2A"],
    "蒙古色系": ["#8B0000", "#FFD700", "#2A4D8F", "#E8E0D8", "#5C2E00", "#C9A227", "#B03A2E", "#3A5A8A"],
    "藏族色系": ["#B03A2E", "#FFD700", "#2A6E8F", "#C8334B", "#E8A33D", "#7A2E2E", "#C9A227", "#4A2A2A"],
    "傣族色系": ["#2A8A6A", "#FFD700", "#C8334B", "#E8A33D", "#00A0B0", "#8B4513", "#FF6A3A", "#3A6E5A"],
    "彝族色系": ["#C8334B", "#2A3A5A", "#E8A33D", "#7A2E4A", "#2A6E8F", "#D4A060", "#8B4513", "#3A5A8A"],
    # ---- 色彩体系 ----
    "无彩色系": ["#FFFFFF", "#CCCCCC", "#999999", "#666666", "#333333", "#000000", "#E8E8E8", "#B0B0B0"],
    "有彩色系": ["#FF0000", "#FFD700", "#00CC00", "#0000FF", "#800080", "#FF6600", "#00CED1", "#FF1493"],
    "冷色系": ["#00BFFF", "#2A4D8F", "#00CED1", "#3A7CA5", "#6A5ACD", "#2E8B57", "#4A90D9", "#A8D8EA"],
    "暖色系": ["#FF4500", "#FFA500", "#FFD700", "#FF6B6B", "#FF7F50", "#C8334B", "#FFB347", "#E8A33D"],
    "中间色系": ["#8A7A6A", "#9A8A7A", "#A89A8A", "#B8A89A", "#7A6A5A", "#C0B0A0", "#6A5A4A", "#D0C0B0"],
    "原色系": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#00FFFF", "#FF00FF", "#000000", "#FFFFFF"],
    "间色系": ["#FF7F00", "#00FF7F", "#7F00FF", "#00FFFF", "#FF00FF", "#FFFF00", "#808000", "#008080"],
    "复色系": ["#8B5A2B", "#7A6B58", "#5C4033", "#6B5B4A", "#9A8B76", "#4A4238", "#A08060", "#3A3028"],
    "互补色系": ["#FF0000", "#00FFFF", "#00FF00", "#FF00FF", "#0000FF", "#FFFF00", "#FF7F00", "#7F00FF"],
    "邻近色系": ["#FF6B6B", "#FF9A56", "#FFB347", "#FF8C00", "#FF7F50", "#FFA07A", "#FFC04C", "#F4A460"],
    "单色系": ["#E0115F", "#C00E54", "#A00D49", "#800B3E", "#600A33", "#400824", "#FF1A70", "#FF3380"],
    "同类色系": ["#4A90D9", "#3A80C9", "#5AA0E8", "#2A70B8", "#6AB0F0", "#7AC0F8", "#8AD0FF", "#2A5AA8"],
    "对比色系": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF", "#000000", "#FFFFFF"],
    "明度色系": ["#FFFFFF", "#E0E0E0", "#C0C0C0", "#A0A0A0", "#808080", "#404040", "#101010", "#B0B0B0"],
    "纯度色系": ["#FF0000", "#FF8080", "#FFC0C0", "#FFE0E0", "#FF8C8C", "#FFA0A0", "#E00000", "#C00000"],
    "CIE色系": ["#FF0000", "#00FF00", "#0000FF", "#FFD700", "#00CED1", "#FF69B4", "#00A86B", "#FF7F50"],
    "孟塞尔色系": ["#B03A2E", "#E8A33D", "#3E7A5E", "#2A4D8F", "#7A4E6E", "#8B7355", "#C9A227", "#5A6A8A"],
    "奥斯特瓦尔德色系": ["#FF7F50", "#00CED1", "#FFD700", "#8A2BE2", "#32CD32", "#FF69B4", "#00A86B", "#FF4500"],
    "NCS自然色彩体系": ["#FF0000", "#FFD700", "#00A86B", "#00BFFF", "#FF6600", "#A020F0", "#00CED1", "#FFA500"],
    "PCCS实用配色体系": ["#FF4D6D", "#FF9A00", "#00A86B", "#3A7CA5", "#7A5CFF", "#FFB703", "#C8334B", "#00BFA0"],
    "RAL色系": ["#E0E0E0", "#B03A2E", "#3A6E5A", "#2A4D8F", "#FFD700", "#8B7355", "#404040", "#C8A060"],
    "潘通色系": ["#FF6B6B", "#FFB703", "#06D6A0", "#3A7CA5", "#8338EC", "#FF7F50", "#00C2FF", "#F4A261"],
    "DIC色系": ["#B03A2E", "#E8A33D", "#2A4D8F", "#3E7A5E", "#E0D8C8", "#7A4E6E", "#C9A227", "#2A6E8F"],
    "CMYK色系": ["#00FFFF", "#FF00FF", "#FFFF00", "#000000", "#FF0000", "#00FF00", "#0000FF", "#808080"],
    "RGB色系": ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#FFFF00", "#00FFFF", "#FF00FF", "#000000"],
    "HSB色系": ["#FF0000", "#FFD700", "#00FF00", "#00FFFF", "#0000FF", "#FF00FF", "#FF6600", "#00CCFF"],
    "HSL色系": ["#FF0000", "#FFA500", "#00FF00", "#00FFFF", "#8080FF", "#FF80FF", "#FFFF00", "#FF8080"],
    "LAB色系": ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#7A7A7A", "#FFFF00", "#FF00FF", "#00FFFF"],
    "XYZ色系": ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#FFA500", "#800080", "#00FFFF", "#FFFF00"],
    "YUV色系": ["#FF0000", "#00FF00", "#0000FF", "#FFD700", "#00CED1", "#FF69B4", "#00A86B", "#FF7F50"],
    # ---- 风格 ----
    "淡粉色系": ["#FFD1DC", "#FFE4E1", "#FFC0CB", "#FFDAB9", "#FADADD", "#FFE0E6", "#FFB6C1", "#FFF0F5"],
    "明亮色系": ["#FFD700", "#FF6B6B", "#00C2FF", "#7CFC00", "#FF69B4", "#FFA500", "#00E5FF", "#FFB703"],
    "鲜艳色系": ["#FF0000", "#FFD700", "#00FF00", "#00BFFF", "#FF00FF", "#FF4500", "#FFD700", "#7A00FF"],
    "浓烈色系": ["#8B0000", "#B8860B", "#006400", "#00008B", "#8B008B", "#A0522D", "#7A3F00", "#4A0A2A"],
    "深重色系": ["#1A1A2E", "#2F0F0F", "#1F2A1A", "#0A1A2A", "#2A1A2A", "#101018", "#3A2A3A", "#201020"],
    "黑灰色系": ["#000000", "#1A1A1A", "#2E2E2E", "#404040", "#555555", "#6E6E6E", "#808080", "#2A2A2A"],
    "柔和色系": ["#FFD1DC", "#E8D8F0", "#C8E8D8", "#F0E0D0", "#D8E8F0", "#F5E0E8", "#E0F0E0", "#F0E8F8"],
    "雅致色系": ["#B0A8B8", "#A8B8C0", "#C8C0B8", "#9A9AA8", "#D0C8D0", "#B8B0A0", "#A898B0", "#C0B8C8"],
    "清爽色系": ["#00C2FF", "#7CFC00", "#E0FFFF", "#98FB98", "#B0E0E6", "#87CEEB", "#A0F0FF", "#C8F8C8"],
    "清凉色系": ["#00CED1", "#2A9AB8", "#A8E0F0", "#B0E0E6", "#4AB8D0", "#7AC8E0", "#D0F0F8", "#8AD8E8"],
    "温暖色系": ["#FFD700", "#FFA500", "#FF8C00", "#FFB347", "#F4A460", "#FFC04C", "#FFE066", "#E88A00"],
    "古典色系": ["#8B5A2B", "#A0522D", "#7B3F00", "#B8860B", "#6B4226", "#C2A878", "#4A2A10", "#9A6B48"],
    "自然色系": ["#6B8E5A", "#8B5A2B", "#A8C87A", "#5C4033", "#CD853F", "#7A9E5C", "#3E6B33", "#D2B48C"],
    "华丽色系": ["#D4AF37", "#8B0000", "#800080", "#C8334B", "#2A4D8F", "#E8A33D", "#7A2E8A", "#C8A060"],
    "浪漫色系": ["#FF69B4", "#FFB6C1", "#E0115F", "#FFA07A", "#DDA0DD", "#F08080", "#FF8FA0", "#E8A0B8"],
    "跃动色系": ["#FF4500", "#FFD700", "#00FF7F", "#00BFFF", "#FF1493", "#FF8C00", "#00E5FF", "#FF4D6D"],
    "沉稳色系": ["#2F4F4F", "#708090", "#556B2F", "#4A4A5A", "#6B5B8E", "#3A5A7A", "#5A6A7A", "#404858"],
    "宁静色系": ["#A8D8EA", "#B8E0D0", "#C8E0E0", "#D8E8E8", "#A0C8C0", "#E0F0E8", "#B8E8E0", "#D0E8F0"],
    "优雅色系": ["#8A7A9E", "#A89AB8", "#C8BCD0", "#6E6A8A", "#B0A8C8", "#9890B0", "#7A6A8E", "#C0B8D0"],
    "知性色系": ["#2F4F6F", "#4A6E8A", "#708090", "#5A7A9E", "#3A5A7A", "#7A8AA8", "#2A4A6A", "#90A0B8"],
    "活力色系": ["#FF4D6D", "#FF9A00", "#06D6A0", "#FFB703", "#118AB2", "#EF476F", "#00C2FF", "#FF7F50"],
    "青春色系": ["#FFD1DC", "#B5EAD7", "#A5D8FF", "#FFD3A5", "#C7CEEA", "#FF9AA2", "#FFF1A8", "#B8F0D9"],
    "成熟色系": ["#8B4513", "#5C4033", "#A0522D", "#6B4226", "#7B4A2A", "#9A6B48", "#B08060", "#4A3018"],
    "摩登色系": ["#2E2E2E", "#FF4D6D", "#00C2FF", "#FFFFFF", "#FFB703", "#1A1A1A", "#00A86B", "#E8E8E8"],
    "乡村色系": ["#8B5A2B", "#A0522D", "#6B8E5A", "#C9A96E", "#5C4033", "#B8860B", "#7A6B58", "#D2B48C"],
    "田园色系": ["#A8C87A", "#FFD700", "#8BC34A", "#FFB703", "#6BA85C", "#E8D8B0", "#C8E090", "#F0E0A0"],
    "海滨色系": ["#4AB8D0", "#A8D8EA", "#F0D8A8", "#2A9AB8", "#FFE0C0", "#7AC8E0", "#D8E8F0", "#C0A878"],
    "山野色系": ["#5E7A4A", "#6B8E5A", "#8B5A2B", "#4A6E3A", "#A8C87A", "#7A5C3A", "#3A5A2E", "#C9A96E"],
    # ---- 传统单色 ----
    "赤色系": ["#FF0000", "#E0115F", "#C8334B", "#B03A2E", "#FF4D6D", "#FF6B6B", "#D04A60", "#A02A3A"],
    "黄色系": ["#FFD700", "#FFA500", "#FFC04C", "#FFE066", "#F4A460", "#FFB347", "#E0C030", "#FFF080"],
    "青色系": ["#00CED1", "#00A0B0", "#00BFFF", "#20B2AA", "#00A86B", "#1A8A8A", "#40C8C0", "#00D0D8"],
    "白色系": ["#FFFFFF", "#F8F8F8", "#F0F0F0", "#FAFAFA", "#F5F5F5", "#ECECEC", "#FFF8F0", "#F0F8FF"],
    "黑色系": ["#000000", "#111111", "#1A1A1A", "#0A0A0A", "#222222", "#2A2A2A", "#151515", "#080808"],
    "朱红色系": ["#FF4D00", "#E0342C", "#FF2E00", "#D02A20", "#FF5A2E", "#C0281C", "#FF6A38", "#B02218"],
    "胭脂色系": ["#C8334B", "#D04A60", "#B02A40", "#E0556A", "#A02030", "#D06070", "#E87888", "#B83850"],
    "绯红色系": ["#DC143C", "#C81D4E", "#E0115F", "#B0171F", "#D43B5A", "#C02040", "#E84060", "#A01830"],
    "绛红色系": ["#722F37", "#8B2635", "#6A1F2C", "#7A2A38", "#A03A4A", "#5E1A26", "#904050", "#4A1420"],
    "大红系": ["#FF0000", "#E60000", "#CC0000", "#FF2020", "#D00000", "#FF4040", "#B00000", "#FF6060"],
    "丹色系": ["#C03028", "#D04030", "#A02820", "#E05038", "#B8382A", "#D85038", "#E87058", "#90201A"],
    "橙色系": ["#FF7F00", "#FFA500", "#FF8C00", "#FF9A56", "#E8800A", "#FFB347", "#FF6A00", "#D87810"],
    "鹅黄色系": ["#F0D050", "#E8C830", "#F8E070", "#D8B020", "#F0D860", "#E0C038", "#FFF080", "#C8A818"],
    "柳黄色系": ["#D0C050", "#C0B040", "#E0D060", "#B0A038", "#D8C858", "#A89030", "#E8D868", "#988828"],
    "杏黄色系": ["#F0C090", "#E8B070", "#F8D0A0", "#D8A060", "#F0C8A0", "#E0B880", "#FFE0C0", "#C89050"],
    "金黄色系": ["#FFD700", "#E0B800", "#FFC04C", "#D4A010", "#FFE066", "#C8A020", "#FFD850", "#B09018"],
    "香槟色系": ["#F7E7CE", "#F0DCC8", "#FFEBD6", "#E8D0B0", "#FFF0DC", "#E0C8A8", "#F8E8D0", "#D8C0A0"],
    "苍黄色系": ["#E8D8A0", "#D8C888", "#F0E0B0", "#C8B878", "#E0D0A0", "#D0C090", "#F8E8C0", "#B8A868"],
    "草绿色系": ["#7CCD7C", "#6BA85C", "#8FBC8F", "#9ECB7A", "#5E9E4A", "#7AAF6A", "#B0E0A0", "#4A8838"],
    "竹青色系": ["#6AA85A", "#5A9850", "#7AB86A", "#4A8840", "#8AC87A", "#66A85C", "#98D088", "#3A7830"],
    "松绿色系": ["#1F7A4A", "#2E8B57", "#3A9A5A", "#268A50", "#17804A", "#2A9058", "#40AA68", "#0A6A38"],
    "柏绿色系": ["#1A5C3A", "#226A44", "#2A7A4E", "#1E6A40", "#16704A", "#2E8054", "#3A8A5A", "#0E5030"],
    "柳绿色系": ["#9ACD32", "#8AB02A", "#AAD83C", "#7AA020", "#B8E04A", "#90C030", "#C0E858", "#6A8818"],
    "黛青色系": ["#2A4A5A", "#1A3A4A", "#2E5A6A", "#264A5A", "#3A6A7A", "#20384A", "#466A7A", "#183040"],
    "黛蓝色系": ["#2A3A6E", "#1E2E5A", "#2E4A8A", "#263A6A", "#3A4A9E", "#1A2A4A", "#4050A8", "#16263E"],
    "天青色系": ["#7AC8E0", "#8AD8E8", "#6AB8D0", "#9AE8F0", "#5AA8C8", "#7AD0E0", "#A8E8F8", "#4A98B8"],
    "月白色系": ["#E8F0F8", "#D8E8F0", "#F0F8FF", "#C8E0F0", "#E0F0F8", "#D8F0F8", "#F8FCFF", "#B8D8E8"],
    "皎月色系": ["#F0F8FF", "#E8F4FF", "#F8FCFF", "#E0F0FF", "#F0FAFF", "#E8F8FF", "#FFFFFF", "#D8ECFF"],
    "霁蓝色系": ["#4A6A9A", "#5A7AAA", "#3A5A8A", "#6A8ABA", "#2A4A7A", "#7A9ACA", "#8AAAC8", "#3A5A8A"],
    "藏蓝色系": ["#1A2A5A", "#2A3A6A", "#20305A", "#3A4A7A", "#16264E", "#1E2E5E", "#4A5A8A", "#0E1E42"],
    "宝蓝色系": ["#1A4DA0", "#2A5AB0", "#1A45A0", "#2050B0", "#2A65B8", "#15409E", "#3A6AC8", "#0E3A8A"],
    "绀青色系": ["#2A3A6E", "#1E2E5E", "#364A7E", "#2A3A7A", "#40508E", "#1A2A5A", "#4A5A9E", "#12224E"],
    "藕荷色系": ["#D8C0D8", "#C8B0C8", "#E0D0E0", "#B8A0B8", "#D0C0D0", "#E8D8E8", "#C0B0C0", "#F0E8F0"],
    "丁香色系": ["#C8A0D0", "#B888C0", "#D8B0E0", "#A878B8", "#D0A8D8", "#B890C8", "#E8C8F0", "#9878A8"],
    "紫棠色系": ["#5A3A6A", "#4A2A5A", "#6A4A7A", "#3A1A4A", "#7A5A8A", "#2A0A3A", "#8A6A9A", "#503060"],
    "葡萄色系": ["#6A2A6E", "#7A3A7A", "#5A1A5E", "#8A4A8A", "#4A1A4E", "#9A5A9A", "#B070A8", "#3A0A3E"],
    "灰色系": ["#B0B0B0", "#A0A0A0", "#C0C0C0", "#909090", "#D0D0D0", "#808080", "#E0E0E0", "#707070"],
    "褐色系": ["#8B5A2B", "#6B4226", "#A0522D", "#7B4A2A", "#9A6B48", "#5C4033", "#C08A50", "#4A3018"],
    "墨色系": ["#1A1A2A", "#101020", "#2A2A3A", "#080818", "#222232", "#0E0E1E", "#303044", "#06060E"],
    "玄色系": ["#000000", "#0A0A0A", "#111111", "#050505", "#1A1A1A", "#151515", "#202020", "#080808"],
    "缁色系": ["#1A1A1A", "#2A2A2A", "#222222", "#333333", "#181818", "#2E2E2E", "#3D3D3D", "#101010"],
    # ---- 颜色环 ----
    "红色系": ["#FF0000", "#E0115F", "#DC143C", "#FF4040", "#C8334B", "#FF6B6B", "#B0171F", "#FF8080"],
    "橙红色系": ["#FF4500", "#FF4D2E", "#E0342C", "#FF5A2E", "#D02A20", "#FF6A3A", "#FF2E00", "#C0281C"],
    "橙黄色系": ["#FFA000", "#FFB300", "#FFC04C", "#FF8F00", "#F4A460", "#FF9E2E", "#FFD060", "#E08800"],
    "黄绿色系": ["#9ACD32", "#ADFF2F", "#7FBF2A", "#B8E04A", "#8AB02A", "#C8F04E", "#6AA018", "#E0FF80"],
    "绿色系": ["#00A86B", "#2E8B57", "#32CD32", "#3CB371", "#228B22", "#40B060", "#66D88A", "#1A7A4A"],
    "蓝绿色系": ["#00CED1", "#20B2AA", "#00A0B0", "#1A8A8A", "#48D1CC", "#008B8B", "#2AB8B8", "#00E0D8"],
    "蓝色系": ["#2A5AB0", "#1A4DA0", "#3A6AC8", "#2050B0", "#4A7AD8", "#15409E", "#5A8AE0", "#0E3A8A"],
    "蓝紫色系": ["#5A4A9E", "#6A5ACD", "#4A3A8E", "#7A6AD8", "#3A2A7A", "#8A7AE0", "#6A5AB0", "#2A1A6A"],
    "紫色系": ["#800080", "#8A2BE2", "#A020F0", "#6A0DAD", "#9400D3", "#7A00C0", "#B060E0", "#5A0A8A"],
    "紫红色系": ["#C71585", "#DB7093", "#C833B4", "#A02070", "#E0115F", "#B0177A", "#E068A0", "#8A0A5A"],
    "粉红色系": ["#FFB6C1", "#FFC0CB", "#FF69B4", "#FFA0B0", "#FF90A0", "#FFD0D8", "#FF6A90", "#FFE0E8"],
    "棕红色系": ["#8B4513", "#A0522D", "#B03028", "#6B4226", "#9A5A3A", "#7A3A2A", "#C06840", "#5A2A1A"],
    "棕黄色系": ["#C8A060", "#D4A030", "#B8860B", "#CD853F", "#A0825A", "#D0A040", "#E0B060", "#907030"],
    "橄榄绿色系": ["#556B2F", "#6B8E23", "#708238", "#4A5A24", "#8A9A48", "#5E6B2A", "#A0B060", "#3A4A1A"],
    "灰蓝色系": ["#6A7A9E", "#5A6A8A", "#7A8AA8", "#4A5A7A", "#8A9AB8", "#3A4A6A", "#98A8C0", "#2A3A5A"],
    "灰紫色系": ["#8A7A9E", "#9A8AB0", "#7A6A8E", "#A89AB8", "#6A5A7E", "#B0A0C0", "#5A4A6E", "#C0B0D0"],
    "米黄色系": ["#F5DEB3", "#F0D8A8", "#E8D0A0", "#F8E8C0", "#E0C890", "#FAEBD7", "#FFF0D8", "#D8C080"],
    "奶白色系": ["#FFF8E7", "#FFF5E1", "#FFF0DB", "#FFF8F0", "#FFFAF0", "#FDF5E6", "#FFF0E8", "#FFFFF8"],
    # ---- 金属/质感 ----
    "象牙色系": ["#FFFFF0", "#FFF8E7", "#FFF5DC", "#FFF8F0", "#FFFAE0", "#FFF0D8", "#FFFFF8", "#F8F0E0"],
    "米色系": ["#F5F5DC", "#E8E0C8", "#DCD0B8", "#F0ECD8", "#E0D8C0", "#D8D0B0", "#F8F4E8", "#C8C0A8"],
    "裸色系": ["#E8C4A0", "#F0D0B8", "#D8B890", "#F5DCC8", "#E0C0A0", "#D0A878", "#F8E8D8", "#C8A080"],
    "肤色系": ["#FFE0BD", "#F8D0B0", "#FFD6A0", "#E8C09A", "#F0CBA0", "#D8B090", "#FFE8D0", "#E0B080"],
    "陶土色系": ["#C0683A", "#D07848", "#A05830", "#B86838", "#D88850", "#904A28", "#E89868", "#7A3A20"],
    "水泥色系": ["#B8B8B8", "#A8A8A8", "#C8C8C8", "#989898", "#D0D0D0", "#888888", "#E0E0E0", "#787878"],
    "混凝土色系": ["#A0A0A0", "#909090", "#B0B0B0", "#808080", "#C0C0C0", "#787878", "#B8B8B8", "#6E6E6E"],
    "沥青色系": ["#2A2A2A", "#1F1F1F", "#333333", "#262626", "#3A3A3A", "#1A1A1A", "#404040", "#151515"],
    "石墨色系": ["#3A3A3A", "#4A4A4A", "#2A2A2A", "#555555", "#404040", "#303030", "#606060", "#282828"],
    "碳灰色系": ["#505050", "#404040", "#606060", "#383838", "#555555", "#2E2E2E", "#6E6E6E", "#262626"],
    "烟灰色系": ["#C0C0C0", "#B0B0B0", "#D0D0D0", "#A0A0A0", "#D8D8D8", "#989898", "#E8E8E8", "#888888"],
    "银灰色系": ["#C0C0C0", "#D3D3D3", "#A9A9A9", "#E0E0E0", "#B8B8B8", "#CCCCCC", "#F0F0F0", "#989898"],
    "锡色系": ["#8E8E8E", "#9E9E9E", "#7E7E7E", "#AAAAAA", "#8A8A8A", "#969696", "#B8B8B8", "#6E6E6E"],
    "铅色系": ["#6E6E6E", "#5E5E5E", "#7E7E7E", "#4E4E4E", "#8A8A8A", "#585858", "#9A9A9A", "#404040"],
    "铁锈色系": ["#8B3A2A", "#A0522D", "#7A2E1E", "#B8683A", "#6B2A1A", "#9A4A2A", "#C87848", "#5A2012"],
    "铜绿色系": ["#3A7A6A", "#2A6A5A", "#4A8A7A", "#1A5A4A", "#5A9A8A", "#2E7A68", "#6AAA98", "#0E4A3A"],
    "青铜色系": ["#8B6B4A", "#A07A50", "#7A5A3A", "#B88A58", "#6A4E30", "#9A7048", "#C8A068", "#5A3E28"],
    "古铜色系": ["#7A4A2A", "#8B5A32", "#6A3E22", "#9A6840", "#5C341E", "#A87848", "#B88858", "#4A2A18"],
    "黄铜色系": ["#B5A642", "#C9B037", "#A08A2E", "#D1BA5A", "#9A8A32", "#BFA85A", "#E0C86A", "#8A7A28"],
    "玫瑰金色系": ["#B76E79", "#C98A94", "#A85A66", "#D49AA4", "#9E4E5A", "#E0A8B0", "#F0C8CE", "#8A4250"],
    "白金系": ["#E5E4E2", "#F0EFEE", "#D8D7D6", "#F5F4F3", "#D0CFCE", "#FAF9F8", "#C8C7C6", "#E8E7E6"],
    "铂金系": ["#E5E4E2", "#EAE8E6", "#DCDAD8", "#F0EEEC", "#D5D3D1", "#E8E6E4", "#C8C6C4", "#F5F4F2"],
}

# 默认快捷键：- 开始模拟，= 关闭模拟
DEFAULT_HOTKEY_START = {"type": "keyboard", "key": int(Qt.Key_Minus), "mods": 0, "display": "-"}
DEFAULT_HOTKEY_STOP = {"type": "keyboard", "key": int(Qt.Key_Equal), "mods": 0, "display": "="}

# 多媒体按键（v1.2.17）：FN+F1~F12 等多功能键大多发送以下媒体虚拟键码，
# RegisterHotKey 可直接注册触发（名称, Windows VK）。v1.2.18 扩展更多 FN 功能键。
MEDIA_KEYS = [
    ("静音", 0xAD), ("音量减小", 0xAE), ("音量增大", 0xAF),
    ("下一曲", 0xB0), ("上一曲", 0xB1), ("停止媒体", 0xB2), ("播放/暂停", 0xB3),
    ("浏览器后退", 0xA6), ("浏览器前进", 0xA7), ("浏览器刷新", 0xA8),
    ("浏览器停止", 0xA9), ("搜索", 0xAA), ("收藏夹", 0xAB),
    ("浏览器主页", 0xAC), ("打开邮件", 0xB4), ("媒体选择", 0xB5),
    ("计算器", 0xB6), ("我的电脑", 0xB7), ("休眠", 0x5F),
]


# =========================================================
# 鼠标模拟点击后端
# =========================================================
_PYNPUT = None
try:
    from pynput.mouse import Controller as _PynputController
    from pynput.mouse import Button as _PynputButton

    _PYNPUT = (_PynputController(), _PynputButton)
except Exception:
    _PYNPUT = None

# Windows mouse_event 标志：按键 -> (按下, 抬起)
_MOUSE_FLAGS = {
    "left":   (0x0002, 0x0004),  # MOUSEEVENTF_LEFTDOWN / LEFTUP
    "right":  (0x0008, 0x0010),  # MOUSEEVENTF_RIGHTDOWN / RIGHTUP
    "middle": (0x0020, 0x0040),  # MOUSEEVENTF_MIDDLEDOWN / MIDDLEUP
}


def simulate_click(button):
    """在当前鼠标位置模拟一次指定按键的点击。button: 'left' / 'middle' / 'right'"""
    if _PYNPUT is not None:
        controller, btn = _PYNPUT
        controller.click(getattr(btn, button))
    elif _WIN32:
        down, up = _MOUSE_FLAGS[button]
        user32 = ctypes.windll.user32
        user32.mouse_event(down, 0, 0, 0, 0)
        user32.mouse_event(up, 0, 0, 0, 0)
    else:
        raise RuntimeError("无可用的鼠标模拟后端，请安装 pynput")


# =========================================================
# 快捷键引擎（v1.2.0）：键盘（RegisterHotKey）+ 手柄按钮（pygame 线程）
# =========================================================
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
# 低层键盘钩子（v1.2.20）：监听媒体/OEM 键原始 VK，RegisterHotKey 对部分键注册不可靠/无效
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong), ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_ulong),
    ]

# Qt.Key -> Windows VK 映射（RegisterHotKey 用）
_QT_KEY_TO_VK = {}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _QT_KEY_TO_VK[getattr(Qt, f"Key_{_c}")] = ord(_c)
for _d in "0123456789":
    _QT_KEY_TO_VK[getattr(Qt, f"Key_{_d}")] = ord(_d)
for _i in range(1, 25):
    _QT_KEY_TO_VK[getattr(Qt, f"Key_F{_i}")] = 0x6F + _i
_QT_KEY_TO_VK.update({
    Qt.Key_Return: 0x0D, Qt.Key_Enter: 0x0D, Qt.Key_Escape: 0x1B,
    Qt.Key_Space: 0x20, Qt.Key_Tab: 0x09, Qt.Key_Backspace: 0x08,
    Qt.Key_Delete: 0x2E, Qt.Key_Insert: 0x2D, Qt.Key_Home: 0x24,
    Qt.Key_End: 0x23, Qt.Key_PageUp: 0x21, Qt.Key_PageDown: 0x22,
    Qt.Key_Up: 0x26, Qt.Key_Down: 0x28, Qt.Key_Left: 0x25, Qt.Key_Right: 0x27,
    Qt.Key_Minus: 0xBD, Qt.Key_Equal: 0xBB,
    Qt.Key_Comma: 0xBC, Qt.Key_Period: 0xBE,
    Qt.Key_Semicolon: 0xBA, Qt.Key_Slash: 0xBF,
    Qt.Key_Backslash: 0xDC, Qt.Key_BracketLeft: 0xDB, Qt.Key_BracketRight: 0xDD,
    Qt.Key_QuoteLeft: 0xC0, Qt.Key_Apostrophe: 0xDE,
})
# Qt 媒体/功能键 -> 媒体 VK（v1.2.18 补基础映射；v1.2.19 补全浏览器/Launch/Standby 等——
# 否则 KSE 捕获到 Favorites/Launch0 等 Qt 键时 _qt_key_to_vk 返回 0 导致不注册、只显示不生效）
_QT_KEY_TO_VK.update({
    Qt.Key_VolumeMute: 0xAD, Qt.Key_VolumeDown: 0xAE, Qt.Key_VolumeUp: 0xAF,
    Qt.Key_MediaNext: 0xB0, Qt.Key_MediaPrevious: 0xB1, Qt.Key_MediaStop: 0xB2,
    Qt.Key_MediaPlay: 0xB3, Qt.Key_MediaPause: 0xB3, Qt.Key_MediaTogglePlayPause: 0xB3,
    Qt.Key_LaunchMail: 0xB4, Qt.Key_LaunchMedia: 0xB5,
    Qt.Key_Back: 0xA6, Qt.Key_Forward: 0xA7, Qt.Key_Refresh: 0xA8, Qt.Key_Stop: 0xA9,
    Qt.Key_Search: 0xAA, Qt.Key_Favorites: 0xAB, Qt.Key_HomePage: 0xAC,
    Qt.Key_Standby: 0x5F, Qt.Key_Sleep: 0x5F, Qt.Key_Calculator: 0xB6,
    Qt.Key_Launch0: 0xB6, Qt.Key_Launch1: 0xB7,  # LaunchApp1/2（键盘若发 0xB6/0xB7 则生效）
    # v1.2.20：补全 Launch2~F/G/H 与 MediaRecord（供低层钩子监听原始 VK）
    Qt.Key_Launch2: 0xB8, Qt.Key_Launch3: 0xB9, Qt.Key_Launch4: 0xBA,
    Qt.Key_Launch5: 0xBB, Qt.Key_Launch6: 0xBC, Qt.Key_Launch7: 0xBD,
    Qt.Key_Launch8: 0xBE, Qt.Key_Launch9: 0xBF, Qt.Key_LaunchA: 0xC0,
    Qt.Key_LaunchB: 0xC1, Qt.Key_LaunchC: 0xC2, Qt.Key_LaunchD: 0xC3,
    Qt.Key_LaunchE: 0xC4, Qt.Key_LaunchF: 0xC5, Qt.Key_LaunchG: 0xC6, Qt.Key_LaunchH: 0xC7,
    Qt.Key_MediaRecord: 0xB3,
})


def _qt_key_to_vk(qkey):
    """Qt.Key 枚举 -> Windows 虚拟键码（无映射返回 0）"""
    return _QT_KEY_TO_VK.get(int(qkey), 0)


def _qt_mods_to_win(qmods):
    """Qt 修饰符 -> Windows MOD_* 标志"""
    try:
        qmods = int(qmods)
    except Exception:
        qmods = int(getattr(qmods, "value", 0) or 0)
    m = 0
    if qmods & int(getattr(Qt.ShiftModifier, "value", 0)):
        m |= 0x0004  # MOD_SHIFT
    if qmods & int(getattr(Qt.ControlModifier, "value", 0)):
        m |= 0x0002  # MOD_CONTROL
    if qmods & int(getattr(Qt.AltModifier, "value", 0)):
        m |= 0x0001  # MOD_ALT
    if qmods & int(getattr(Qt.MetaModifier, "value", 0)):
        m |= 0x0008  # MOD_WIN
    return m


class _HotkeyNativeFilter(QAbstractNativeEventFilter):
    """Qt 原生事件过滤器（单继承 QAbstractNativeEventFilter，避免与 QObject 双继承失效）。

    坑：PySide6 中若一个类同时继承 QObject 和 QAbstractNativeEventFilter，其
    nativeEventFilter 重写不会被调用（热键注册成功但 WM_HOTKEY 无法触发）。
    """

    def __init__(self, manager):
        super().__init__()
        self._manager = manager

    def nativeEventFilter(self, eventType, message):
        return self._manager._handle_native_event(message)


class HotkeyManager(QObject):
    """统一管理开始/关闭模拟的快捷键（键盘全局热键 + 手柄按钮）。

    快捷键配置格式 dict：
      keyboard: {"type": "keyboard", "key": <Qt.Key int>, "mods": <Qt 修饰符 int>, "display": str}
      gamepad : {"type": "gamepad", "button": <按钮号 int>, "display": str}
    """

    triggered = Signal(str)                 # "start" / "stop"
    gamepad_button_captured = Signal(int)   # 捕获模式下手柄按钮号
    gamepad_button_pressed = Signal(int, str)  # (按钮号, "start"/"stop"/""未绑定) v1.2.16 实时反馈

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_cfg = None
        self._stop_cfg = None
        self._capture_button = False
        self._gamepad_thread = None
        self._gamepad_stop_event = threading.Event()  # set=请求停止；初始已停止（v1.2.15 用 Event 替代布尔）
        self._gamepad_stop_event.set()
        self._filter_installed = False
        self._native_filter = _HotkeyNativeFilter(self)
        self._hotkey_actions = {}          # v1.2.20：媒体/功能键 VK -> "start"/"stop"（低层钩子监听）
        self._ll_hook = None               # 低层键盘钩子句柄
        self._ll_proc = None               # 回调引用（防 GC）
        self._ll_last = 0                  # 上次触发时间（防 auto-repeat）
        self._events = queue.Queue()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(40)  # v1.2.15：更灵敏（60→40ms）
        self._poll_timer.timeout.connect(self._poll_events)
        self._poll_timer.start()

    # ---------- 应用配置 ----------
    def apply(self, start_cfg, stop_cfg, allow_keyboard=True):
        self._start_cfg = start_cfg
        self._stop_cfg = stop_cfg
        if allow_keyboard:
            self._register_keyboard()
        else:
            self._unregister_keyboard()
        self._ensure_ll_hook()
        self._restart_gamepad()

    def shutdown(self):
        """关闭时注销热键、移除过滤器、停止手柄监听"""
        self._stop_gamepad()
        self._unregister_keyboard()
        self._remove_filter()
        self._stop_ll_hook()

    # ---------- 键盘热键（RegisterHotKey 普通键 + 低层钩子监听媒体/OEM 键）----------
    def _unregister_keyboard(self):
        self._hotkey_actions = {}
        self._stop_ll_hook()
        if not _WIN32:
            return
        try:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(None, 1)  # id 1 = start
            user32.UnregisterHotKey(None, 2)  # id 2 = stop
        except Exception:
            pass

    def _register_keyboard(self):
        self._unregister_keyboard()
        if not _WIN32:
            return
        self._hotkey_actions = {}
        try:
            user32 = ctypes.windll.user32
            for hid, cfg in ((1, self._start_cfg), (2, self._stop_cfg)):
                if cfg and cfg.get("type") == "keyboard":
                    if cfg.get("media"):
                        # 多媒体按键：key 直接是 Windows VK（v1.2.17）
                        vk = int(cfg.get("key") or 0)
                    elif cfg.get("raw_vk"):
                        # KSE 捕获的原生 VK（v1.2.20）：直接注册，不再 Qt 映射
                        vk = int(cfg.get("key") or 0)
                    else:
                        vk = _qt_key_to_vk(cfg.get("key"))
                    if not vk:
                        continue
                    action = "start" if hid == 1 else "stop"
                    mod = _qt_mods_to_win(cfg.get("mods", 0)) | MOD_NOREPEAT
                    if vk >= 0xA6 or vk == 0x5F:
                        mod = 0  # 媒体键无修饰符
                    # 标准媒体键（0xA6~0xB7、0x5F）RegisterHotKey 已验证全部可注册；失败才用钩子兜底（v1.2.20）
                    registered = user32.RegisterHotKey(None, hid, mod, vk)
                    if not registered:
                        self._hotkey_actions[vk] = action
            self._ensure_filter_installed()
            self._ensure_ll_hook()
        except Exception:
            pass

    def _ensure_ll_hook(self):
        """安装低层键盘钩子（幂等），监听 _hotkey_actions 中的媒体/OEM 键 VK（v1.2.20）"""
        if not _WIN32 or self._ll_hook is not None or not self._hotkey_actions:
            return
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p)
            self._ll_proc = HOOKPROC(self._ll_callback)
            self._ll_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._ll_proc, kernel32.GetModuleHandleW(None), 0)
        except Exception:
            self._ll_hook = None

    def _stop_ll_hook(self):
        """卸载低层键盘钩子"""
        if not _WIN32 or self._ll_hook is None:
            return
        try:
            ctypes.windll.user32.UnhookWindowsHookEx(self._ll_hook)
        except Exception:
            pass
        self._ll_hook = None
        self._ll_proc = None

    def _ll_callback(self, nCode, wParam, lParam):
        """低层键盘钩子回调：媒体/OEM 键按下匹配 VK 即入队触发（走 _poll_events）"""
        if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            try:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = int(kb.vkCode)
                action = self._hotkey_actions.get(vk)
                if action:
                    now = int(time.time() * 1000)
                    if now - self._ll_last > 250:  # 防 auto-repeat 重复触发
                        self._ll_last = now
                        self._events.put(("action", action))
            except Exception:
                pass
        try:
            return ctypes.windll.user32.CallNextHookEx(self._ll_hook, nCode, wParam, lParam)
        except Exception:
            return 0

    def _ensure_filter_installed(self):
        if self._filter_installed:
            return
        app = QApplication.instance()
        if app is None:
            return
        app.installNativeEventFilter(self._native_filter)
        self._filter_installed = True

    def _remove_filter(self):
        if not self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeNativeEventFilter(self._native_filter)
            except Exception:
                pass
        self._filter_installed = False

    def _handle_native_event(self, message):
        """由 _HotkeyNativeFilter 委托调用，处理 WM_HOTKEY"""
        if not _WIN32:
            return False, 0
        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0
        if msg.message == WM_HOTKEY:
            if msg.wParam == 1:
                self.triggered.emit("start")
            elif msg.wParam == 2:
                self.triggered.emit("stop")
        return False, 0

    # ---------- 手柄热键（pygame 后台线程）----------
    def _restart_gamepad(self):
        """按配置启停手柄监听线程：先停旧线程（确保退出），再按需启动（v1.2.15 杜绝多线程并存抢 pygame 事件）"""
        need = (
            (self._start_cfg or {}).get("type") == "gamepad"
            or (self._stop_cfg or {}).get("type") == "gamepad"
        )
        self._stop_gamepad()
        if need:
            self._start_gamepad()

    def _start_gamepad(self):
        """幂等启动手柄监听线程；已存活则复用（避免多个线程同时 pygame.event.get() 抢事件）"""
        if self._gamepad_thread and self._gamepad_thread.is_alive():
            return self._gamepad_thread
        self._gamepad_stop_event.clear()
        t = threading.Thread(target=self._gamepad_loop, daemon=True)
        self._gamepad_thread = t
        t.start()
        return t

    def _stop_gamepad(self):
        """停止手柄线程并等待其真正退出（确保新旧线程不并存）"""
        if not self._gamepad_thread:
            return
        self._gamepad_stop_event.set()
        t = self._gamepad_thread
        if t.is_alive():
            t.join(timeout=1.0)
            if t.is_alive():
                t.join(timeout=1.0)  # 二次等待，避免僵尸线程与新线程并存
        self._gamepad_thread = None

    def _register_joysticks(self, pygame_mod):
        """注册所有已连接手柄设备（v1.2.14 修复）。

        pygame 必须对每个检测到的手柄调用 Joystick(i).init() 才会产生
        JOYBUTTONDOWN 事件；未注册的设备按键无响应。返回已注册设备列表。
        """
        joys = []
        try:
            for i in range(pygame_mod.joystick.get_count()):
                j = pygame_mod.joystick.Joystick(i)
                j.init()
                joys.append(j)
        except Exception:
            pass
        return joys

    def _gamepad_loop(self):
        try:
            # 抑制 pygame 横幅：环境变量必须在 import pygame 之前设置
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame
            pygame.init()
            pygame.joystick.init()
        except Exception:
            return
        joys = []  # 已注册的手柄设备
        while not self._gamepad_stop_event.is_set():
            try:
                # 热插拔检测：手柄数量变化时重新注册
                if len(joys) != pygame.joystick.get_count():
                    joys = self._register_joysticks(pygame)
                pygame.event.pump()
                for e in pygame.event.get():
                    if e.type == pygame.JOYBUTTONDOWN:
                        if self._capture_button:
                            self._events.put(("capture", e.button))
                        else:
                            sc = self._start_cfg
                            tc = self._stop_cfg
                            if sc and sc.get("type") == "gamepad" and e.button == sc.get("button"):
                                self._events.put(("action", "start"))
                                self._events.put(("feedback", (e.button, "start")))
                            elif tc and tc.get("type") == "gamepad" and e.button == tc.get("button"):
                                self._events.put(("action", "stop"))
                                self._events.put(("feedback", (e.button, "stop")))
                            else:
                                self._events.put(("feedback", (e.button, "")))
            except Exception:
                pass
            time.sleep(0.005)  # v1.2.15：5ms 高频轮询，按键响应更灵敏

    def capture_gamepad_button(self):
        """进入手柄按钮捕获模式，下一次按下任意手柄按钮时发出 gamepad_button_captured"""
        self._start_gamepad()
        self._capture_button = True

    def cancel_capture(self):
        self._capture_button = False

    def _poll_events(self):
        try:
            while True:
                kind, value = self._events.get_nowait()
                if kind == "action":
                    self.triggered.emit(value)
                elif kind == "capture":
                    self._capture_button = False
                    self.gamepad_button_captured.emit(value)
                elif kind == "feedback":
                    self.gamepad_button_pressed.emit(value[0], value[1])
        except queue.Empty:
            pass


class CaptureKeySequenceEdit(QKeySequenceEdit):
    """捕获按键时记录 Windows 原生虚拟键码（v1.2.20：媒体/OEM 键按真实 VK 注册，根治"有显示不生效"）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._native_vk = 0

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        try:
            vk = int(event.nativeVirtualKey())
            if vk:
                self._native_vk = vk
        except Exception:
            pass

    def clear(self):
        super().clear()
        self._native_vk = 0


class ClickSelectSpinBox(QSpinBox):
    """点击数字框自动全选文本，方便直接输入新数值（v1.2.4，v1.2.5 增强）。

    - auto_select 开关（默认 True），由设置控制
    - 仅对文本区域点击全选（点上下箭头不触发）
    - 延迟到事件分发完成后全选，避免被内部光标逻辑覆盖
    - 获得焦点时也全选
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auto_select = True

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.auto_select and event.button() == Qt.LeftButton:
            if self.lineEdit().geometry().contains(event.position().toPoint()):
                QTimer.singleShot(0, self.selectAll)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.auto_select:
            QTimer.singleShot(0, self.selectAll)


class ClickProgressBar(QWidget):
    """细进度条：显示模拟点击次数进度，用所选色系渐变色填充（v1.2.6）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._max = 100
        self._colors = COLOR_THEMES["马卡龙色系"]
        self.setFixedHeight(4)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_bar_height(self, height):
        """设置进度条粗细（像素，v1.2.8）"""
        self.setFixedHeight(max(1, int(height)))

    def set_colors(self, colors):
        if colors:
            self._colors = list(colors)
            self.update()

    def set_value(self, value):
        self._value = value % self._max
        self.update()

    def set_max(self, m):
        self._max = max(1, int(m))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(220, 220, 220))  # 淡灰背景，与分隔线一致
        ratio = max(0.0, min(1.0, self._value / self._max))
        fill_w = int(rect.width() * ratio)
        if fill_w <= 0:
            return
        grad = QLinearGradient(0, 0, fill_w, 0)
        n = len(self._colors)
        for i, c in enumerate(self._colors):
            grad.setColorAt(i / max(n - 1, 1), QColor(c))
        painter.fillRect(QRect(rect.left(), rect.top(), fill_w, rect.height()), grad)


class ColorSwatchStrip(QWidget):
    """色板预览条：水平显示一组颜色小方块（用于设置里预览色系，v1.2.7）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = []
        self.setMinimumWidth(80)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_colors(self, colors):
        self._colors = list(colors) if colors else []
        self.setToolTip("  ·  ".join(self._colors) if self._colors else "")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        n = len(self._colors)
        if n == 0:
            painter.fillRect(rect, QColor(245, 245, 245))
            return
        w = rect.width() / n
        pen = QColor(210, 210, 210)
        for i, c in enumerate(self._colors):
            sw = QRect(int(rect.left() + i * w), rect.top(), int(w) + 1, rect.height())
            painter.fillRect(sw, QColor(c))
            painter.setPen(pen)
            painter.drawRect(sw)


class TestIndicator(QLabel):
    """测试模式指示灯：待机黄 / 生效绿(闪烁) / 停止红（v1.2.21，调试用）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self.setVisible(False)
        self.set_color("#f9a825")  # 默认黄（待机）

    def set_color(self, color):
        self._color = color
        self.setStyleSheet(f"background: {color}; border-radius: 7px;")


# =========================================================
# 主窗口
# =========================================================
class MainWindow(QWidget):
    def __init__(self, enable_global_hotkey=True):
        super().__init__()
        self._click_count = 0
        self._button = "left"
        self._loading = True
        self._start_maximized = False
        self._hotkey_start = dict(DEFAULT_HOTKEY_START)
        self._hotkey_stop = dict(DEFAULT_HOTKEY_STOP)
        self._resizable = bool(DEFAULT_SETTINGS["resizable"])
        self._auto_select = bool(DEFAULT_SETTINGS["auto_select"])
        self._progress_enabled = bool(DEFAULT_SETTINGS["progress_bar"])
        self._progress_theme = DEFAULT_SETTINGS["progress_theme"]
        self._progress_height = int(DEFAULT_SETTINGS["progress_height"])
        self._test_enabled = bool(DEFAULT_SETTINGS["test_enabled"])  # 是否显示「调试中」单选（v1.2.21）
        self._indicator_enabled = bool(DEFAULT_SETTINGS["indicator_enabled"])  # 平时是否显示指示灯（v1.2.22）
        self._test_state = "idle"      # idle=待机(黄) / running=生效(绿闪) / stopped=停止(红)
        self._test_blink_on = False     # 指示灯闪烁相位

        # 定时点击器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._do_click)

        # 测试指示灯闪烁定时器（v1.2.21）
        self._test_blink_timer = QTimer(self)
        self._test_blink_timer.setInterval(300)
        self._test_blink_timer.timeout.connect(self._test_blink)

        # 设置自动保存（500ms 防抖单次定时器）
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(500)
        self._settings_save_timer.timeout.connect(self._save_settings_now)

        # 快捷键管理器（键盘全局热键 + 手柄按钮）
        self._hotkey_mgr = HotkeyManager(self)
        self._hotkey_mgr.triggered.connect(self._on_hotkey_triggered)
        self._hotkey_mgr.gamepad_button_pressed.connect(self._on_gamepad_button)

        self._build_ui()
        self.load_settings()
        self._loading = False
        self._apply_hotkeys(allow_keyboard=enable_global_hotkey)

    # ---------- 界面 ----------
    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} - v{__version__}")
        self.resize(320, 170)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # 第 1 行：模拟开关 + 实时快捷键显示 + 设置按钮
        row0 = QHBoxLayout()
        self.sim_check = QCheckBox("模拟开关")
        self.sim_check.setToolTip("勾选后开始模拟点击；快捷键可在「设置」中自定义")
        row0.addWidget(self.sim_check)
        row0.addStretch(1)
        self._hotkey_label = QLabel("")
        self._hotkey_label.setStyleSheet("color: #666;")
        row0.addWidget(self._hotkey_label)
        row0.addSpacing(8)
        self._btn_settings = QPushButton("设置")
        self._btn_settings.setToolTip("打开设置（快捷键等）")
        self._btn_settings.clicked.connect(self._open_settings)
        row0.addWidget(self._btn_settings)
        root.addLayout(row0)

        # 第 2 行：间隔时长（单位毫秒，点击数字框自动全选）
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("间隔时长(毫秒)"))
        self.interval_spin = ClickSelectSpinBox()
        self.interval_spin.setRange(1, 9999)
        self.interval_spin.setValue(50)
        row1.addWidget(self.interval_spin)
        row1.addStretch(1)
        root.addLayout(row1)

        # 第 3 行：鼠标按键选择
        grp = QGroupBox("鼠标按键选择")
        grp_layout = QHBoxLayout(grp)
        grp_layout.setContentsMargins(10, 6, 10, 6)
        self.left_radio = QRadioButton("左键")
        self.middle_radio = QRadioButton("中键")
        self.right_radio = QRadioButton("右键")
        self.test_radio = QRadioButton("调试中")
        self.test_radio.setToolTip("调试中：测试模拟快捷键是否生效（不真正点击，仅看指示灯，需在设置开启「平时显示指示灯」）：\n生效=闪烁绿灯 ｜ 停止=红灯 ｜ 待机=黄灯")
        self.test_radio.setVisible(False)  # 默认隐藏，设置开启后才显示（v1.2.21）
        self.left_radio.setChecked(True)
        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self.left_radio, 0)
        self._btn_group.addButton(self.middle_radio, 1)
        self._btn_group.addButton(self.right_radio, 2)
        self._btn_group.addButton(self.test_radio, 3)
        grp_layout.addWidget(self.left_radio)
        grp_layout.addWidget(self.middle_radio)
        grp_layout.addWidget(self.right_radio)
        grp_layout.addWidget(self.test_radio)
        self._test_indicator = TestIndicator()
        self._test_indicator.setToolTip("测试指示灯：生效=闪烁绿灯 ｜ 停止=红灯 ｜ 待机=黄灯")
        grp_layout.addWidget(self._test_indicator)
        grp_layout.addStretch(1)
        root.addWidget(grp)

        # 点击进度条（细条，显示模拟次数并随色系变色）+ 分隔线
        self._progress = ClickProgressBar()
        self._progress.setVisible(self._progress_enabled)
        self._progress.set_colors(COLOR_THEMES.get(self._progress_theme, COLOR_THEMES["马卡龙色系"]))
        root.addWidget(self._progress)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        status_row = QHBoxLayout()
        self._status_label = QLabel("状态：已停止")
        self._status_label.setStyleSheet("color: #999;")
        status_row.addWidget(self._status_label)
        status_row.addStretch(1)
        self._count_label = QLabel("已模拟 0 次")
        self._count_label.setStyleSheet("color: #999;")
        status_row.addWidget(self._count_label)
        root.addLayout(status_row)

        # 信号连接
        self.sim_check.toggled.connect(self._on_sim_toggled)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        self._btn_group.idToggled.connect(self._on_button_toggled)
        self._apply_test_visibility()  # 按设置同步「测试」单选与指示灯可见性（v1.2.21）

    # ---------- 快捷键（v1.2.0）----------
    def _apply_hotkeys(self, allow_keyboard=True):
        """把当前快捷键配置应用到 HotkeyManager，并刷新主界面显示"""
        self._hotkey_mgr.apply(self._hotkey_start, self._hotkey_stop, allow_keyboard=allow_keyboard)
        self._update_hotkey_display()

    def _on_hotkey_triggered(self, action):
        """快捷键触发入口（键盘全局热键 / 手柄按钮）"""
        if action == "start":
            self._start_simulate()
        elif action == "stop":
            self._stop_simulate()

    def _on_gamepad_button(self, button, action):
        """手柄按键实时反馈：状态栏显示收到的按钮号与匹配结果（v1.2.16，便于诊断）"""
        if action:
            label = {"start": "开始", "stop": "关闭"}.get(action, action)
            self._status_label.setText(f"手柄按钮 {button} → {label}")
            self._status_label.setStyleSheet("color: #1565c0;")
        else:
            self._status_label.setText(f"手柄按钮 {button}（未绑定）")
            self._status_label.setStyleSheet("color: #c62828;")
        QTimer.singleShot(2000, self._update_status)  # 2 秒后恢复运行状态

    def _update_hotkey_display(self):
        """主界面实时显示当前开始/关闭快捷键"""
        s = (self._hotkey_start or {}).get("display", "?")
        e = (self._hotkey_stop or {}).get("display", "?")
        self._hotkey_label.setText(f"开始: {s} ｜ 关闭: {e}")
        self._hotkey_label.setToolTip("可在「设置」中自定义快捷键（支持键盘/手柄按钮）")

    def _apply_progress(self):
        """应用进度条开关、色系与高度设置"""
        self._progress.setVisible(self._progress_enabled)
        self._progress.set_bar_height(self._progress_height)
        self._progress.set_colors(COLOR_THEMES.get(self._progress_theme, COLOR_THEMES["马卡龙色系"]))

    def _open_settings(self):
        dlg = SettingsDialog(self._hotkey_start, self._hotkey_stop, self._hotkey_mgr,
                             self._resizable, self._auto_select,
                             self._progress_enabled, self._progress_theme, self._progress_height,
                             self._test_enabled, self._indicator_enabled, self)
        if dlg.exec() == QDialog.Accepted:
            (self._hotkey_start, self._hotkey_stop, self._resizable, self._auto_select,
             self._progress_enabled, self._progress_theme, self._progress_height,
             self._test_enabled, self._indicator_enabled) = dlg.get_result()
            self.interval_spin.auto_select = self._auto_select
            self._apply_progress()
            self._apply_test_visibility()
            self._apply_hotkeys()
            self._apply_window_mode()
            self._save_settings_now()
            self._status_label.setText("状态：设置已更新")
            self._status_label.setStyleSheet("color: #1565c0;")

    def _apply_window_mode(self):
        """根据 resizable 设置应用窗口大小模式（固定紧凑 / 可自由调整）"""
        if self._resizable:
            self.setMaximumSize(16777215, 16777215)  # 解除固定上限
            self.setMinimumSize(300, 160)
        else:
            # 固定宽度 320；高度自适应内容（至少 170），进度条加高时窗口自动变高不遮挡上方（v1.2.27）
            lay = self.layout()
            h = lay.sizeHint().height() if lay else 170
            self.setFixedSize(320, max(170, h))

    # ---------- 逻辑 ----------
    def _on_sim_toggled(self, checked):
        """开关状态 -> 定时器启停"""
        if checked:
            self._timer.start(self.interval_spin.value())
        else:
            self._timer.stop()
        if self._light_active():
            # 指示灯可见时跟踪状态：生效/停止（调试中或平时开启指示灯，v1.2.22）
            self._test_state = "running" if checked else "stopped"
        self._update_status()
        self._update_test_light()

    def _on_interval_changed(self, value):
        if self._timer.isActive():
            self._timer.setInterval(value)
        # 闪烁频率随间隔实时变化，直观观察间隔效果（v1.2.23）
        if self._test_state == "running" and self._test_blink_timer.isActive():
            self._test_blink_timer.setInterval(max(1, value))
        self._autosave_settings()

    def _on_button_toggled(self, btn_id, checked):
        if checked:
            self._button = ["left", "middle", "right", "test"][btn_id]
            self._apply_test_visibility()
            self._autosave_settings()

    # ---------- 调试模式 + 指示灯（v1.2.21/22，调试用）----------
    def _test_mode_active(self):
        """是否处于调试模式（选中「调试中」单选）"""
        return getattr(self, "_button", "left") == "test"

    def _light_active(self):
        """指示灯是否应显示：仅由「平时显示指示灯」设置开关决定（v1.2.26）"""
        return self._indicator_enabled

    def _apply_test_visibility(self):
        """应用「显示调试单选」与「平时显示指示灯」开关：控制单选与指示灯显示（v1.2.22）"""
        self.test_radio.setVisible(self._test_enabled)
        show = self._light_active()
        self._test_indicator.setVisible(show)
        if not show:
            self._test_blink_timer.stop()
        self._update_test_light()

    def _update_test_light(self):
        """更新指示灯：待机=黄 ｜ 生效=绿(闪烁) ｜ 停止=红（灯可见时）"""
        if not self._light_active():
            return
        if self._test_state == "running":
            self._test_blink_on = True  # 首次 blink 立即切到暗绿，实现亮/暗对称交替
            self._test_indicator.set_color("#66bb6a")
            # 闪烁间隔 = 间隔时长：间隔越短闪得越快，直观观察间隔效果（v1.2.23）
            self._test_blink_timer.setInterval(max(1, self.interval_spin.value()))
            self._test_blink_timer.start()
        elif self._test_state == "stopped":
            self._test_blink_timer.stop()
            self._test_indicator.set_color("#e53935")
        else:  # idle 待机
            self._test_blink_timer.stop()
            self._test_indicator.set_color("#f9a825")

    def _test_blink(self):
        """指示灯闪烁：绿色亮/暗交替（生效时）"""
        if self._test_blink_on:
            self._test_indicator.set_color("#a5d6a7")  # 暗绿
        else:
            self._test_indicator.set_color("#66bb6a")  # 亮绿
        self._test_blink_on = not self._test_blink_on

    def _start_simulate(self):
        self.sim_check.setChecked(True)

    def _stop_simulate(self):
        self.sim_check.setChecked(False)

    def _update_status(self):
        if self._timer.isActive():
            self._status_label.setText("状态：模拟中…")
            self._status_label.setStyleSheet("color: #2e7d32;")
        else:
            self._status_label.setText("状态：已停止")
            self._status_label.setStyleSheet("color: #999;")

    def _do_click(self):
        """定时触发的模拟点击（测试模式下不真正点击，仅驱动指示灯，v1.2.21）"""
        if not self._test_mode_active():
            try:
                simulate_click(self._button)
            except Exception:
                self.sim_check.setChecked(False)
                self._status_label.setText("状态：模拟失败，已停止")
                self._status_label.setStyleSheet("color: #c62828;")
                return
        self._click_count += 1
        self._count_label.setText(f"已模拟 {self._click_count} 次")
        if self._progress_enabled:
            self._progress.set_value(self._click_count % 100)

    # ---------- 设置持久化（v1.1.0）----------
    def load_settings(self):
        """启动时读取设置并恢复：间隔 / 按键 / 窗口几何 / 最大化"""
        data = {}
        try:
            path = settings_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception:
            data = {}
        try:
            self.interval_spin.setValue(
                int(data.get("interval", DEFAULT_SETTINGS["interval"]))
            )
        except Exception:
            pass
        self._test_enabled = bool(data.get("test_enabled", DEFAULT_SETTINGS["test_enabled"]))
        self._indicator_enabled = bool(data.get("indicator_enabled", DEFAULT_SETTINGS["indicator_enabled"]))
        btn = data.get("button", "left")
        btn_id = {"left": 0, "middle": 1, "right": 2, "test": 3}.get(btn, 0)
        self._btn_group.button(btn_id).setChecked(True)
        self._button = btn if btn in ("left", "middle", "right", "test") else "left"
        self._start_maximized = bool(data.get("window_maximized", False))
        self._hotkey_start = self._sanitize_hotkey(data.get("hotkey_start"), DEFAULT_HOTKEY_START)
        self._hotkey_stop = self._sanitize_hotkey(data.get("hotkey_stop"), DEFAULT_HOTKEY_STOP)
        self._resizable = bool(data.get("resizable", DEFAULT_SETTINGS["resizable"]))
        self._auto_select = bool(data.get("auto_select", DEFAULT_SETTINGS["auto_select"]))
        self.interval_spin.auto_select = self._auto_select
        self._progress_enabled = bool(data.get("progress_bar", DEFAULT_SETTINGS["progress_bar"]))
        theme = data.get("progress_theme", DEFAULT_SETTINGS["progress_theme"])
        self._progress_theme = theme if theme in COLOR_THEMES else DEFAULT_SETTINGS["progress_theme"]
        self._progress_height = int(data.get("progress_height", DEFAULT_SETTINGS["progress_height"]))
        self._apply_progress()
        self._apply_test_visibility()  # 同步「测试」单选与指示灯可见性（v1.2.21）
        geo = data.get("window_geometry")
        if geo and self._resizable:
            try:
                self.restoreGeometry(base64.b64decode(geo))
            except Exception:
                pass
        self._apply_window_mode()

    def _autosave_settings(self):
        """控件变更 -> 启动防抖定时器，避免频繁写盘"""
        if getattr(self, "_loading", False):
            return
        self._settings_save_timer.start()

    @staticmethod
    def _sanitize_hotkey(cfg, default):
        """校验持久化的快捷键配置，非法时回退默认"""
        if not isinstance(cfg, dict):
            return dict(default)
        if cfg.get("type") == "keyboard":
            try:
                key = int(cfg["key"])
                if key <= 0:
                    return dict(default)
                if cfg.get("media"):
                    # 多媒体按键：key 即 Windows VK（v1.2.17）
                    return {
                        "type": "keyboard",
                        "key": key,
                        "mods": 0,
                        "display": str(cfg.get("display") or default.get("display", "?")),
                        "media": True,
                    }
                return {
                    "type": "keyboard",
                    "key": key,
                    "mods": int(cfg.get("mods", 0)),
                    "display": str(cfg.get("display") or default.get("display", "?")),
                    "raw_vk": bool(cfg.get("raw_vk")),
                }
            except Exception:
                return dict(default)
        if cfg.get("type") == "gamepad":
            try:
                button = int(cfg["button"])
                if button < 0:
                    return dict(default)
                return {
                    "type": "gamepad",
                    "button": button,
                    "display": str(cfg.get("display") or f"手柄按钮 {button}"),
                }
            except Exception:
                return dict(default)
        return dict(default)

    def _save_settings_now(self):
        """立即收集设置并原子写入 JSON（tmp + os.replace）"""
        data = {
            "interval": self.interval_spin.value(),
            "button": self._button,
            "window_geometry": base64.b64encode(bytes(self.saveGeometry())).decode("ascii"),
            "window_maximized": self.isMaximized(),
            "resizable": bool(self._resizable),
            "auto_select": bool(self._auto_select),
            "progress_bar": bool(self._progress_enabled),
            "progress_theme": self._progress_theme,
            "progress_height": int(self._progress_height),
            "test_enabled": bool(self._test_enabled),
            "indicator_enabled": bool(self._indicator_enabled),
            "hotkey_start": self._hotkey_start,
            "hotkey_stop": self._hotkey_stop,
        }
        path = settings_path()
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass

    def closeEvent(self, event):
        self._timer.stop()
        self._test_blink_timer.stop()
        self._settings_save_timer.stop()
        self._save_settings_now()
        self._hotkey_mgr.shutdown()
        super().closeEvent(event)


# =========================================================
# 设置对话框（多标签页设计，便于后续迭代）
# =========================================================
class SettingsDialog(QDialog):
    """设置窗口：多标签页。当前含「快捷键」页，预留「其他」页。

    快捷键配置格式：
      keyboard: {"type":"keyboard","key":Qt.Key int,"mods":Qt修饰符 int,"display":str}
      gamepad : {"type":"gamepad","button":按钮号 int,"display":str}
    """

    def __init__(self, hotkey_start, hotkey_stop, hotkey_mgr, resizable=False, auto_select=True,
                 progress_enabled=True, progress_theme="马卡龙色系", progress_height=4,
                 test_enabled=False, indicator_enabled=False, parent=None):
        super().__init__(parent)
        self._hotkey_mgr = hotkey_mgr
        self._result = (hotkey_start, hotkey_stop, bool(resizable), bool(auto_select),
                        bool(progress_enabled), progress_theme, int(progress_height),
                        bool(test_enabled), bool(indicator_enabled))
        self._capturing = None                      # 正在捕获手柄按钮的项："start"/"stop"/None
        self._gamepad_button = {"start": None, "stop": None}
        self._capture_timer = None
        self._capture_connected = False             # 手柄捕获信号是否已连接

        self.setWindowTitle(f"设置 - {APP_NAME}")
        self.setMinimumWidth(460)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_hotkey_tab(), "快捷键")
        tabs.addTab(self._build_extra_tab(), "其他")

        btnbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btnbox.button(QDialogButtonBox.Ok).setText("确定")
        btnbox.button(QDialogButtonBox.Cancel).setText("取消")
        btnbox.accepted.connect(self._on_ok)
        btnbox.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(btnbox)

        self._load_initial(hotkey_start, hotkey_stop, bool(resizable), bool(auto_select),
                           bool(progress_enabled), progress_theme, int(progress_height),
                           bool(test_enabled), bool(indicator_enabled))

    # ---------- Tab：快捷键 ----------
    def _build_hotkey_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._start_type = QComboBox()
        self._start_type.addItems(["键盘按键", "手柄按钮"])
        self._start_kse = CaptureKeySequenceEdit()  # 记录原生 VK（v1.2.20）
        self._start_media = self._make_media_combo("start")  # 多媒体按键下拉（v1.2.17）
        self._start_capture_btn = QPushButton("捕获手柄按钮…")
        self._start_capture_btn.clicked.connect(lambda: self._begin_capture("start"))
        self._start_gp_label = QLabel("未设置")
        self._start_gp_label.setStyleSheet("color: #666;")
        self._start_stack = self._make_capture_stack(self._start_kse, self._start_media, self._start_capture_btn, self._start_gp_label)
        self._start_type.currentIndexChanged.connect(lambda i: self._sync_type_visibility())
        form.addRow("开始模拟：", self._stack_row(self._start_type, self._start_stack))

        self._stop_type = QComboBox()
        self._stop_type.addItems(["键盘按键", "手柄按钮"])
        self._stop_kse = CaptureKeySequenceEdit()  # 记录原生 VK（v1.2.20）
        self._stop_media = self._make_media_combo("stop")  # 多媒体按键下拉（v1.2.17）
        self._stop_capture_btn = QPushButton("捕获手柄按钮…")
        self._stop_capture_btn.clicked.connect(lambda: self._begin_capture("stop"))
        self._stop_gp_label = QLabel("未设置")
        self._stop_gp_label.setStyleSheet("color: #666;")
        self._stop_stack = self._make_capture_stack(self._stop_kse, self._stop_media, self._stop_capture_btn, self._stop_gp_label)
        self._stop_type.currentIndexChanged.connect(lambda i: self._sync_type_visibility())
        form.addRow("关闭模拟：", self._stack_row(self._stop_type, self._stop_stack))

        tip = QLabel("提示：键盘在输入框内直接按下按键/组合键/FN+任意键（程序捕获 FN 组合实际产生的键码），\n或在下拉选多媒体键（FN+F1~F12 等）；注意 FN 键本身多数键盘不发送键码，\n故以 FN 组合后实际产生的键为准（FN+字母=该字母、FN+多媒体键=对应媒体键）。\n手柄需先连接手柄，再点「捕获手柄按钮」并按下手柄按钮。\n留空表示使用默认快捷键（- 开始、= 关闭）。")
        tip.setStyleSheet("color: #888;")
        tip.setWordWrap(True)
        form.addRow(tip)

        restore_btn = QPushButton("恢复默认快捷键")
        restore_btn.setToolTip("一键将开始/关闭快捷键恢复为默认值（- 开始、= 关闭）")
        restore_btn.clicked.connect(self._restore_default_hotkeys)
        form.addRow(restore_btn)
        return page

    def _make_capture_stack(self, kse, media_combo, capture_btn, gp_label):
        """键盘输入框+多媒体下拉 与 手柄捕获按钮（互斥显示）"""
        key_wrap = QWidget()
        klay = QHBoxLayout(key_wrap)
        klay.setContentsMargins(0, 0, 0, 0)
        klay.addWidget(kse)
        klay.addWidget(media_combo)
        gp_wrap = QWidget()
        glay = QHBoxLayout(gp_wrap)
        glay.setContentsMargins(0, 0, 0, 0)
        glay.addWidget(capture_btn)
        glay.addWidget(gp_label)
        glay.addStretch(1)
        return (key_wrap, gp_wrap)

    def _make_media_combo(self, which):
        """多媒体按键下拉（FN+F1~F12 等多功能键，v1.2.17）"""
        combo = QComboBox()
        combo.addItem("无")
        for name, vk in MEDIA_KEYS:
            combo.addItem(f"多媒体·{name}", int(vk))
        combo.setToolTip("选择 FN+功能键等多媒体按键（需键盘发送对应媒体键码，如静音/音量/播放控制）")
        combo.currentIndexChanged.connect(lambda i: self._sync_media(which))
        return combo

    def _sync_media(self, which):
        """多媒体下拉选中时禁用按键输入框（二选一，v1.2.17）"""
        media = self._start_media if which == "start" else self._stop_media
        kse = self._start_kse if which == "start" else self._stop_kse
        kse.setEnabled(media.currentData() is None)
        if media.currentData() is not None:
            kse.clear()

    def _stack_row(self, type_combo, stack):
        row = QWidget()
        rlay = QHBoxLayout(row)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(type_combo)
        key_wrap, gp_wrap = stack
        rlay.addWidget(key_wrap)
        rlay.addWidget(gp_wrap)
        return row

    def _sync_type_visibility(self):
        for type_combo, stack in ((self._start_type, self._start_stack),
                                  (self._stop_type, self._stop_stack)):
            key_wrap, gp_wrap = stack
            key_wrap.setVisible(type_combo.currentIndex() == 0)
            gp_wrap.setVisible(type_combo.currentIndex() == 1)

    def _restore_default_hotkeys(self):
        """一键恢复默认快捷键：- 开始、= 关闭（v1.2.13）"""
        self._cancel_capture()
        # 若正在捕获手柄，断开信号连接（避免残留连接）
        if self._capture_connected:
            try:
                self._hotkey_mgr.gamepad_button_captured.disconnect(self._on_captured)
            except Exception:
                pass
            self._capture_connected = False
        self._gamepad_button = {"start": None, "stop": None}
        for which, type_combo, kse, gp_label, media, default_cfg in (
            ("start", self._start_type, self._start_kse, self._start_gp_label, self._start_media, DEFAULT_HOTKEY_START),
            ("stop", self._stop_type, self._stop_kse, self._stop_gp_label, self._stop_media, DEFAULT_HOTKEY_STOP),
        ):
            type_combo.setCurrentIndex(0)  # 切回键盘
            media.setCurrentIndex(0)  # 多媒体重置为"无"
            try:
                comb = QKeyCombination(Qt.KeyboardModifier(default_cfg["mods"]), Qt.Key(default_cfg["key"]))
                kse.setKeySequence(QKeySequence(comb))
            except Exception:
                kse.clear()
            kse.setEnabled(True)
            gp_label.setText("未设置")
        self._sync_type_visibility()

    def _update_swatch(self, theme=None):
        """色系下拉变化时刷新右侧色板预览，并同步高度预览条颜色（v1.2.7/v1.2.10）"""
        theme = theme or self._theme_combo.currentText()
        colors = COLOR_THEMES.get(theme, [])
        self._theme_swatch.set_colors(colors)
        self._height_preview.set_colors(colors)

    def _update_height_preview(self, h=None):
        """高度数值变化时刷新右侧效果预览条（v1.2.10）"""
        h = self._height_spin.value() if h is None else int(h)
        self._height_preview.set_bar_height(h)

    # ---------- Tab：其他（v1.2.2 起加入设置项，v1.2.6 加进度条）----------
    def _build_extra_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self._resizable_check = QCheckBox("允许调整窗口大小")
        self._resizable_check.setToolTip("勾选后窗口可自由调整大小并记忆几何位置；取消则固定为紧凑小窗口")
        lay.addWidget(self._resizable_check)
        self._auto_select_check = QCheckBox("点击数字框自动全选")
        self._auto_select_check.setToolTip("勾选后点击间隔时长数字框会自动全选文本，方便直接输入新数值")
        lay.addWidget(self._auto_select_check)
        self._test_check = QCheckBox("显示「调试中」单选（调试用）")
        self._test_check.setToolTip("勾选后主界面鼠标按键选择处显示「调试中」选项，用于测试模拟快捷键是否生效：\n生效=闪烁绿灯 ｜ 停止=红灯 ｜ 待机=黄灯（调试中不真正点击，仅看指示灯）")
        lay.addWidget(self._test_check)
        self._indicator_check = QCheckBox("平时显示指示灯（反映模拟状态）")
        self._indicator_check.setToolTip("勾选后显示右侧指示灯（反映模拟状态），取消勾选则始终隐藏：\n模拟中=闪烁绿灯 ｜ 停止=红灯 ｜ 待机=黄灯")
        lay.addWidget(self._indicator_check)
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        lay.addWidget(line1)
        self._progress_check = QCheckBox("开启点击进度条效果")
        self._progress_check.setToolTip("勾选后在分隔线上方显示细进度条，随模拟点击次数推进并变色")
        lay.addWidget(self._progress_check)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("进度条色系："))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(COLOR_THEMES.keys()))
        self._theme_combo.setCurrentText("马卡龙色系")
        self._theme_combo.setToolTip("选择进度条渐变色系")
        self._theme_combo.currentTextChanged.connect(self._update_swatch)
        theme_row.addWidget(self._theme_combo)
        self._theme_swatch = ColorSwatchStrip()
        self._theme_swatch.setToolTip("当前色系所含颜色")
        theme_row.addWidget(self._theme_swatch, 1)  # 占剩余空间，不增加窗口宽度
        lay.addLayout(theme_row)
        height_row = QHBoxLayout()
        height_row.addWidget(QLabel("进度条高度(px)："))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(2, 20)
        self._height_spin.setValue(4)
        self._height_spin.setToolTip("设置进度条粗细（像素），右侧即时预览效果")
        height_row.addWidget(self._height_spin)
        self._height_preview = ClickProgressBar()
        self._height_preview.set_value(60)  # 固定 60% 展示高度效果
        self._height_preview.setToolTip("高度效果预览")
        height_row.addWidget(self._height_preview, 1)  # 占剩余空间
        lay.addLayout(height_row)
        self._height_spin.valueChanged.connect(self._update_height_preview)
        self._progress_check.toggled.connect(self._theme_combo.setEnabled)
        self._progress_check.toggled.connect(self._height_spin.setEnabled)
        self._progress_check.toggled.connect(self._height_preview.setVisible)
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        lay.addWidget(line2)
        label = QLabel("更多设置将在后续版本中添加。")
        label.setStyleSheet("color: #888;")
        lay.addWidget(label)
        lay.addStretch(1)
        return page

    # ---------- 手柄按钮捕获 ----------
    def _begin_capture(self, which):
        self._capturing = which
        btn = self._start_capture_btn if which == "start" else self._stop_capture_btn
        btn.setText("正在捕获…请按手柄按钮")
        # 仅在已连接时才断开，避免对未连接的信号 disconnect 触发 RuntimeWarning（v1.2.12）
        if self._capture_connected:
            try:
                self._hotkey_mgr.gamepad_button_captured.disconnect(self._on_captured)
            except Exception:
                pass
            self._capture_connected = False
        self._hotkey_mgr.gamepad_button_captured.connect(self._on_captured)
        self._capture_connected = True
        self._hotkey_mgr.capture_gamepad_button()
        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.timeout.connect(lambda: self._cancel_capture(which))
        self._capture_timer.start(15000)

    def _cancel_capture(self, which=None):
        self._capturing = None
        if self._capture_timer:
            self._capture_timer.stop()
        self._hotkey_mgr.cancel_capture()
        if which == "start":
            self._start_capture_btn.setText("捕获手柄按钮…")
        elif which == "stop":
            self._stop_capture_btn.setText("捕获手柄按钮…")

    def _on_captured(self, button):
        which = self._capturing
        self._cancel_capture(which)
        if which == "start":
            self._gamepad_button["start"] = button
            self._start_gp_label.setText(f"手柄按钮 {button}")
        elif which == "stop":
            self._gamepad_button["stop"] = button
            self._stop_gp_label.setText(f"手柄按钮 {button}")
        # 捕获完成，断开信号连接
        if self._capture_connected:
            try:
                self._hotkey_mgr.gamepad_button_captured.disconnect(self._on_captured)
            except Exception:
                pass
            self._capture_connected = False

    # ---------- 加载初始值 ----------
    def _load_initial(self, hotkey_start, hotkey_stop, resizable=False, auto_select=True,
                      progress_enabled=True, progress_theme="马卡龙色系", progress_height=4,
                      test_enabled=False, indicator_enabled=False):
        for which, cfg, type_combo, kse, gp_label, media in (
            ("start", hotkey_start, self._start_type, self._start_kse, self._start_gp_label, self._start_media),
            ("stop", hotkey_stop, self._stop_type, self._stop_kse, self._stop_gp_label, self._stop_media),
        ):
            if cfg and cfg.get("type") == "gamepad":
                type_combo.setCurrentIndex(1)
                self._gamepad_button[which] = cfg.get("button")
                gp_label.setText(cfg.get("display", f"手柄按钮 {cfg.get('button')}"))
            else:
                type_combo.setCurrentIndex(0)
                if cfg:
                    if cfg.get("media"):
                        # 多媒体按键：恢复下拉并禁用输入框（v1.2.17）
                        idx = media.findData(int(cfg.get("key", 0)))
                        media.setCurrentIndex(idx if idx >= 0 else 0)
                    else:
                        media.setCurrentIndex(0)
                        if cfg.get("raw_vk"):
                            # raw_vk 配置的 key 是原生 VK，非 Qt.Key 枚举（v1.2.20）：
                            # 标准媒体 VK 经多媒体下拉恢复；OEM 键用捕获时 display 回填 KSE（v1.2.24）
                            idx = media.findData(int(cfg.get("key", 0)))
                            if idx >= 0:
                                media.setCurrentIndex(idx)  # 下拉选中，_sync_media 会禁用输入框
                            else:
                                disp = str(cfg.get("display") or "")
                                if disp:
                                    try:
                                        seq = QKeySequence(disp)
                                        if not seq.isEmpty():
                                            kse.setKeySequence(seq)
                                    except Exception:
                                        pass
                        else:
                            try:
                                comb = QKeyCombination(Qt.KeyboardModifier(cfg.get("mods", 0)), Qt.Key(cfg["key"]))
                                kse.setKeySequence(QKeySequence(comb))
                            except Exception:
                                pass
                self._sync_media(which)
        self._resizable_check.setChecked(bool(resizable))
        self._auto_select_check.setChecked(bool(auto_select))
        self._test_check.setChecked(bool(test_enabled))
        self._indicator_check.setChecked(bool(indicator_enabled))
        self._progress_check.setChecked(bool(progress_enabled))
        theme = progress_theme if progress_theme in COLOR_THEMES else "马卡龙色系"
        self._theme_combo.setCurrentText(theme)
        self._theme_combo.setEnabled(bool(progress_enabled))
        self._height_spin.setValue(int(progress_height))
        self._height_spin.setEnabled(bool(progress_enabled))
        self._update_height_preview(int(progress_height))
        self._height_preview.setVisible(bool(progress_enabled))
        self._sync_type_visibility()
        self._update_swatch()  # 首次打开即显示当前色系色板（默认项不触发 currentTextChanged）

    # ---------- 生成配置 / 确定 ----------
    def _make_cfg(self, which):
        type_combo = self._start_type if which == "start" else self._stop_type
        if type_combo.currentIndex() == 0:  # 键盘
            media = self._start_media if which == "start" else self._stop_media
            vk = media.currentData()
            if vk:
                # 多媒体按键（v1.2.17）：key 即 Windows VK
                name = media.currentText()
                if name.startswith("多媒体·"):
                    name = name[len("多媒体·"):]
                return {"type": "keyboard", "key": int(vk), "mods": 0,
                        "display": f"多媒体·{name}", "media": True}
            kse = self._start_kse if which == "start" else self._stop_kse
            seq = kse.keySequence()
            if seq.isEmpty():
                return None
            comb = seq[0]
            if int(comb.key()) <= 0:
                return None
            _mods = comb.keyboardModifiers()
            _nvk = getattr(kse, "_native_vk", 0)
            if _nvk:
                # KSE 捕获时的原生 Windows VK（媒体/OEM 键更准确，v1.2.20 根治）
                return {"type": "keyboard", "key": int(_nvk),
                        "mods": int(getattr(_mods, "value", _mods)),
                        "display": seq.toString(), "raw_vk": True}
            return {
                "type": "keyboard",
                "key": int(comb.key()),
                "mods": int(getattr(_mods, "value", _mods)),
                "display": seq.toString(),
            }
        # 手柄
        button = self._gamepad_button.get(which)
        if button is None:
            return None
        return {"type": "gamepad", "button": button, "display": f"手柄按钮 {button}"}

    def _on_ok(self):
        start = self._make_cfg("start")
        stop = self._make_cfg("stop")
        # 留空的快捷键回退为默认（v1.2.11：允许留空，按默认键处理）
        if start is None:
            start = dict(DEFAULT_HOTKEY_START)
        if stop is None:
            stop = dict(DEFAULT_HOTKEY_STOP)
        if start == stop:
            QMessageBox.warning(self, "提示", "开始与关闭快捷键不能相同")
            return
        self._result = (start, stop, self._resizable_check.isChecked(), self._auto_select_check.isChecked(),
                        self._progress_check.isChecked(), self._theme_combo.currentText(),
                        self._height_spin.value(), self._test_check.isChecked(),
                        self._indicator_check.isChecked())
        self.accept()

    def get_result(self):
        return self._result


# =========================================================
# 入口
# =========================================================
def _app_icon():
    """加载程序图标 icon.ico（开发/打包均从程序目录取，找不到返回空图标）"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "icon.ico")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(_app_icon())
    window = MainWindow()
    if window._start_maximized:
        window.showMaximized()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
