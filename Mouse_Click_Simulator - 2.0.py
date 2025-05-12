import sys
import time
import threading
import json
import random
import platform
import psutil
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QSpinBox, QPushButton, QGroupBox,
                            QLineEdit, QCheckBox, QTabWidget, QTextEdit, QFileDialog,
                            QSystemTrayIcon, QMenu, QAction, QMessageBox, QScrollArea,
                            QDoubleSpinBox, QTimeEdit, QColorDialog, QProgressBar)
from PyQt5.QtCore import Qt, QSettings, QTimer, QTime, QSize, QByteArray, QPoint
from PyQt5.QtGui import QIcon, QColor, QPixmap, QImage
import pyautogui
import keyboard
import cv2
from pynput.mouse import Controller as MouseController
from pynput.keyboard import GlobalHotKeys, Key, Listener as KeyboardListener
from screeninfo import get_monitors
from PIL import ImageGrab, Image
import requests
import socket
import pickle
import zlib
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import hashlib
import logging
from logging.handlers import RotatingFileHandler

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('mouse_simulator.log', maxBytes=1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)

class MouseClickSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级鼠标点击模拟器")
        self.setGeometry(100, 100, 900, 700)
        
        # 初始化设置
        self.settings = QSettings("AdvancedMouseClickSimulator", "Config")
        self.load_settings()
        
        # 初始化变量
        self.clicking = False
        self.click_thread = None
        self.click_count = 0
        self.emergency_stop = False
        self.mouse_positions = []
        self.record_macro = False
        self.macro_actions = []
        self.color_trigger_active = False
        self.image_trigger_active = False
        self.timer_trigger_active = False
        self.remote_control_active = False
        self.remote_server = None
        self.remote_thread = None
        self.script_engine = None
        self.tray_icon = None
        
        # 初始化UI
        self.init_ui()
        self.setup_hotkeys()
        self.setup_tray_icon()
        
        # 启动监控定时器
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.monitor_timer.start(1000)
        
        # 鼠标位置定时器
        self.mouse_pos_timer = QTimer(self)
        self.mouse_pos_timer.timeout.connect(self.update_mouse_position)
        self.mouse_pos_timer.start(100)
        
        # 初始化鼠标控制器
        self.mouse_controller = MouseController()
        
        # 初始化键盘监听器
        self.keyboard_listener = KeyboardListener(on_press=self.on_key_press)
        self.keyboard_listener.start()
        
        # 检查开机自启动
        self.check_autostart()
    
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 基本设置标签页
        self.basic_tab = QWidget()
        self.init_basic_tab()
        self.tabs.addTab(self.basic_tab, "基本设置")
        
        # 高级设置标签页
        self.advanced_tab = QWidget()
        self.init_advanced_tab()
        self.tabs.addTab(self.advanced_tab, "高级设置")
        
        # 触发器标签页
        self.trigger_tab = QWidget()
        self.init_trigger_tab()
        self.tabs.addTab(self.trigger_tab, "触发器")
        
        # 脚本标签页
        self.script_tab = QWidget()
        self.init_script_tab()
        self.tabs.addTab(self.script_tab, "脚本")
        
        # 远程控制标签页
        self.remote_tab = QWidget()
        self.init_remote_tab()
        self.tabs.addTab(self.remote_tab, "远程控制")
        
        # 状态监控标签页
        self.monitor_tab = QWidget()
        self.init_monitor_tab()
        self.tabs.addTab(self.monitor_tab, "状态监控")
        
        # 添加到主布局
        main_layout.addWidget(self.tabs)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("开始模拟")
        self.stop_button = QPushButton("停止模拟")
        self.stop_button.setEnabled(False)
        self.emergency_button = QPushButton("紧急停止 (ESC)")
        self.emergency_button.setStyleSheet("background-color: red; color: white;")
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.emergency_button)
        
        # 状态栏
        self.status_bar = QLabel("状态: 未运行 | 点击次数: 0 | CPU: 0% | 内存: 0MB")
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
        
        # 添加到主布局
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.status_bar)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 连接信号槽
        self.start_button.clicked.connect(self.start_clicking)
        self.stop_button.clicked.connect(self.stop_clicking)
        self.emergency_button.clicked.connect(self.emergency_stop_func)
    
    def init_basic_tab(self):
        layout = QVBoxLayout()
        
        # 鼠标按键设置
        button_group = QGroupBox("鼠标按键设置")
        button_layout = QVBoxLayout()
        
        self.button_combo = QComboBox()
        self.button_combo.addItems(["左键", "中键", "右键"])
        self.button_combo.setCurrentIndex(self.settings.value("basic/button_index", 0, type=int))
        
        self.click_mode_combo = QComboBox()
        self.click_mode_combo.addItems(["单次点击", "双击", "三连击", "长按"])
        self.click_mode_combo.setCurrentIndex(self.settings.value("basic/click_mode", 0, type=int))
        self.click_mode_combo.currentIndexChanged.connect(self.update_click_mode)
        
        self.hold_time_spin = QSpinBox()
        self.hold_time_spin.setRange(1, 10000)
        self.hold_time_spin.setValue(self.settings.value("basic/hold_time", 100, type=int))
        self.hold_time_spin.setSuffix("ms")
        self.hold_time_spin.setEnabled(False)
        
        button_layout.addWidget(QLabel("选择鼠标按键:"))
        button_layout.addWidget(self.button_combo)
        button_layout.addWidget(QLabel("点击模式:"))
        button_layout.addWidget(self.click_mode_combo)
        button_layout.addWidget(QLabel("长按时间:"))
        button_layout.addWidget(self.hold_time_spin)
        button_group.setLayout(button_layout)
        
        # 点击间隔设置
        interval_group = QGroupBox("点击间隔设置")
        interval_layout = QVBoxLayout()
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1000000)
        self.interval_spin.setValue(self.settings.value("basic/interval", 100, type=int))
        self.interval_spin.setSuffix("ms")
        
        self.random_interval_check = QCheckBox("随机间隔")
        self.random_interval_check.setChecked(self.settings.value("basic/random_interval", False, type=bool))
        self.random_interval_check.stateChanged.connect(self.update_interval_mode)
        
        self.min_interval_spin = QSpinBox()
        self.min_interval_spin.setRange(1, 1000000)
        self.min_interval_spin.setValue(self.settings.value("basic/min_interval", 50, type=int))
        self.min_interval_spin.setSuffix("ms")
        self.min_interval_spin.setEnabled(self.random_interval_check.isChecked())
        
        self.max_interval_spin = QSpinBox()
        self.max_interval_spin.setRange(1, 1000000)
        self.max_interval_spin.setValue(self.settings.value("basic/max_interval", 200, type=int))
        self.max_interval_spin.setSuffix("ms")
        self.max_interval_spin.setEnabled(self.random_interval_check.isChecked())
        
        self.click_limit_check = QCheckBox("点击次数限制")
        self.click_limit_check.setChecked(self.settings.value("basic/click_limit", False, type=bool))
        
        self.click_limit_spin = QSpinBox()
        self.click_limit_spin.setRange(1, 1000000)
        self.click_limit_spin.setValue(self.settings.value("basic/click_limit_value", 100, type=int))
        self.click_limit_spin.setEnabled(self.click_limit_check.isChecked())
        
        interval_layout.addWidget(QLabel("点击间隔:"))
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addWidget(self.random_interval_check)
        interval_layout.addWidget(QLabel("最小间隔:"))
        interval_layout.addWidget(self.min_interval_spin)
        interval_layout.addWidget(QLabel("最大间隔:"))
        interval_layout.addWidget(self.max_interval_spin)
        interval_layout.addWidget(self.click_limit_check)
        interval_layout.addWidget(self.click_limit_spin)
        interval_group.setLayout(interval_layout)
        
        # 坐标设置
        position_group = QGroupBox("坐标设置")
        position_layout = QVBoxLayout()
        
        self.position_mode_combo = QComboBox()
        self.position_mode_combo.addItems(["当前鼠标位置", "固定坐标位置", "多坐标循环"])
        self.position_mode_combo.setCurrentIndex(self.settings.value("basic/position_mode", 0, type=int))
        self.position_mode_combo.currentIndexChanged.connect(self.update_position_mode)
        
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 9999)
        self.x_spin.setValue(self.settings.value("basic/x_position", 0, type=int))
        self.x_spin.setEnabled(False)
        
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 9999)
        self.y_spin.setValue(self.settings.value("basic/y_position", 0, type=int))
        self.y_spin.setEnabled(False)
        
        self.position_list = QTextEdit()
        self.position_list.setPlainText(self.settings.value("basic/position_list", ""))
        self.position_list.setEnabled(False)
        
        self.add_position_btn = QPushButton("添加当前位置")
        self.add_position_btn.setEnabled(False)
        self.add_position_btn.clicked.connect(self.add_current_position)
        
        self.clear_positions_btn = QPushButton("清空列表")
        self.clear_positions_btn.setEnabled(False)
        self.clear_positions_btn.clicked.connect(self.clear_positions)
        
        position_layout.addWidget(QLabel("坐标模式:"))
        position_layout.addWidget(self.position_mode_combo)
        position_layout.addWidget(QLabel("X坐标:"))
        position_layout.addWidget(self.x_spin)
        position_layout.addWidget(QLabel("Y坐标:"))
        position_layout.addWidget(self.y_spin)
        position_layout.addWidget(QLabel("坐标列表 (每行一个坐标,格式:x,y):"))
        position_layout.addWidget(self.position_list)
        position_layout.addWidget(self.add_position_btn)
        position_layout.addWidget(self.clear_positions_btn)
        position_group.setLayout(position_layout)
        
        # 添加到标签页
        layout.addWidget(button_group)
        layout.addWidget(interval_group)
        layout.addWidget(position_group)
        self.basic_tab.setLayout(layout)
    
    def init_advanced_tab(self):
        layout = QVBoxLayout()
        
        # 游戏辅助设置
        game_group = QGroupBox("游戏辅助设置")
        game_layout = QVBoxLayout()
        
        self.combo_key_check = QCheckBox("组合键模拟")
        self.combo_key_check.setChecked(self.settings.value("advanced/combo_key", False, type=bool))
        
        self.combo_key_combo = QComboBox()
        self.combo_key_combo.addItems(["左键+右键", "左键+中键", "右键+中键"])
        self.combo_key_combo.setCurrentIndex(self.settings.value("advanced/combo_key_type", 0, type=int))
        self.combo_key_combo.setEnabled(self.combo_key_check.isChecked())
        
        self.recoil_check = QCheckBox("压枪模式")
        self.recoil_check.setChecked(self.settings.value("advanced/recoil_mode", False, type=bool))
        
        self.recoil_pattern_edit = QTextEdit()
        self.recoil_pattern_edit.setPlainText(self.settings.value("advanced/recoil_pattern", "0,0\n0,1\n0,2\n0,1\n0,0"))
        self.recoil_pattern_edit.setEnabled(self.recoil_check.isChecked())
        
        self.anti_detect_check = QCheckBox("防检测机制")
        self.anti_detect_check.setChecked(self.settings.value("advanced/anti_detect", False, type=bool))
        
        self.random_offset_spin = QSpinBox()
        self.random_offset_spin.setRange(0, 100)
        self.random_offset_spin.setValue(self.settings.value("advanced/random_offset", 5, type=int))
        self.random_offset_spin.setSuffix("px")
        self.random_offset_spin.setEnabled(self.anti_detect_check.isChecked())
        
        game_layout.addWidget(self.combo_key_check)
        game_layout.addWidget(self.combo_key_combo)
        game_layout.addWidget(self.recoil_check)
        game_layout.addWidget(QLabel("压枪模式 (每行一个移动偏移量,格式:x,y):"))
        game_layout.addWidget(self.recoil_pattern_edit)
        game_layout.addWidget(self.anti_detect_check)
        game_layout.addWidget(QLabel("随机偏移量:"))
        game_layout.addWidget(self.random_offset_spin)
        game_group.setLayout(game_layout)
        
        # 自动化测试设置
        test_group = QGroupBox("自动化测试设置")
        test_layout = QVBoxLayout()
        
        self.test_loop_spin = QSpinBox()
        self.test_loop_spin.setRange(1, 100000)
        self.test_loop_spin.setValue(self.settings.value("advanced/test_loop", 1, type=int))
        self.test_loop_spin.setSuffix("次")
        
        self.verify_check = QCheckBox("结果验证")
        self.verify_check.setChecked(self.settings.value("advanced/verify_result", False, type=bool))
        
        self.verify_area_edit = QTextEdit()
        self.verify_area_edit.setPlainText(self.settings.value("advanced/verify_area", "0,0,100,100"))
        self.verify_area_edit.setEnabled(self.verify_check.isChecked())
        
        self.report_check = QCheckBox("生成测试报告")
        self.report_check.setChecked(self.settings.value("advanced/generate_report", True, type=bool))
        
        test_layout.addWidget(QLabel("循环测试次数:"))
        test_layout.addWidget(self.test_loop_spin)
        test_layout.addWidget(self.verify_check)
        test_layout.addWidget(QLabel("验证区域 (x1,y1,x2,y2):"))
        test_layout.addWidget(self.verify_area_edit)
        test_layout.addWidget(self.report_check)
        test_group.setLayout(test_layout)
        
        # 添加到标签页
        layout.addWidget(game_group)
        layout.addWidget(test_group)
        self.advanced_tab.setLayout(layout)
    
    def init_trigger_tab(self):
        layout = QVBoxLayout()
        
        # 颜色触发器
        color_group = QGroupBox("颜色触发器")
        color_layout = QVBoxLayout()
        
        self.color_trigger_check = QCheckBox("启用颜色触发")
        self.color_trigger_check.setChecked(self.settings.value("trigger/color_trigger", False, type=bool))
        self.color_trigger_check.stateChanged.connect(self.update_trigger_status)
        
        self.color_x_spin = QSpinBox()
        self.color_x_spin.setRange(0, 9999)
        self.color_x_spin.setValue(self.settings.value("trigger/color_x", 0, type=int))
        
        self.color_y_spin = QSpinBox()
        self.color_y_spin.setRange(0, 9999)
        self.color_y_spin.setValue(self.settings.value("trigger/color_y", 0, type=int))
        
        self.target_color_btn = QPushButton("选择目标颜色")
        self.target_color_btn.clicked.connect(self.select_target_color)
        self.target_color = QColor(self.settings.value("trigger/target_color", "#FF0000"))
        
        self.color_tolerance_spin = QSpinBox()
        self.color_tolerance_spin.setRange(0, 255)
        self.color_tolerance_spin.setValue(self.settings.value("trigger/color_tolerance", 10, type=int))
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(50, 50)
        self.update_color_preview()
        
        color_layout.addWidget(self.color_trigger_check)
        color_layout.addWidget(QLabel("检测位置 X:"))
        color_layout.addWidget(self.color_x_spin)
        color_layout.addWidget(QLabel("检测位置 Y:"))
        color_layout.addWidget(self.color_y_spin)
        color_layout.addWidget(self.target_color_btn)
        color_layout.addWidget(QLabel("颜色容差:"))
        color_layout.addWidget(self.color_tolerance_spin)
        color_layout.addWidget(QLabel("目标颜色:"))
        color_layout.addWidget(self.color_preview)
        color_group.setLayout(color_layout)
        
        # 图像触发器
        image_group = QGroupBox("图像触发器")
        image_layout = QVBoxLayout()
        
        self.image_trigger_check = QCheckBox("启用图像触发")
        self.image_trigger_check.setChecked(self.settings.value("trigger/image_trigger", False, type=bool))
        self.image_trigger_check.stateChanged.connect(self.update_trigger_status)
        
        self.image_path_edit = QLineEdit(self.settings.value("trigger/image_path", ""))
        self.browse_image_btn = QPushButton("浏览...")
        self.browse_image_btn.clicked.connect(self.browse_image)
        
        self.capture_area_btn = QPushButton("捕捉屏幕区域")
        self.capture_area_btn.clicked.connect(self.capture_screen_area)
        
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setValue(self.settings.value("trigger/confidence", 0.9, type=float))
        self.confidence_spin.setSingleStep(0.05)
        
        self.image_preview = QLabel()
        self.image_preview.setFixedSize(100, 100)
        self.update_image_preview()
        
        image_layout.addWidget(self.image_trigger_check)
        image_layout.addWidget(QLabel("目标图像路径:"))
        image_layout.addWidget(self.image_path_edit)
        image_layout.addWidget(self.browse_image_btn)
        image_layout.addWidget(self.capture_area_btn)
        image_layout.addWidget(QLabel("匹配置信度:"))
        image_layout.addWidget(self.confidence_spin)
        image_layout.addWidget(QLabel("目标图像预览:"))
        image_layout.addWidget(self.image_preview)
        image_group.setLayout(image_layout)
        
        # 定时触发器
        timer_group = QGroupBox("定时触发器")
        timer_layout = QVBoxLayout()
        
        self.timer_trigger_check = QCheckBox("启用定时触发")
        self.timer_trigger_check.setChecked(self.settings.value("trigger/timer_trigger", False, type=bool))
        self.timer_trigger_check.stateChanged.connect(self.update_trigger_status)
        
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.start_time_edit.setTime(QTime.fromString(self.settings.value("trigger/start_time", "00:00:00"), "HH:mm:ss"))
        
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit.setTime(QTime.fromString(self.settings.value("trigger/end_time", "23:59:59"), "HH:mm:ss"))
        
        timer_layout.addWidget(self.timer_trigger_check)
        timer_layout.addWidget(QLabel("开始时间:"))
        timer_layout.addWidget(self.start_time_edit)
        timer_layout.addWidget(QLabel("结束时间:"))
        timer_layout.addWidget(self.end_time_edit)
        timer_group.setLayout(timer_layout)
        
        # 添加到标签页
        layout.addWidget(color_group)
        layout.addWidget(image_group)
        layout.addWidget(timer_group)
        self.trigger_tab.setLayout(layout)
    
    def init_script_tab(self):
        layout = QVBoxLayout()
        
        # 宏录制
        macro_group = QGroupBox("宏录制")
        macro_layout = QVBoxLayout()
        
        self.record_macro_btn = QPushButton("开始录制宏")
        self.record_macro_btn.clicked.connect(self.toggle_record_macro)
        
        self.stop_record_btn = QPushButton("停止录制")
        self.stop_record_btn.setEnabled(False)
        self.stop_record_btn.clicked.connect(self.stop_record_macro)
        
        self.play_macro_btn = QPushButton("播放宏")
        self.play_macro_btn.clicked.connect(self.play_macro)
        
        self.save_macro_btn = QPushButton("保存宏")
        self.save_macro_btn.clicked.connect(self.save_macro)
        
        self.load_macro_btn = QPushButton("加载宏")
        self.load_macro_btn.clicked.connect(self.load_macro)
        
        self.macro_info = QTextEdit()
        self.macro_info.setReadOnly(True)
        
        macro_layout.addWidget(self.record_macro_btn)
        macro_layout.addWidget(self.stop_record_btn)
        macro_layout.addWidget(self.play_macro_btn)
        macro_layout.addWidget(self.save_macro_btn)
        macro_layout.addWidget(self.load_macro_btn)
        macro_layout.addWidget(QLabel("宏信息:"))
        macro_layout.addWidget(self.macro_info)
        macro_group.setLayout(macro_layout)
        
        # 脚本编辑
        script_group = QGroupBox("脚本编辑")
        script_layout = QVBoxLayout()
        
        self.script_edit = QTextEdit()
        self.script_edit.setPlainText(self.settings.value("script/code", "# 在这里编写自定义脚本\n# 可以使用以下变量:\n# - mouse: 鼠标控制器\n# - keyboard: 键盘控制器\n# - pyautogui: pyautogui模块\n# - time: 时间模块\n\n# 示例: 移动鼠标并点击\n# mouse.move(100, 100)\n# mouse.click('left')\n"))
        
        self.run_script_btn = QPushButton("运行脚本")
        self.run_script_btn.clicked.connect(self.run_script)
        
        script_layout.addWidget(self.script_edit)
        script_layout.addWidget(self.run_script_btn)
        script_group.setLayout(script_layout)
        
        # 添加到标签页
        layout.addWidget(macro_group)
        layout.addWidget(script_group)
        self.script_tab.setLayout(layout)
    
    def init_remote_tab(self):
        layout = QVBoxLayout()
        
        # 远程控制设置
        remote_group = QGroupBox("远程控制设置")
        remote_layout = QVBoxLayout()
        
        self.remote_enable_check = QCheckBox("启用远程控制")
        self.remote_enable_check.setChecked(self.settings.value("remote/enabled", False, type=bool))
        self.remote_enable_check.stateChanged.connect(self.toggle_remote_control)
        
        self.remote_port_spin = QSpinBox()
        self.remote_port_spin.setRange(1024, 65535)
        self.remote_port_spin.setValue(self.settings.value("remote/port", 12345, type=int))
        
        self.remote_password_edit = QLineEdit()
        self.remote_password_edit.setPlaceholderText("设置远程控制密码")
        self.remote_password_edit.setText(self.settings.value("remote/password", ""))
        
        self.remote_status_label = QLabel("状态: 未运行")
        
        remote_layout.addWidget(self.remote_enable_check)
        remote_layout.addWidget(QLabel("端口号:"))
        remote_layout.addWidget(self.remote_port_spin)
        remote_layout.addWidget(QLabel("密码:"))
        remote_layout.addWidget(self.remote_password_edit)
        remote_layout.addWidget(self.remote_status_label)
        remote_group.setLayout(remote_layout)
        
        # 远程脚本库
        script_lib_group = QGroupBox("远程脚本库")
        script_lib_layout = QVBoxLayout()
        
        self.script_list = QComboBox()
        self.script_list.addItems(["加载脚本...", "基本点击脚本", "游戏辅助脚本", "自动化测试脚本"])
        
        self.download_script_btn = QPushButton("下载脚本")
        self.download_script_btn.clicked.connect(self.download_script)
        
        self.upload_script_btn = QPushButton("上传脚本")
        self.upload_script_btn.clicked.connect(self.upload_script)
        
        script_lib_layout.addWidget(self.script_list)
        script_lib_layout.addWidget(self.download_script_btn)
        script_lib_layout.addWidget(self.upload_script_btn)
        script_lib_group.setLayout(script_lib_layout)
        
        # 添加到标签页
        layout.addWidget(remote_group)
        layout.addWidget(script_lib_group)
        self.remote_tab.setLayout(layout)
    
    def init_monitor_tab(self):
        layout = QVBoxLayout()
        
        # 状态监控
        monitor_group = QGroupBox("状态监控")
        monitor_layout = QVBoxLayout()
        
        self.click_count_label = QLabel("点击次数: 0")
        self.mouse_position_label = QLabel("鼠标位置: (0, 0)")
        self.cpu_usage_label = QLabel("CPU使用率: 0%")
        self.memory_usage_label = QLabel("内存使用: 0MB")
        
        self.cpu_usage_bar = QProgressBar()
        self.cpu_usage_bar.setRange(0, 100)
        
        self.memory_usage_bar = QProgressBar()
        self.memory_usage_bar.setRange(0, 100)
        
        monitor_layout.addWidget(self.click_count_label)
        monitor_layout.addWidget(self.mouse_position_label)
        monitor_layout.addWidget(self.cpu_usage_label)
        monitor_layout.addWidget(self.cpu_usage_bar)
        monitor_layout.addWidget(self.memory_usage_label)
        monitor_layout.addWidget(self.memory_usage_bar)
        monitor_group.setLayout(monitor_layout)
        
        # 日志查看
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        
        # 添加到标签页
        layout.addWidget(monitor_group)
        layout.addWidget(log_group)
        self.monitor_tab.setLayout(layout)
    
    def update_click_mode(self, index):
        self.hold_time_spin.setEnabled(index == 3)  # 长按模式
    
    def update_interval_mode(self, state):
        enabled = state == Qt.Checked
        self.min_interval_spin.setEnabled(enabled)
        self.max_interval_spin.setEnabled(enabled)
    
    def update_position_mode(self, index):
        self.x_spin.setEnabled(index == 1)
        self.y_spin.setEnabled(index == 1)
        self.position_list.setEnabled(index == 2)
        self.add_position_btn.setEnabled(index == 2)
        self.clear_positions_btn.setEnabled(index == 2)
    
    def update_trigger_status(self):
        self.color_trigger_active = self.color_trigger_check.isChecked()
        self.image_trigger_active = self.image_trigger_check.isChecked()
        self.timer_trigger_active = self.timer_trigger_check.isChecked()
    
    def update_color_preview(self):
        pixmap = QPixmap(50, 50)
        pixmap.fill(self.target_color)
        self.color_preview.setPixmap(pixmap)
    
    def update_image_preview(self):
        image_path = self.image_path_edit.text()
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio)
                self.image_preview.setPixmap(pixmap)
                return
        self.image_preview.clear()
    
    def select_target_color(self):
        color = QColorDialog.getColor(self.target_color, self, "选择目标颜色")
        if color.isValid():
            self.target_color = color
            self.settings.setValue("trigger/target_color", color.name())
            self.update_color_preview()
    
    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择目标图像", "", "Images (*.png *.jpg *.bmp)")
        if file_path:
            self.image_path_edit.setText(file_path)
            self.settings.setValue("trigger/image_path", file_path)
            self.update_image_preview()
    
    def capture_screen_area(self):
        self.hide()
        time.sleep(0.5)  # 给窗口隐藏时间
        
        # 使用PIL捕获屏幕
        screen = ImageGrab.grab()
        screen.save("screenshot.png")
        
        self.show()
        
        # 让用户选择区域
        from PIL import Image
        img = Image.open("screenshot.png")
        img.show()
        
        # 这里应该有一个更专业的方法让用户选择区域
        # 暂时使用简单的输入框
        x, y, w, h = QInputDialog.getInt(self, "捕捉区域", "左上角 X:", 0), \
                      QInputDialog.getInt(self, "捕捉区域", "左上角 Y:", 0), \
                      QInputDialog.getInt(self, "捕捉区域", "宽度:", 100), \
                      QInputDialog.getInt(self, "捕捉区域", "高度:", 100)
        
        # 裁剪并保存图像
        area = (x, y, x+w, y+h)
        cropped = img.crop(area)
        save_path, _ = QFileDialog.getSaveFileName(self, "保存捕捉的区域", "", "PNG Image (*.png)")
        if save_path:
            cropped.save(save_path)
            self.image_path_edit.setText(save_path)
            self.settings.setValue("trigger/image_path", save_path)
            self.update_image_preview()
    
    def add_current_position(self):
        x, y = pyautogui.position()
        current_text = self.position_list.toPlainText()
        if current_text:
            current_text += "\n"
        current_text += f"{x},{y}"
        self.position_list.setPlainText(current_text)
    
    def clear_positions(self):
        self.position_list.clear()
    
    def toggle_record_macro(self):
        if not self.record_macro:
            self.record_macro = True
            self.macro_actions = []
            self.record_macro_btn.setEnabled(False)
            self.stop_record_btn.setEnabled(True)
            self.macro_info.setPlainText("开始录制宏...\n移动鼠标并点击进行录制")
            
            # 启动鼠标监听线程
            self.macro_listener = MouseController()
            self.macro_listener_thread = threading.Thread(target=self.record_macro_actions)
            self.macro_listener_thread.start()
        else:
            self.stop_record_macro()
    
    def record_macro_actions(self):
        last_pos = None
        last_time = time.time()
        
        while self.record_macro:
            current_pos = self.mouse_controller.position
            current_time = time.time()
            
            # 记录移动
            if last_pos is None or current_pos != last_pos:
                self.macro_actions.append({
                    'type': 'move',
                    'x': current_pos[0],
                    'y': current_pos[1],
                    'time': current_time - last_time if last_time else 0
                })
                last_pos = current_pos
                last_time = current_time
            
            # 记录点击 (通过监听鼠标事件)
            # 这里简化处理，实际应该监听鼠标点击事件
            time.sleep(0.01)
    
    def stop_record_macro(self):
        self.record_macro = False
        self.record_macro_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        
        if hasattr(self, 'macro_listener_thread'):
            self.macro_listener_thread.join(timeout=1)
        
        self.macro_info.setPlainText(f"宏录制完成!\n共录制了 {len(self.macro_actions)} 个动作")
    
    def play_macro(self):
        if not self.macro_actions:
            QMessageBox.warning(self, "警告", "没有可播放的宏!")
            return
        
        def play():
            for action in self.macro_actions:
                if not self.clicking:
                    break
                
                if action['type'] == 'move':
                    pyautogui.moveTo(action['x'], action['y'])
                elif action['type'] == 'click':
                    pyautogui.click(button=action['button'])
                
                time.sleep(action.get('time', 0.1))
        
        threading.Thread(target=play, daemon=True).start()
    
    def save_macro(self):
        if not self.macro_actions:
            QMessageBox.warning(self, "警告", "没有可保存的宏!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "保存宏", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.macro_actions, f)
                QMessageBox.information(self, "成功", "宏已成功保存!")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存宏时出错:\n{str(e)}")
    
    def load_macro(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "加载宏", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    self.macro_actions = json.load(f)
                self.macro_info.setPlainText(f"成功加载宏!\n共 {len(self.macro_actions)} 个动作")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载宏时出错:\n{str(e)}")
    
    def run_script(self):
        script = self.script_edit.toPlainText()
        if not script.strip():
            QMessageBox.warning(self, "警告", "脚本内容为空!")
            return
        
        try:
            # 创建执行环境
            env = {
                'mouse': self.mouse_controller,
                'keyboard': keyboard,
                'pyautogui': pyautogui,
                'time': time,
                'random': random,
                'math': __import__('math'),
                'datetime': __import__('datetime')
            }
            
            # 执行脚本
            exec(script, env)
            QMessageBox.information(self, "成功", "脚本执行完成!")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行脚本时出错:\n{str(e)}")
    
    def toggle_remote_control(self, state):
        if state == Qt.Checked:
            self.start_remote_control()
        else:
            self.stop_remote_control()
    
    def start_remote_control(self):
        port = self.remote_port_spin.value()
        password = self.remote_password_edit.text()
        
        if not password:
            QMessageBox.warning(self, "警告", "请设置远程控制密码!")
            self.remote_enable_check.setChecked(False)
            return
        
        try:
            self.remote_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.remote_server.bind(('0.0.0.0', port))
            self.remote_server.listen(1)
            
            self.remote_thread = threading.Thread(target=self.handle_remote_connections, daemon=True)
            self.remote_thread.start()
            
            self.remote_status_label.setText(f"状态: 监听中 (端口: {port})")
            self.remote_control_active = True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动远程控制服务失败:\n{str(e)}")
            self.remote_enable_check.setChecked(False)
    
    def stop_remote_control(self):
        self.remote_control_active = False
        if self.remote_server:
            try:
                self.remote_server.close()
            except:
                pass
            self.remote_server = None
        
        self.remote_status_label.setText("状态: 已停止")
    
    def handle_remote_connections(self):
        while self.remote_control_active:
            try:
                conn, addr = self.remote_server.accept()
                logging.info(f"远程连接来自: {addr}")
                
                # 验证密码
                password = self.remote_password_edit.text()
                conn.sendall(b"AUTH_REQUIRED")
                received_password = conn.recv(1024).decode().strip()
                
                if received_password != password:
                    conn.sendall(b"AUTH_FAILED")
                    conn.close()
                    continue
                
                conn.sendall(b"AUTH_SUCCESS")
                
                # 处理命令
                while self.remote_control_active:
                    try:
                        data = conn.recv(1024)
                        if not data:
                            break
                        
                        command = data.decode().strip()
                        logging.info(f"收到远程命令: {command}")
                        
                        # 执行命令
                        if command == "START":
                            self.start_clicking()
                            conn.sendall(b"STARTED")
                        elif command == "STOP":
                            self.stop_clicking()
                            conn.sendall(b"STOPPED")
                        elif command.startswith("CLICK"):
                            _, button, x, y = command.split()
                            pyautogui.click(int(x), int(y), button=button.lower())
                            conn.sendall(b"CLICKED")
                        else:
                            conn.sendall(b"UNKNOWN_COMMAND")
                    except Exception as e:
                        logging.error(f"处理远程命令时出错: {str(e)}")
                        break
                
                conn.close()
            except Exception as e:
                logging.error(f"处理远程连接时出错: {str(e)}")
                if self.remote_control_active:
                    time.sleep(1)
    
    def download_script(self):
        script_name = self.script_list.currentText()
        if script_name == "加载脚本...":
            QMessageBox.warning(self, "警告", "请选择一个脚本!")
            return
        
        try:
            # 这里应该是从服务器下载脚本的逻辑
            # 简化处理，直接使用内置脚本
            scripts = {
                "基本点击脚本": "# 基本点击脚本\nimport time\n\nfor i in range(10):\n    pyautogui.click()\n    time.sleep(0.5)",
                "游戏辅助脚本": "# 游戏辅助脚本\nimport time\nimport random\n\nfor i in range(100):\n    pyautogui.click()\n    time.sleep(0.1 + random.random() * 0.1)",
                "自动化测试脚本": "# 自动化测试脚本\nimport time\n\nfor i in range(5):\n    pyautogui.click(button='left')\n    time.sleep(1)\n    pyautogui.click(button='right')\n    time.sleep(1)"
            }
            
            script = scripts.get(script_name, "# 空脚本")
            self.script_edit.setPlainText(script)
            QMessageBox.information(self, "成功", f"已下载脚本: {script_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载脚本时出错:\n{str(e)}")
    
    def upload_script(self):
        script_name, ok = QInputDialog.getText(self, "上传脚本", "输入脚本名称:")
        if not ok or not script_name:
            return
        
        script_content = self.script_edit.toPlainText()
        if not script_content.strip():
            QMessageBox.warning(self, "警告", "脚本内容为空!")
            return
        
        try:
            # 这里应该是上传脚本到服务器的逻辑
            # 简化处理，只是显示消息
            QMessageBox.information(self, "成功", f"脚本 '{script_name}' 已上传!")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"上传脚本时出错:\n{str(e)}")
    
    def update_monitor(self):
        # 更新CPU使用率
        cpu_percent = psutil.cpu_percent()
        self.cpu_usage_label.setText(f"CPU使用率: {cpu_percent}%")
        self.cpu_usage_bar.setValue(int(cpu_percent))
        
        # 更新内存使用
        memory = psutil.virtual_memory()
        memory_used = memory.used / (1024 * 1024)
        memory_percent = memory.percent
        self.memory_usage_label.setText(f"内存使用: {memory_used:.1f}MB ({memory_percent}%)")
        self.memory_usage_bar.setValue(int(memory_percent))
        
        # 更新点击次数
        self.click_count_label.setText(f"点击次数: {self.click_count}")
        
        # 更新状态栏
        status_text = f"状态: {'运行中' if self.clicking else '未运行'} | 点击次数: {self.click_count} | CPU: {cpu_percent}% | 内存: {memory_used:.1f}MB"
        self.status_bar.setText(status_text)
    
    def update_mouse_position(self):
        x, y = pyautogui.position()
        self.mouse_position_label.setText(f"鼠标位置: ({x}, {y})")
    
    def setup_hotkeys(self):
        try:
            keyboard.remove_hotkey(self.start_hotkey)
        except:
            pass
        try:
            keyboard.remove_hotkey(self.stop_hotkey)
        except:
            pass
        
        self.start_hotkey = self.settings.value("hotkeys/start", "-")
        self.stop_hotkey = self.settings.value("hotkeys/stop", "=")
        
        if self.start_hotkey:
            keyboard.add_hotkey(self.start_hotkey, self.start_clicking)
        if self.stop_hotkey:
            keyboard.add_hotkey(self.stop_hotkey, self.stop_clicking)
    
    def setup_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # 需要一个图标文件
        
        tray_menu = QMenu()
        
        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        start_action = QAction("开始模拟", self)
        start_action.triggered.connect(self.start_clicking)
        tray_menu.addAction(start_action)
        
        stop_action = QAction("停止模拟", self)
        stop_action.triggered.connect(self.stop_clicking)
        tray_menu.addAction(stop_action)
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.tray_icon_activated)
    
    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
    
    def check_autostart(self):
        autostart = self.settings.value("system/autostart", False, type=bool)
        if autostart:
            # 这里应该实现添加/删除开机启动项的逻辑
            # 不同操作系统实现方式不同
            pass
    
    def save_settings(self):
        # 基本设置
        self.settings.setValue("basic/button_index", self.button_combo.currentIndex())
        self.settings.setValue("basic/click_mode", self.click_mode_combo.currentIndex())
        self.settings.setValue("basic/hold_time", self.hold_time_spin.value())
        self.settings.setValue("basic/interval", self.interval_spin.value())
        self.settings.setValue("basic/random_interval", self.random_interval_check.isChecked())
        self.settings.setValue("basic/min_interval", self.min_interval_spin.value())
        self.settings.setValue("basic/max_interval", self.max_interval_spin.value())
        self.settings.setValue("basic/click_limit", self.click_limit_check.isChecked())
        self.settings.setValue("basic/click_limit_value", self.click_limit_spin.value())
        self.settings.setValue("basic/position_mode", self.position_mode_combo.currentIndex())
        self.settings.setValue("basic/x_position", self.x_spin.value())
        self.settings.setValue("basic/y_position", self.y_spin.value())
        self.settings.setValue("basic/position_list", self.position_list.toPlainText())
        
        # 高级设置
        self.settings.setValue("advanced/combo_key", self.combo_key_check.isChecked())
        self.settings.setValue("advanced/combo_key_type", self.combo_key_combo.currentIndex())
        self.settings.setValue("advanced/recoil_mode", self.recoil_check.isChecked())
        self.settings.setValue("advanced/recoil_pattern", self.recoil_pattern_edit.toPlainText())
        self.settings.setValue("advanced/anti_detect", self.anti_detect_check.isChecked())
        self.settings.setValue("advanced/random_offset", self.random_offset_spin.value())
        self.settings.setValue("advanced/test_loop", self.test_loop_spin.value())
        self.settings.setValue("advanced/verify_result", self.verify_check.isChecked())
        self.settings.setValue("advanced/verify_area", self.verify_area_edit.toPlainText())
        self.settings.setValue("advanced/generate_report", self.report_check.isChecked())
        
        # 触发器设置
        self.settings.setValue("trigger/color_trigger", self.color_trigger_check.isChecked())
        self.settings.setValue("trigger/color_x", self.color_x_spin.value())
        self.settings.setValue("trigger/color_y", self.color_y_spin.value())
        self.settings.setValue("trigger/color_tolerance", self.color_tolerance_spin.value())
        self.settings.setValue("trigger/image_trigger", self.image_trigger_check.isChecked())
        self.settings.setValue("trigger/image_path", self.image_path_edit.text())
        self.settings.setValue("trigger/confidence", self.confidence_spin.value())
        self.settings.setValue("trigger/timer_trigger", self.timer_trigger_check.isChecked())
        self.settings.setValue("trigger/start_time", self.start_time_edit.time().toString("HH:mm:ss"))
        self.settings.setValue("trigger/end_time", self.end_time_edit.time().toString("HH:mm:ss"))
        
        # 远程控制设置
        self.settings.setValue("remote/enabled", self.remote_enable_check.isChecked())
        self.settings.setValue("remote/port", self.remote_port_spin.value())
        self.settings.setValue("remote/password", self.remote_password_edit.text())
        
        # 快捷键设置
        self.settings.setValue("hotkeys/start", self.start_hotkey)
        self.settings.setValue("hotkeys/stop", self.stop_hotkey)
        
        # 系统设置
        self.settings.setValue("system/autostart", False)  # 需要根据实际设置
        
        # 脚本设置
        self.settings.setValue("script/code", self.script_edit.toPlainText())
    
    def load_settings(self):
        # 基本设置
        self.button_index = self.settings.value("basic/button_index", 0, type=int)
        self.click_mode = self.settings.value("basic/click_mode", 0, type=int)
        self.hold_time = self.settings.value("basic/hold_time", 100, type=int)
        self.interval = self.settings.value("basic/interval", 100, type=int)
        self.random_interval = self.settings.value("basic/random_interval", False, type=bool)
        self.min_interval = self.settings.value("basic/min_interval", 50, type=int)
        self.max_interval = self.settings.value("basic/max_interval", 200, type=int)
        self.click_limit = self.settings.value("basic/click_limit", False, type=bool)
        self.click_limit_value = self.settings.value("basic/click_limit_value", 100, type=int)
        self.position_mode = self.settings.value("basic/position_mode", 0, type=int)
        self.x_position = self.settings.value("basic/x_position", 0, type=int)
        self.y_position = self.settings.value("basic/y_position", 0, type=int)
        self.position_list_text = self.settings.value("basic/position_list", "")
        
        # 高级设置
        self.combo_key = self.settings.value("advanced/combo_key", False, type=bool)
        self.combo_key_type = self.settings.value("advanced/combo_key_type", 0, type=int)
        self.recoil_mode = self.settings.value("advanced/recoil_mode", False, type=bool)
        self.recoil_pattern = self.settings.value("advanced/recoil_pattern", "0,0\n0,1\n0,2\n0,1\n0,0")
        self.anti_detect = self.settings.value("advanced/anti_detect", False, type=bool)
        self.random_offset = self.settings.value("advanced/random_offset", 5, type=int)
        self.test_loop = self.settings.value("advanced/test_loop", 1, type=int)
        self.verify_result = self.settings.value("advanced/verify_result", False, type=bool)
        self.verify_area = self.settings.value("advanced/verify_area", "0,0,100,100")
        self.generate_report = self.settings.value("advanced/generate_report", True, type=bool)
        
        # 触发器设置
        self.color_trigger = self.settings.value("trigger/color_trigger", False, type=bool)
        self.color_x = self.settings.value("trigger/color_x", 0, type=int)
        self.color_y = self.settings.value("trigger/color_y", 0, type=int)
        self.color_tolerance = self.settings.value("trigger/color_tolerance", 10, type=int)
        self.image_trigger = self.settings.value("trigger/image_trigger", False, type=bool)
        self.image_path = self.settings.value("trigger/image_path", "")
        self.confidence = self.settings.value("trigger/confidence", 0.9, type=float)
        self.timer_trigger = self.settings.value("trigger/timer_trigger", False, type=bool)
        self.start_time = self.settings.value("trigger/start_time", "00:00:00")
        self.end_time = self.settings.value("trigger/end_time", "23:59:59")
        
        # 远程控制设置
        self.remote_enabled = self.settings.value("remote/enabled", False, type=bool)
        self.remote_port = self.settings.value("remote/port", 12345, type=int)
        self.remote_password = self.settings.value("remote/password", "")
        
        # 快捷键设置
        self.start_hotkey = self.settings.value("hotkeys/start", "-")
        self.stop_hotkey = self.settings.value("hotkeys/stop", "=")
        
        # 系统设置
        self.autostart = self.settings.value("system/autostart", False, type=bool)
        
        # 脚本设置
        self.script_code = self.settings.value("script/code", "# 在这里编写自定义脚本\n# 可以使用以下变量:\n# - mouse: 鼠标控制器\n# - keyboard: 键盘控制器\n# - pyautogui: pyautogui模块\n# - time: 时间模块\n\n# 示例: 移动鼠标并点击\n# mouse.move(100, 100)\n# mouse.click('left')\n")
    
    def start_clicking(self):
        if self.clicking:
            return
            
        self.clicking = True
        self.emergency_stop = False
        self.click_count = 0
        self.status_bar.setText("状态: 运行中")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 保存设置
        self.save_settings()
        # 重新设置快捷键
        self.setup_hotkeys()
        
        # 获取当前设置
        button = self.button_combo.currentText()
        click_mode = self.click_mode_combo.currentIndex()
        hold_time = self.hold_time_spin.value() / 1000.0  # 转换为秒
        
        interval = self.interval_spin.value() / 1000.0
        random_interval = self.random_interval_check.isChecked()
        min_interval = self.min_interval_spin.value() / 1000.0
        max_interval = self.max_interval_spin.value() / 1000.0
        
        click_limit = self.click_limit_check.isChecked()
        click_limit_value = self.click_limit_spin.value()
        
        position_mode = self.position_mode_combo.currentIndex()
        fixed_x = self.x_spin.value()
        fixed_y = self.y_spin.value()
        
        positions = []
        if position_mode == 2:  # 多坐标循环
            pos_text = self.position_list.toPlainText()
            for line in pos_text.split('\n'):
                if ',' in line:
                    x, y = map(int, line.strip().split(','))
                    positions.append((x, y))
            if not positions:
                QMessageBox.warning(self, "警告", "坐标列表为空，将使用当前位置!")
                positions = [pyautogui.position()]
        
        # 游戏辅助设置
        combo_key = self.combo_key_check.isChecked()
        combo_key_type = self.combo_key_combo.currentIndex()
        
        recoil_mode = self.recoil_check.isChecked()
        recoil_pattern = []
        if recoil_mode:
            for line in self.recoil_pattern_edit.toPlainText().split('\n'):
                if ',' in line:
                    x, y = map(int, line.strip().split(','))
                    recoil_pattern.append((x, y))
        
        anti_detect = self.anti_detect_check.isChecked()
        random_offset = self.random_offset_spin.value()
        
        # 自动化测试设置
        test_loop = self.test_loop_spin.value()
        verify_result = self.verify_check.isChecked()
        verify_area = list(map(int, self.verify_area_edit.toPlainText().split(','))) if verify_result else None
        generate_report = self.report_check.isChecked()
        
        # 启动点击线程
        self.click_thread = threading.Thread(
            target=self.click_loop,
            args=(
                button, click_mode, hold_time,
                interval, random_interval, min_interval, max_interval,
                click_limit, click_limit_value,
                position_mode, fixed_x, fixed_y, positions,
                combo_key, combo_key_type,
                recoil_mode, recoil_pattern,
                anti_detect, random_offset,
                test_loop, verify_result, verify_area, generate_report
            ),
            daemon=True
        )
        self.click_thread.start()
    
    def stop_clicking(self):
        self.clicking = False
        self.status_bar.setText("状态: 已停止")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join(timeout=1)
    
    def emergency_stop_func(self):
        self.emergency_stop = True
        self.stop_clicking()
        QMessageBox.information(self, "紧急停止", "模拟已紧急停止!")
    
    def click_loop(
        self,
        button, click_mode, hold_time,
        interval, random_interval, min_interval, max_interval,
        click_limit, click_limit_value,
        position_mode, fixed_x, fixed_y, positions,
        combo_key, combo_key_type,
        recoil_mode, recoil_pattern,
        anti_detect, random_offset,
        test_loop, verify_result, verify_area, generate_report
    ):
        button_map = {
            "左键": "left",
            "中键": "middle",
            "右键": "right"
        }
        button = button_map.get(button, "left")
        
        combo_buttons = []
        if combo_key:
            if combo_key_type == 0:
                combo_buttons = ["left", "right"]
            elif combo_key_type == 1:
                combo_buttons = ["left", "middle"]
            elif combo_key_type == 2:
                combo_buttons = ["right", "middle"]
        
        current_position_index = 0
        current_recoil_index = 0
        test_iteration = 0
        
        while self.clicking and not self.emergency_stop:
            # 检查触发器
            if not self.check_triggers():
                time.sleep(0.1)
                continue
            
            # 检查点击限制
            if click_limit and self.click_count >= click_limit_value:
                self.stop_clicking()
                break
            
            # 获取目标位置
            if position_mode == 0:  # 当前鼠标位置
                x, y = pyautogui.position()
            elif position_mode == 1:  # 固定坐标
                x, y = fixed_x, fixed_y
            else:  # 多坐标循环
                if not positions:
                    break
                x, y = positions[current_position_index]
                current_position_index = (current_position_index + 1) % len(positions)
            
            # 应用随机偏移
            if anti_detect:
                x += random.randint(-random_offset, random_offset)
                y += random.randint(-random_offset, random_offset)
            
            # 移动鼠标
            pyautogui.moveTo(x, y)
            
            # 执行点击
            if click_mode == 0:  # 单次点击
                if combo_key:
                    for btn in combo_buttons:
                        pyautogui.mouseDown(button=btn)
                    time.sleep(0.05)
                    for btn in reversed(combo_buttons):
                        pyautogui.mouseUp(button=btn)
                else:
                    pyautogui.click(button=button)
            elif click_mode == 1:  # 双击
                pyautogui.doubleClick(button=button)
            elif click_mode == 2:  # 三连击
                pyautogui.click(button=button, clicks=3)
            elif click_mode == 3:  # 长按
                pyautogui.mouseDown(button=button)
                time.sleep(hold_time)
                pyautogui.mouseUp(button=button)
            
            # 应用压枪模式
            if recoil_mode and recoil_pattern:
                dx, dy = recoil_pattern[current_recoil_index]
                pyautogui.moveRel(dx, dy)
                current_recoil_index = (current_recoil_index + 1) % len(recoil_pattern)
            
            self.click_count += 1
            
            # 检查自动化测试验证
            if verify_result and verify_area and len(verify_area) == 4:
                # 这里应该实现验证逻辑
                pass
            
            # 计算间隔时间
            if random_interval:
                current_interval = random.uniform(min_interval, max_interval)
            else:
                current_interval = interval
            
            # 等待间隔时间
            start_time = time.time()
            while time.time() - start_time < current_interval:
                if not self.clicking or self.emergency_stop:
                    break
                time.sleep(0.01)
            
            # 检查测试循环
            test_iteration += 1
            if test_iteration >= test_loop:
                break
        
        # 生成测试报告
        if generate_report and test_loop > 1:
            self.generate_test_report(test_loop)
    
    def check_triggers(self):
        if not (self.color_trigger_active or self.image_trigger_active or self.timer_trigger_active):
            return True
        
        current_time = QTime.currentTime()
        
        # 检查定时触发器
        if self.timer_trigger_active:
            start_time = self.start_time_edit.time()
            end_time = self.end_time_edit.time()
            
            if not (start_time <= current_time <= end_time):
                return False
        
        # 检查颜色触发器
        if self.color_trigger_active:
            x = self.color_x_spin.value()
            y = self.color_y_spin.value()
            tolerance = self.color_tolerance_spin.value()
            
            # 获取屏幕颜色
            screenshot = ImageGrab.grab()
            pixel_color = screenshot.getpixel((x, y))
            
            # 转换为QColor
            screen_color = QColor(*pixel_color)
            target_color = self.target_color
            
            # 计算颜色差异
            diff = abs(screen_color.red() - target_color.red()) + \
                   abs(screen_color.green() - target_color.green()) + \
                   abs(screen_color.blue() - target_color.blue())
            
            if diff > tolerance:
                return False
        
        # 检查图像触发器
        if self.image_trigger_active:
            image_path = self.image_path_edit.text()
            confidence = self.confidence_spin.value()
            
            if not os.path.exists(image_path):
                return False
            
            try:
                location = pyautogui.locateOnScreen(image_path, confidence=confidence)
                if not location:
                    return False
            except:
                return False
        
        return True
    
    def generate_test_report(self, test_loop):
        report = f"""测试报告 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        
测试循环次数: {test_loop}
实际点击次数: {self.click_count}
成功率: {100.0 * self.click_count / test_loop if test_loop > 0 else 0:.2f}%
        
设置参数:
- 鼠标按键: {self.button_combo.currentText()}
- 点击模式: {self.click_mode_combo.currentText()}
- 点击间隔: {self.interval_spin.value()}ms
- 坐标模式: {self.position_mode_combo.currentText()}
        
备注: 测试完成
"""
        
        # 保存报告到文件
        report_path = os.path.join(os.getcwd(), f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(report_path, 'w') as f:
                f.write(report)
            logging.info(f"测试报告已保存到: {report_path}")
        except Exception as e:
            logging.error(f"保存测试报告时出错: {str(e)}")
    
    def on_key_press(self, key):
        try:
            if key == Key.esc and self.clicking:
                # 检测ESC键是否被按住3秒
                start_time = time.time()
                while time.time() - start_time < 3:
                    time.sleep(0.1)
                    if not keyboard.is_pressed('esc'):
                        return
                
                self.emergency_stop_func()
        except AttributeError:
            pass
    
    def closeEvent(self, event):
        self.stop_clicking()
        self.stop_remote_control()
        self.save_settings()
        
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()
        
        if self.tray_icon:
            self.tray_icon.hide()
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 创建并显示主窗口
    window = MouseClickSimulator()
    window.show()
    
    sys.exit(app.exec_())