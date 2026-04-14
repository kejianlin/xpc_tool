# -*- coding: utf-8 -*-
"""
XCP tool - 主界面
功能：串口配置、解锁验证、EEPROM读写、参数写入
"""

import sys
import html
import ctypes
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QComboBox, QPushButton, QLineEdit, QTextEdit,
    QMessageBox, QStatusBar, QGridLayout, QSplitter, QListView
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter

from xcp_protocol import XCPProtocol


class XCPToolWindow(QMainWindow):
    """XCP工具主窗口"""
    
    BAUDRATES = ['1200', '2400', '4800', '9600', '19200', '57600']
    DEFAULT_BAUDRATE = '9600'
    LOGO_CANDIDATES = [
        Path(__file__).resolve().parent / "logo.png",
        Path(__file__).resolve().parent / "Logo.png",
        Path.cwd() / "logo.png",
        Path.cwd() / "Logo.png",
    ]
    
    def __init__(self):
        super().__init__()
        self.xcp = XCPProtocol()
        self.init_ui()
        self.refresh_ports()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("XCP tool")
        window_icon = self._load_logo_icon()
        if not window_icon.isNull():
            self.setWindowIcon(window_icon)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(self._get_stylesheet())
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        
        left_layout.addWidget(self._create_serial_group())
        left_layout.addWidget(self._create_unlock_group())
        left_layout.addWidget(self._create_eeprom_group())
        left_layout.addWidget(self._create_parameter_group())
        left_layout.addWidget(self._create_control_group())
        left_layout.addStretch()
        
        right_panel = self._create_log_group()
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([260, 640])
        
        main_layout.addWidget(splitter)
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status("就绪 - 请选择串口并连接")

    def _load_logo_icon(self) -> QIcon:
        """
        加载多尺寸图标，避免标题栏和任务栏显示模糊。
        """
        for logo_path in self.LOGO_CANDIDATES:
            if logo_path.exists():
                return self._build_square_icon(str(logo_path))
        return QIcon()

    @staticmethod
    def _build_square_icon(image_path: str) -> QIcon:
        """
        将任意比例图片按等比例缩放并居中到正方形画布，避免图标被拉伸。
        """
        source = QPixmap(image_path)
        if source.isNull():
            return QIcon()

        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 128, 256):
            canvas = QPixmap(size, size)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            scaled = source.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.end()
            icon.addPixmap(canvas)
        return icon
        
    def _get_stylesheet(self) -> str:
        """获取样式表 - 明亮工业制造业风格"""
        return """
            QMainWindow {
                background-color: #eef3f8;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #b8c7d9;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #f8fbff;
                color: #26415f;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px;
                color: #1777ff;
                background-color: #eef3f8;
            }
            QPushButton {
                background-color: #1777ff;
                color: white;
                border: 1px solid #0d5fd6;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #3388ff;
                border: 1px solid #1777ff;
            }
            QPushButton:pressed {
                background-color: #0d5fd6;
            }
            QPushButton:disabled {
                background-color: #d8e2ee;
                color: #8ea0b5;
                border: 1px solid #c4d0de;
            }
            QPushButton#exitBtn {
                background-color: #f25f5c;
                border: 1px solid #da4b48;
            }
            QPushButton#exitBtn:hover {
                background-color: #ff7471;
                border: 1px solid #f25f5c;
            }
            QPushButton#unlockBtn {
                background-color: #19a974;
                border: 1px solid #12855b;
            }
            QPushButton#unlockBtn:hover {
                background-color: #24bf87;
                border: 1px solid #19a974;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #b8c7d9;
                border-radius: 3px;
                background-color: white;
                color: #1f334a;
                selection-background-color: #1777ff;
                selection-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #1777ff;
                background-color: #fafdff;
            }
            QComboBox {
                padding: 5px;
                padding-right: 24px;
                border: 1px solid #b8c7d9;
                border-radius: 3px;
                background-color: white;
                color: #1f334a;
            }
            QComboBox:hover {
                border: 1px solid #1777ff;
                background-color: #fafdff;
            }
            QComboBox::drop-down {
                border-left: 1px solid #d5dfeb;
                width: 20px;
                background-color: #f3f7fc;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #1777ff;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #1f334a;
                selection-background-color: #1777ff;
                selection-color: white;
                border: 1px solid #b8c7d9;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 5px;
                min-height: 20px;
                background-color: white;
                color: #1f334a;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e8f1ff;
                color: #1777ff;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #1777ff;
                color: white;
            }
            QTextEdit {
                border: 1px solid #b8c7d9;
                border-radius: 3px;
                background-color: #f5f9ff;
                color: #1f334a;
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
            }
            QLabel {
                color: #526b88;
            }
            QStatusBar {
                background-color: #e9f1fb;
                color: #1777ff;
                border-top: 1px solid #c9d8e8;
            }
            QSplitter::handle {
                background-color: #d7e2ee;
            }
            QSplitter::handle:hover {
                background-color: #1777ff;
            }
        """
    
    def _create_serial_group(self) -> QGroupBox:
        """创建串口配置组"""
        group = QGroupBox("串口配置")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        
        layout.addWidget(QLabel("COM口:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setView(QListView())
        self.port_combo.setMinimumWidth(120)
        layout.addWidget(self.port_combo, 0, 1)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(self.refresh_btn, 0, 2)
        
        layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.setView(QListView())
        self.baudrate_combo.addItems(self.BAUDRATES)
        self.baudrate_combo.setCurrentText(self.DEFAULT_BAUDRATE)
        layout.addWidget(self.baudrate_combo, 1, 1)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn, 1, 2)
        
        info_label = QLabel("数据位:8  停止位:1  校验:无")
        info_label.setStyleSheet("color: #6f86a0; font-size: 10px;")
        layout.addWidget(info_label, 2, 0, 1, 3)
        
        return group
    
    def _create_unlock_group(self) -> QGroupBox:
        """创建解锁验证组"""
        group = QGroupBox("解锁验证")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)
        
        self.unlock_btn = QPushButton("解锁")
        self.unlock_btn.setObjectName("unlockBtn")
        self.unlock_btn.clicked.connect(self.send_unlock)
        self.unlock_btn.setEnabled(False)
        layout.addWidget(self.unlock_btn)
        
        self.verify_btn = QPushButton("验证解锁状态")
        self.verify_btn.clicked.connect(self.verify_unlock)
        self.verify_btn.setEnabled(False)
        layout.addWidget(self.verify_btn)
        
        self.unlock_status_label = QLabel("状态: 未解锁")
        self.unlock_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        layout.addWidget(self.unlock_status_label)
        
        layout.addStretch()
        
        return group
    
    def _create_eeprom_group(self) -> QGroupBox:
        """创建EEPROM读写组"""
        group = QGroupBox("EEPROM 读/写")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        
        layout.addWidget(QLabel("地址:"), 0, 0)
        self.addr_input = QLineEdit()
        self.addr_input.setPlaceholderText("如: 9101")
        layout.addWidget(self.addr_input, 0, 1)
        
        layout.addWidget(QLabel("参数:"), 0, 2)
        self.param_input = QLineEdit()
        self.param_input.setPlaceholderText("如: 42240")
        layout.addWidget(self.param_input, 0, 3)
        
        btn_layout = QHBoxLayout()
        
        self.read_eep_btn = QPushButton("读 EEP")
        self.read_eep_btn.clicked.connect(self.read_eeprom)
        self.read_eep_btn.setEnabled(False)
        btn_layout.addWidget(self.read_eep_btn)
        
        self.write_eep_btn = QPushButton("写 EEP")
        self.write_eep_btn.clicked.connect(self.write_eeprom)
        self.write_eep_btn.setEnabled(False)
        btn_layout.addWidget(self.write_eep_btn)
        
        self.factory_reset_btn = QPushButton("恢复出厂")
        self.factory_reset_btn.clicked.connect(self.factory_reset)
        self.factory_reset_btn.setEnabled(False)
        self.factory_reset_btn.setStyleSheet(
            "QPushButton { background-color: #ffb347; border: 1px solid #f0a126; color: #ffffff; }"
            "QPushButton:hover { background-color: #ffc165; border: 1px solid #1777ff; }"
            "QPushButton:disabled { background-color: #d8e2ee; color: #8ea0b5; border: 1px solid #c4d0de; }"
        )
        btn_layout.addWidget(self.factory_reset_btn)
        
        self.reset_mcu_btn = QPushButton("复位MCU")
        self.reset_mcu_btn.clicked.connect(self.reset_mcu)
        self.reset_mcu_btn.setEnabled(False)
        self.reset_mcu_btn.setStyleSheet(
            "QPushButton { background-color: #6c8ef5; border: 1px solid #5479eb; color: #ffffff; }"
            "QPushButton:hover { background-color: #84a1ff; border: 1px solid #1777ff; }"
            "QPushButton:disabled { background-color: #d8e2ee; color: #8ea0b5; border: 1px solid #c4d0de; }"
        )
        btn_layout.addWidget(self.reset_mcu_btn)
        
        layout.addLayout(btn_layout, 1, 0, 1, 4)
        
        return group
    
    def _create_parameter_group(self) -> QGroupBox:
        """创建参数写入组"""
        group = QGroupBox("参数写入")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        
        layout.addWidget(QLabel("P/N:"), 0, 0)
        self.pn_input = QLineEdit()
        self.pn_input.setPlaceholderText("CTO码")
        layout.addWidget(self.pn_input, 0, 1)
        
        layout.addWidget(QLabel("S/N:"), 0, 2)
        self.sn_input = QLineEdit()
        self.sn_input.setPlaceholderText("14位序列号")
        self.sn_input.setMaxLength(14)
        layout.addWidget(self.sn_input, 0, 3)
        
        layout.addWidget(QLabel("KVA:"), 1, 0)
        self.kva_input = QLineEdit()
        self.kva_input.setPlaceholderText("功率")
        layout.addWidget(self.kva_input, 1, 1)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.write_conf)
        self.send_btn.setEnabled(False)
        layout.addWidget(self.send_btn, 1, 2, 1, 2)
        
        return group
    
    def _create_control_group(self) -> QGroupBox:
        """创建控制按钮组"""
        group = QGroupBox("控制")
        layout = QHBoxLayout(group)
        
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        layout.addWidget(self.clear_log_btn)
        
        layout.addStretch()
        
        self.exit_btn = QPushButton("退出")
        self.exit_btn.setObjectName("exitBtn")
        self.exit_btn.clicked.connect(self.exit_app)
        layout.addWidget(self.exit_btn)
        
        return group
    
    def _create_log_group(self) -> QGroupBox:
        """创建日志显示组"""
        group = QGroupBox("日志区")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumWidth(350)
        layout.addWidget(self.log_text)
        
        return group
    
    def log(self, message: str, level: str = "INFO"):
        """添加日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        color_map = {
            "INFO": "#1777ff",
            "WARN": "#ff9800",
            "ERROR": "#e14d4d",
            "SUCCESS": "#18a058"
        }
        color = color_map.get(level, "#2ecc71")
        safe_message = html.escape(message)
        
        self.log_text.append(f'<span style="color: #7f8c8d;">[{timestamp}]</span> '
                            f'<span style="color: {color};">{safe_message}</span>')
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def update_status(self, message: str):
        """更新状态栏"""
        self.statusBar.showMessage(message)
    
    def refresh_ports(self):
        """刷新串口列表"""
        self.port_combo.clear()
        ports = self.xcp.get_available_ports()
        if ports:
            self.port_combo.addItems(ports)
            self.log(f"发现 {len(ports)} 个串口: {', '.join(ports)}")
        else:
            self.log("未发现可用串口", "WARN")
    
    def toggle_connection(self):
        """切换连接状态"""
        if self.xcp.is_connected:
            success, msg = self.xcp.disconnect()
            if success:
                self.connect_btn.setText("连接")
                self.update_ui_state(connected=False)
                self.log(msg)
                self.update_status("已断开连接")
        else:
            port = self.port_combo.currentText()
            baudrate = int(self.baudrate_combo.currentText())
            
            if not port:
                QMessageBox.warning(self, "警告", "请选择串口")
                return
            
            success, msg = self.xcp.connect(port, baudrate)
            if success:
                self.connect_btn.setText("断开")
                self.update_ui_state(connected=True)
                self.log(msg, "SUCCESS")
                self.update_status(f"已连接 {port} @ {baudrate}")
            else:
                self.log(msg, "ERROR")
                QMessageBox.critical(self, "错误", msg)
    
    def update_ui_state(self, connected: bool = False, unlocked: bool = None):
        """更新UI状态"""
        if unlocked is None:
            unlocked = self.xcp.is_unlocked
            
        self.unlock_btn.setEnabled(connected)
        self.verify_btn.setEnabled(connected)
        
        self.read_eep_btn.setEnabled(connected and unlocked)
        self.write_eep_btn.setEnabled(connected and unlocked)
        self.factory_reset_btn.setEnabled(connected and unlocked)
        self.reset_mcu_btn.setEnabled(connected and unlocked)
        self.send_btn.setEnabled(connected and unlocked)
        
        self.port_combo.setEnabled(not connected)
        self.baudrate_combo.setEnabled(not connected)
        self.refresh_btn.setEnabled(not connected)
        
        if unlocked:
            self.unlock_status_label.setText("状态: 已解锁 ✓")
            self.unlock_status_label.setStyleSheet("color: #18a058; font-weight: bold;")
        else:
            self.unlock_status_label.setText("状态: 未解锁")
            self.unlock_status_label.setStyleSheet("color: #e14d4d; font-weight: bold;")
    
    def send_unlock(self):
        """发送解锁命令"""
        self.log("发送解锁命令...")
        success, msg, tx_data, rx_data = self.xcp.send_unlock()
        if success:
            self.log(f"TX >> {tx_data}", "INFO")
            self.log(f"RX << {rx_data}", "SUCCESS")
            self.log(msg, "SUCCESS")
        else:
            if tx_data:
                self.log(f"TX >> {tx_data}", "INFO")
            self.log(msg, "ERROR")
    
    def verify_unlock(self):
        """验证解锁状态"""
        self.log("验证解锁状态...")
        success, msg, tx_data, rx_data = self.xcp.verify_unlock()
        if tx_data:
            self.log(f"TX >> {tx_data}", "INFO")
        if rx_data:
            self.log(f"RX << {rx_data}", "SUCCESS" if success else "WARN")

        if success:
            self.log(msg, "SUCCESS")
            self.update_ui_state(connected=True, unlocked=True)
            self.update_status("已解锁 - 可以进行读写操作")
        else:
            self.log(msg, "ERROR")
            self.update_ui_state(connected=True, unlocked=False)
    
    def read_eeprom(self):
        """读取EEPROM"""
        try:
            addr = int(self.addr_input.text())
            length = int(self.param_input.text())
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的地址和参数")
            return
        
        self.log(f"读取EEP: 地址={addr}, 长度={length}")
        success, msg = self.xcp.read_eeprom(addr, length)
        if success:
            self.log(msg, "SUCCESS")
        else:
            self.log(msg, "ERROR")
    
    def write_eeprom(self):
        """写入EEPROM"""
        try:
            addr = int(self.addr_input.text())
            data = int(self.param_input.text())
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的地址和参数")
            return
        
        self.log(f"写入EEP: 地址={addr}, 数据={data}")
        self.update_status("正在写入，请稍候...")
        QApplication.processEvents()
        
        success, msg = self.xcp.write_eeprom(addr, data)
        if success:
            self.log(msg, "SUCCESS")
            self.update_status("写入完成")
        else:
            self.log(msg, "ERROR")
            self.update_status("写入失败")
    
    def factory_reset(self):
        """恢复出厂设置"""
        reply = QMessageBox.question(
            self, "确认", "确定要恢复出厂设置吗？\n此操作需要约10秒完成。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.log("恢复出厂设置: 地址=9101, 数据=42240")
            self.update_status("正在恢复出厂设置，请稍候约10秒...")
            QApplication.processEvents()
            
            success, msg = self.xcp.factory_reset()
            if success:
                self.log(msg, "SUCCESS")
                self.update_status("恢复出厂设置完成")
            else:
                self.log(msg, "ERROR")
                self.update_status("恢复出厂设置失败")
    
    def reset_mcu(self):
        """复位MCU"""
        reply = QMessageBox.question(
            self, "确认", "确定要复位MCU吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.log("复位MCU: 地址=150541, 数据=42240")
            self.update_status("正在复位MCU...")
            QApplication.processEvents()
            
            success, msg = self.xcp.reset_mcu()
            if success:
                self.log(msg, "SUCCESS")
                self.update_status("MCU复位完成")
            else:
                self.log(msg, "ERROR")
                self.update_status("MCU复位失败")
    
    def write_conf(self):
        """写入参数"""
        pn = self.pn_input.text().strip()
        sn = self.sn_input.text().strip()
        kva = self.kva_input.text().strip()
        
        if not pn:
            QMessageBox.warning(self, "警告", "请输入P/N码")
            return
        if len(sn) != 14:
            QMessageBox.warning(self, "警告", "S/N必须为14位")
            return
        if not kva:
            QMessageBox.warning(self, "警告", "请输入KVA功率")
            return
        
        self.log(f"写入参数: P/N={pn}, S/N={sn}, KVA={kva}")
        self.update_status("正在写入参数...")
        QApplication.processEvents()
        
        success, msg = self.xcp.write_conf(pn, sn, kva)
        if success:
            self.log(msg, "SUCCESS")
            self.update_status("参数写入完成")
        else:
            self.log(msg, "ERROR")
            self.update_status("参数写入失败")
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.log("日志已清空")
    
    def exit_app(self):
        """退出应用"""
        reply = QMessageBox.question(
            self, "确认退出", "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.xcp.is_connected:
                self.xcp.disconnect()
            QApplication.quit()
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.xcp.is_connected:
            self.xcp.disconnect()
        event.accept()


def main():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xpc.tool.desktop")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    app_icon = QIcon()
    for logo_path in (
        Path(__file__).resolve().parent / "logo.png",
        Path(__file__).resolve().parent / "Logo.png",
        Path.cwd() / "logo.png",
        Path.cwd() / "Logo.png",
    ):
        if logo_path.exists():
            app_icon = XCPToolWindow._build_square_icon(str(logo_path))
            break
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    
    window = XCPToolWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
