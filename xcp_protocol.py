# -*- coding: utf-8 -*-
"""
XCP协议通信模块
"""

import serial
import serial.tools.list_ports
import struct
import time
from typing import Optional, Tuple, List


class XCPProtocol:
    """XCP协议通信类"""
    
    # 命令定义 (HEX: 50 43 50 53 59 46 0D 0A)
    CMD_UNLOCK = bytes([0x50, 0x43, 0x50, 0x53, 0x59, 0x46, 0x0D, 0x0A])
    CMD_UNLOCK_VERIFY = bytes([0xAB, 0x04, 0xCF, 0x00, 0x00, 0x00, 0x82])
    CMD_READ_EEP = 0x10
    CMD_WRITE_EEP = 0x20
    CMD_WRITE_CONF = 0x30
    
    # 响应状态
    RESP_OK = 0x00
    RESP_UNLOCKED = 0x01
    
    def __init__(self):
        self.serial: Optional[serial.Serial] = None
        self.is_connected = False
        self.is_unlocked = False
        
    @staticmethod
    def get_available_ports() -> List[str]:
        """获取可用的串口列表"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port: str, baudrate: int, 
                stopbits: int = 1, databits: int = 8, 
                parity: str = 'N') -> Tuple[bool, str]:
        """
        连接串口
        :param port: COM口
        :param baudrate: 波特率
        :param stopbits: 停止位
        :param databits: 数据位
        :param parity: 校验位
        :return: (成功标志, 消息)
        """
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
            
            stopbits_map = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}
            databits_map = {5: serial.FIVEBITS, 6: serial.SIXBITS, 
                           7: serial.SEVENBITS, 8: serial.EIGHTBITS}
            parity_map = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 
                         'O': serial.PARITY_ODD}
            
            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                stopbits=stopbits_map.get(stopbits, serial.STOPBITS_ONE),
                bytesize=databits_map.get(databits, serial.EIGHTBITS),
                parity=parity_map.get(parity, serial.PARITY_NONE),
                timeout=2,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            self.is_connected = True
            return True, f"已连接到 {port}"
        except Exception as e:
            self.is_connected = False
            return False, f"连接失败: {str(e)}"
    
    def disconnect(self) -> Tuple[bool, str]:
        """断开串口连接"""
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
            self.is_connected = False
            self.is_unlocked = False
            return True, "已断开连接"
        except Exception as e:
            return False, f"断开失败: {str(e)}"
    
    def _send_and_receive(self, data: bytes, timeout: float = 2.0) -> Tuple[bool, bytes]:
        """
        发送数据并接收响应
        :param data: 要发送的数据
        :param timeout: 超时时间
        :return: (成功标志, 响应数据)
        """
        if not self.serial or not self.serial.is_open:
            return False, b''
        
        try:
            # 清空接收缓冲区
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # 发送数据
            written = self.serial.write(data)
            self.serial.flush()
            
            # 等待设备处理并响应
            time.sleep(0.2)
            
            # 读取响应
            response = b''
            self.serial.timeout = 0.3
            end_time = time.time() + timeout
            
            while time.time() < end_time:
                # 检查缓冲区
                waiting = self.serial.in_waiting
                if waiting > 0:
                    chunk = self.serial.read(waiting)
                    if chunk:
                        response += chunk
                    # 继续等待更多数据
                    time.sleep(0.1)
                else:
                    if response:
                        # 已有数据，再等一下确认没有更多
                        time.sleep(0.15)
                        if self.serial.in_waiting == 0:
                            break
                    else:
                        # 还没收到数据，继续等
                        time.sleep(0.1)
            
            return True, response
        except Exception as e:
            return False, str(e).encode()
    
    @staticmethod
    def _bytes_to_hex(data: bytes) -> str:
        """将字节转换为HEX字符串显示，如: 50 43 50 53"""
        return ' '.join(f'{b:02X}' for b in data)
    
    def send_unlock(self) -> Tuple[bool, str, str, str]:
        """
        发送解锁命令
        :return: (成功标志, 消息, 发送报文HEX, 接收报文HEX)
        """
        if not self.is_connected:
            return False, "请先连接串口", "", ""
        
        tx_data = self.CMD_UNLOCK
        tx_hex = self._bytes_to_hex(tx_data)
        
        success, response = self._send_and_receive(tx_data)
        if success:
            if response:
                rx_hex = self._bytes_to_hex(response)
                msg = f"解锁命令已发送，接收 {len(response)} 字节"
            else:
                rx_hex = "(无响应)"
                msg = "解锁命令已发送，未收到响应"
            return True, msg, tx_hex, rx_hex
        return False, "解锁命令发送失败", tx_hex, ""
    
    def verify_unlock(self) -> Tuple[bool, str, str, str]:
        """
        验证解锁状态
        :return: (成功标志, 消息, 发送报文HEX, 接收报文HEX)
        """
        if not self.is_connected:
            return False, "请先连接串口", "", ""

        tx_data = self.CMD_UNLOCK_VERIFY
        tx_hex = self._bytes_to_hex(tx_data)
        success, response = self._send_and_receive(tx_data)

        if success and response:
            rx_hex = self._bytes_to_hex(response)
            if response[0] == self.RESP_UNLOCKED or b'OK' in response or b'UNLOCK' in response.upper():
                self.is_unlocked = True
                return True, f"解锁成功，接收 {len(response)} 字节", tx_hex, rx_hex
            return False, "解锁验证失败", tx_hex, rx_hex

        return False, "验证失败，无响应", tx_hex, "(无响应)"
    
    def read_eeprom(self, address: int, length: int) -> Tuple[bool, str]:
        """
        读取EEPROM数据
        :param address: 地址
        :param length: 长度
        :return: (成功标志, 数据或错误消息)
        """
        if not self.is_connected:
            return False, "请先连接串口"
        if not self.is_unlocked:
            return False, "请先解锁设备"
        
        cmd = struct.pack('>BIH', self.CMD_READ_EEP, address, length)
        success, response = self._send_and_receive(cmd)
        
        if success and len(response) > 0:
            if len(response) >= length:
                hex_data = response[:length].hex().upper()
                formatted = ' '.join([hex_data[i:i+2] for i in range(0, len(hex_data), 2)])
                return True, f"读取成功\n地址: {address}\n数据: {formatted}"
            return True, f"读取数据: {response.hex().upper()}"
        return False, "读取失败，无响应"
    
    def write_eeprom(self, address: int, data: int, timeout: float = 12.0) -> Tuple[bool, str]:
        """
        写入EEPROM数据
        :param address: 地址
        :param data: 数据
        :param timeout: 超时时间
        :return: (成功标志, 消息)
        """
        if not self.is_connected:
            return False, "请先连接串口"
        if not self.is_unlocked:
            return False, "请先解锁设备"
        
        cmd = struct.pack('>BII', self.CMD_WRITE_EEP, address, data)
        success, response = self._send_and_receive(cmd, timeout=timeout)
        
        if success:
            if len(response) > 0 and (response[0] == self.RESP_OK or b'OK' in response):
                return True, f"写入成功\n地址: {address}\n数据: {data}"
            elif len(response) > 0:
                return True, f"写入完成\n地址: {address}\n数据: {data}\n响应: {response.hex()}"
            return True, f"写入完成\n地址: {address}\n数据: {data}"
        return False, "写入失败"
    
    def write_conf(self, pn: str, sn: str, kva: str) -> Tuple[bool, str]:
        """
        写入参数信息
        :param pn: P/N码
        :param sn: S/N序列号 (14位)
        :param kva: 功率
        :return: (成功标志, 消息)
        """
        if not self.is_connected:
            return False, "请先连接串口"
        if not self.is_unlocked:
            return False, "请先解锁设备"
        
        if len(sn) != 14:
            return False, "S/N必须为14位"
        
        pn_bytes = pn.encode('ascii').ljust(32, b'\x00')[:32]
        sn_bytes = sn.encode('ascii')
        kva_bytes = kva.encode('ascii').ljust(8, b'\x00')[:8]
        
        cmd = struct.pack('>B', self.CMD_WRITE_CONF) + pn_bytes + sn_bytes + kva_bytes
        success, response = self._send_and_receive(cmd, timeout=5.0)
        
        if success:
            if len(response) > 0 and (response[0] == self.RESP_OK or b'OK' in response):
                return True, f"参数写入成功\nP/N: {pn}\nS/N: {sn}\nKVA: {kva}"
            elif len(response) > 0:
                return True, f"参数写入完成\nP/N: {pn}\nS/N: {sn}\nKVA: {kva}\n响应: {response.hex()}"
            return True, f"参数写入完成\nP/N: {pn}\nS/N: {sn}\nKVA: {kva}"
        return False, "参数写入失败"
    
    def factory_reset(self) -> Tuple[bool, str]:
        """恢复出厂设置 (地址9101, 数据42240)"""
        return self.write_eeprom(9101, 42240, timeout=12.0)
    
    def reset_mcu(self) -> Tuple[bool, str]:
        """复位MCU (地址150541, 数据42240)"""
        return self.write_eeprom(150541, 42240, timeout=5.0)
