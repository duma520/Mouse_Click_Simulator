import sys
import time
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QSpinBox, QPushButton, QGroupBox,
                             QLineEdit, QCheckBox)
from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QKeySequence
import pyautogui
import keyboard


class MouseClickSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("鼠标点击模拟器")
        self.setGeometry(100, 100, 400, 300)
        
        self.settings = QSettings("MouseClickSimulator", "Config")
        self.load_settings()
        
        self.init_ui()
        self.setup_hotkeys()
        
        self.clicking = False
        self.click_thread = None
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 鼠标按键设置
        button_group = QGroupBox("鼠标按键设置")
        button_layout = QHBoxLayout()
        
        self.button_label = QLabel("选择鼠标按键:")
        self.button_combo = QComboBox()
        self.button_combo.addItems(["左键", "中键", "右键"])
        self.button_combo.setCurrentIndex(self.settings.value("button_index", 0, type=int))
        
        button_layout.addWidget(self.button_label)
        button_layout.addWidget(self.button_combo)
        button_group.setLayout(button_layout)
        
        # 点击间隔设置
        interval_group = QGroupBox("点击间隔设置")
        interval_layout = QHBoxLayout()
        
        self.interval_label = QLabel("点击间隔(ms):")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1000000)
        self.interval_spin.setValue(self.settings.value("interval", 100, type=int))
        
        interval_layout.addWidget(self.interval_label)
        interval_layout.addWidget(self.interval_spin)
        interval_group.setLayout(interval_layout)
        
        # 快捷键设置
        hotkey_group = QGroupBox("快捷键设置")
        hotkey_layout = QVBoxLayout()
        
        # 开启快捷键
        start_hotkey_layout = QHBoxLayout()
        self.start_hotkey_label = QLabel("开启快捷键:")
        self.start_hotkey_edit = QLineEdit()
        self.start_hotkey_edit.setText(self.settings.value("start_hotkey", "-"))
        self.start_hotkey_clear = QPushButton("清除")
        
        start_hotkey_layout.addWidget(self.start_hotkey_label)
        start_hotkey_layout.addWidget(self.start_hotkey_edit)
        start_hotkey_layout.addWidget(self.start_hotkey_clear)
        
        # 关闭快捷键
        stop_hotkey_layout = QHBoxLayout()
        self.stop_hotkey_label = QLabel("关闭快捷键:")
        self.stop_hotkey_edit = QLineEdit()
        self.stop_hotkey_edit.setText(self.settings.value("stop_hotkey", "="))
        self.stop_hotkey_clear = QPushButton("清除")
        
        stop_hotkey_layout.addWidget(self.stop_hotkey_label)
        stop_hotkey_layout.addWidget(self.stop_hotkey_edit)
        stop_hotkey_layout.addWidget(self.stop_hotkey_clear)
        
        hotkey_layout.addLayout(start_hotkey_layout)
        hotkey_layout.addLayout(stop_hotkey_layout)
        hotkey_group.setLayout(hotkey_layout)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("开始模拟")
        self.stop_button = QPushButton("停止模拟")
        self.stop_button.setEnabled(False)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        
        # 状态显示
        self.status_label = QLabel("状态: 未运行")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        # 添加到主布局
        main_layout.addWidget(button_group)
        main_layout.addWidget(interval_group)
        main_layout.addWidget(hotkey_group)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.status_label)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 连接信号槽
        self.start_button.clicked.connect(self.start_clicking)
        self.stop_button.clicked.connect(self.stop_clicking)
        self.start_hotkey_clear.clicked.connect(lambda: self.start_hotkey_edit.clear())
        self.stop_hotkey_clear.clicked.connect(lambda: self.stop_hotkey_edit.clear())
        
    def setup_hotkeys(self):
        try:
            keyboard.remove_hotkey(self.start_hotkey)
        except:
            pass
        try:
            keyboard.remove_hotkey(self.stop_hotkey)
        except:
            pass
            
        self.start_hotkey = self.settings.value("start_hotkey", "-")
        self.stop_hotkey = self.settings.value("stop_hotkey", "=")
        
        if self.start_hotkey:
            keyboard.add_hotkey(self.start_hotkey, self.start_clicking)
        if self.stop_hotkey:
            keyboard.add_hotkey(self.stop_hotkey, self.stop_clicking)
    
    def save_settings(self):
        self.settings.setValue("button_index", self.button_combo.currentIndex())
        self.settings.setValue("interval", self.interval_spin.value())
        self.settings.setValue("start_hotkey", self.start_hotkey_edit.text())
        self.settings.setValue("stop_hotkey", self.stop_hotkey_edit.text())
        
    def load_settings(self):
        self.button_index = self.settings.value("button_index", 0, type=int)
        self.interval = self.settings.value("interval", 100, type=int)
        self.start_hotkey = self.settings.value("start_hotkey", "-")
        self.stop_hotkey = self.settings.value("stop_hotkey", "=")
    
    def start_clicking(self):
        if self.clicking:
            return
            
        self.clicking = True
        self.status_label.setText("状态: 运行中")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 保存设置
        self.save_settings()
        # 重新设置快捷键
        self.setup_hotkeys()
        
        # 获取当前设置
        button = self.button_combo.currentText()
        interval = self.interval_spin.value() / 1000.0  # 转换为秒
        
        # 启动点击线程
        self.click_thread = threading.Thread(target=self.click_loop, args=(button, interval), daemon=True)
        self.click_thread.start()
    
    def stop_clicking(self):
        self.clicking = False
        self.status_label.setText("状态: 已停止")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join(timeout=1)
    
    def click_loop(self, button, interval):
        button_map = {
            "左键": "left",
            "中键": "middle",
            "右键": "right"
        }
        button = button_map.get(button, "left")
        
        while self.clicking:
            pyautogui.click(button=button)
            time.sleep(interval)
    
    def closeEvent(self, event):
        self.stop_clicking()
        self.save_settings()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MouseClickSimulator()
    window.show()
    sys.exit(app.exec_())