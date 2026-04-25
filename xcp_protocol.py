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
    RESP_UNLOCK_OK_PREFIX = bytes([0xAB, 0xCF, 0x22, 0x81, 0x01])
    RESP_UNLOCK_FAIL_PREFIX = bytes([0xAB, 0x09, 0x05, 0x81])    
    FUNC_C9_READ_MEM = 0x52
    FUNC_C9_WRITE_MEM = 0x57
    CPU_ID_CSB = 0x01
    MEM_TYPE_EEP = 0x04
    MEM_TYPE_VAR = 0x05
    CMD_WRITE_CONF = 0x30
    PN_ADDR_WORD = 85277
    SN_ADDR_WORD = PN_ADDR_WORD + 10  # 20字节 = 10个word
    KVA_ADDR_WORD = 85347
    CRC_POLY = 0x102100
    
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

    @staticmethod
    def _format_word_lines(start_addr_word: int, data: bytes) -> str:
        """
        将按word读取到的数据格式化为地址/十六进制/十进制明细。
        协议数据为小端，按2字节一个word解析。
        """
        lines = ["地址    十六进制    十进制"]
        word_count = len(data) // 2
        for i in range(word_count):
            word = int.from_bytes(data[i * 2:(i + 1) * 2], byteorder='little', signed=False)
            lines.append(f"{start_addr_word + i}   0x{word:04x}   {word:>6}")
        return "\n".join(lines)

    @staticmethod
    def _calc_chk(frame_without_chk: bytes) -> int:
        """
        CHK算法：对帧内全部字节（不含CHK）求和，取8位二补数。
        """
        return (-sum(frame_without_chk)) & 0xFF

    def _build_c9_frame(self, func_code: int, mem_type: int, address_words: int,
                        size_words: int, data: bytes = b'') -> bytes:
        """
        构造C9协议帧
        TX:
        AB LEN C9 FuncCode 01 MemType Addr(4B LE) Size(4B LE) Data... CHK
        其中地址和长度入参为word，协议中按字节传输（*2）。
        """
        address_bytes = address_words * 2
        size_bytes = size_words * 2
        addr_le = address_bytes.to_bytes(4, byteorder='little', signed=False)
        size_le = size_bytes.to_bytes(4, byteorder='little', signed=False)

        # LEN = 从C9开始到Data结束（不含AB/LEN/CHK）
        length_field = 12 + len(data)

        body = bytes([0xAB, length_field, 0xC9, func_code, self.CPU_ID_CSB, mem_type]) + addr_le + size_le + data        
        chk = self._calc_chk(body)
        return body + bytes([chk])

    def _build_c9_write_eep_word_frame(self, address_words: int, word_data: int) -> bytes:
        """
        构造写EEP(1个word)专用帧：
        AB LEN C9 57 01 04 Addr4B(LE) Data2B(LE) CHK
        """
        address_bytes = address_words * 2
        addr_le = address_bytes.to_bytes(4, byteorder='little', signed=False)
        data_le = word_data.to_bytes(2, byteorder='little', signed=False)
        payload = bytes([0xC9, self.FUNC_C9_WRITE_MEM, self.CPU_ID_CSB, self.MEM_TYPE_EEP]) + addr_le + data_le
        frame = bytes([0xAB, len(payload)]) + payload
        chk = self._calc_chk(frame)
        return frame + bytes([chk])

    def _build_c9_write_mem_data_frame(self, address_words: int, mem_type: int, raw_data: bytes) -> bytes:
        """
        构造写内存变长数据帧：
        AB LEN C9 57 01 MemType Addr4B(LE) DataN CHK
        """
        address_bytes = address_words * 2
        addr_le = address_bytes.to_bytes(4, byteorder='little', signed=False)
        payload = bytes([0xC9, self.FUNC_C9_WRITE_MEM, self.CPU_ID_CSB, mem_type]) + addr_le + raw_data
        frame = bytes([0xAB, len(payload)]) + payload
        chk = self._calc_chk(frame)
        return frame + bytes([chk])

    def _crc_char(self, new_byte: int, crc: int) -> int:
        crc_calc = ((crc & 0xFFFF) << 8) + (new_byte & 0xFF)
        for _ in range(8):
            crc_calc <<= 1
            if (crc_calc & 0x1000000) != 0:
                crc_calc ^= self.CRC_POLY
        return (crc_calc >> 8) & 0xFFFF

    def _crc_word(self, new_word: int, crc: int) -> int:
        crc_calc = self._crc_char((new_word >> 8) & 0xFF, crc)
        crc_calc = self._crc_char(new_word & 0xFF, crc_calc)
        return crc_calc

    def _crc_string_number(self, value_20b: bytes, crc: int) -> int:
        """
        按固件算法处理字符串：忽略前导'0'，直到遇到首个非'0'字符；
        若全为0，则加入一个'0'字符参与CRC。
        """
        if not value_20b or value_20b[0] == 0:
            return crc

        zeros_skipped = False
        crc_calc = crc
        for c in value_20b[:20]:
            if c == 0:
                break
            if (c != 0x30) or zeros_skipped:
                zeros_skipped = True
                crc_calc = self._crc_char(c, crc_calc)

        if not zeros_skipped:
            crc_calc = self._crc_char(0x30, crc_calc)
        return crc_calc

    def _calc_kva_magic(self, sn_20b: bytes, pn_20b: bytes, kva: int) -> int:
        """
        KVA校验算法（MagicNum）：
        CRC-CCITT over:
        - SN(去前导0)
        - 100*KVA (word)
        - 0xABDC
        - PN(去前导0)
        - 0x0000 (finalize)
        """
        crc = 0xFFFF
        crc = self._crc_string_number(sn_20b, crc)
        crc = self._crc_word((100 * kva) & 0xFFFF, crc)
        crc = self._crc_word(0xABDC, crc)
        crc = self._crc_string_number(pn_20b, crc)
        crc = self._crc_word(0, crc)
        return crc & 0xFFFF

    def _build_c9_write_kva_frame(self, kva: int, sn_20b: bytes, pn_20b: bytes) -> bytes:
        """
        构造KVA发送帧：
        AB LEN C9 57 01 04 Addr4B MagicLo MagicHi KvaLo KvaHi KvaLo KvaHi CHK
        """
        magic = self._calc_kva_magic(sn_20b=sn_20b, pn_20b=pn_20b, kva=kva)
        addr_le = (self.KVA_ADDR_WORD * 2).to_bytes(4, byteorder='little', signed=False)
        kva_word = kva.to_bytes(2, byteorder='little', signed=False)
        payload = (
            bytes([0xC9, self.FUNC_C9_WRITE_MEM, self.CPU_ID_CSB, self.MEM_TYPE_EEP])
            + addr_le
            + magic.to_bytes(2, byteorder='little', signed=False)
            + kva_word
            + kva_word
        )
        frame = bytes([0xAB, len(payload)]) + payload
        chk = self._calc_chk(frame)
        return frame + bytes([chk])

    def _parse_c9_ack(self, response: bytes, expected_func: int, expected_mem_type: int,
                      expected_addr_words: int, expected_size_words: int) -> Tuple[bool, str, bytes]:
        """
        解析并校验ACK：
        AB C9 Len 81 Func CpuId MemType Addr4B Size4B Data... CHK
        不满足格式即失败。
        """
        if len(response) < 16:
            return False, "响应长度不足，非ACK格式", b''
        if response[0] != 0xAB or response[1] != 0xC9:
            return False, "响应头错误，非ACK格式", b''
        if response[3] != 0x81:
            return False, "响应状态不是ACK(0x81)", b''

        # rx_len = response[2]
        # expected_total_len = rx_len + 5  # AB C9 Len 81 [Len bytes] CHK
        # if len(response) != expected_total_len:
        #     return False, f"响应长度不匹配，期望{expected_total_len}字节，实际{len(response)}字节", b''

        chk = response[-1]
        calc_chk = self._calc_chk(response[:-1])
        if chk != calc_chk:
            return False, f"CHK校验失败，期望{calc_chk:02X}，实际{chk:02X}", b''

        func = response[4]
        cpu_id = response[5]
        mem_type = response[6]
        addr_bytes = int.from_bytes(response[7:11], byteorder='little', signed=False)
        size_bytes = int.from_bytes(response[11:15], byteorder='little', signed=False)
        data = response[15:-1]

        if func != expected_func:
            return False, f"FuncCode不匹配，期望{expected_func:02X}，实际{func:02X}", b''
        if mem_type != expected_mem_type:
            return False, f"MemType不匹配，期望{expected_mem_type:02X}，实际{mem_type:02X}", b''

        expected_addr_bytes = expected_addr_words * 2
        expected_size_bytes = expected_size_words * 2
        if addr_bytes != expected_addr_bytes:
            return False, f"地址不匹配，期望{expected_addr_bytes}，实际{addr_bytes}", b''
        if size_bytes != expected_size_bytes:
            return False, f"长度不匹配，期望{expected_size_bytes}字节，实际{size_bytes}字节", b''
        if len(data) != size_bytes:
            return False, f"Data长度不匹配，期望{size_bytes}字节，实际{len(data)}字节", b''

        # CpuId按协议记录，不作为失败条件（避免后续多CPU场景误判）
        _ = cpu_id
        return True, "", data

    def _parse_c9_write_ack(self, response: bytes, expected_mem_type: int,
                            expected_addr_words: int, expected_size_bytes: int) -> Tuple[bool, str]:
        """
        解析写命令ACK：
        AB C9 0B 81 RespCode CpuId MemType Addr4B Size4B CHK
        RespCode: 58/57=成功, 4E=失败
        """
        if len(response) < 16:
            return False, "响应长度不足"
        if response[0] != 0xAB or response[1] != 0xC9:
            return False, "响应头错误"
        if response[2] != 0x0B:
            return False, f"响应长度字段错误({response[2]:02X})"
        if response[3] != 0x81:
            return False, "非ACK响应"

        resp_code = response[4]
        mem_type = response[6]
        addr_bytes = int.from_bytes(response[7:11], byteorder='little', signed=False)
        size_bytes = int.from_bytes(response[11:15], byteorder='little', signed=False)

        if mem_type != expected_mem_type:
            return False, f"MemType不匹配(期望{expected_mem_type:02X}, 实际{mem_type:02X})"

        expected_addr = expected_addr_words * 2
        if addr_bytes != expected_addr:
            return False, f"响应地址不匹配(期望{expected_addr}, 实际{addr_bytes})"
        if size_bytes != expected_size_bytes:
            return False, f"响应长度不匹配(期望{expected_size_bytes}, 实际{size_bytes})"

        if resp_code in (0x58, 0x57):
            return True, f"RespCode: {resp_code:02X}"
        if resp_code == 0x4E:
            return False, "设备返回RespCode=4E"
        return False, f"未知RespCode={resp_code:02X}"
    
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
                resp_upper = response.upper()
                if b'FAIL' in resp_upper:
                    self.is_unlocked = False
                    return False, "设备拒绝解锁命令（返回FAIL）", tx_hex, rx_hex
                msg = f"解锁命令已发送，接收 {len(response)} 字节"
                return True, msg, tx_hex, rx_hex
            return False, "解锁命令已发送，但未收到响应", tx_hex, "(无响应)"
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

        success = False
        response = b''
        max_retries = 3
        for i in range(max_retries):
            success, response = self._send_and_receive(tx_data, timeout=3.0)
            if success and response:
                break
            if i < max_retries - 1:
                time.sleep(0.2)

        if success and response:
            rx_hex = self._bytes_to_hex(response)
            if response.startswith(self.RESP_UNLOCK_OK_PREFIX):
                self.is_unlocked = True
                return True, f"解锁成功，接收 {len(response)} 字节", tx_hex, rx_hex
            if response.startswith(self.RESP_UNLOCK_FAIL_PREFIX):
                self.is_unlocked = False
                return False, "解锁失败", tx_hex, rx_hex
            self.is_unlocked = False
            return False, "解锁验证失败（响应格式不匹配）", tx_hex, rx_hex

        self.is_unlocked = False
        return False, f"验证失败，无响应（已重试{max_retries}次）", tx_hex, "(无响应)"
    
    def read_eeprom(self, address: int, length: int) -> Tuple[bool, str, str, str]:
        """
        读取EEPROM数据
        :param address: 地址
        :param length: 长度
        :return: (成功标志, 数据或错误消息)
        """
        if not self.is_connected:
            return False, "请先连接串口", "", ""
        if not self.is_unlocked:
            return False, "请先解锁设备", "", ""

        if address < 0 or length <= 0:
            return False, "地址和长度必须为正整数（word）", "", ""

        tx = self._build_c9_frame(
            func_code=self.FUNC_C9_READ_MEM,
            mem_type=self.MEM_TYPE_EEP,
            address_words=address,
            size_words=length,
            data=b''
        )

        tx_hex = self._bytes_to_hex(tx)
        success, response = self._send_and_receive(tx, timeout=3.0)
        if not success or not response:
            return False, "读取失败，无响应", tx_hex, "(无响应)"

        rx_hex = self._bytes_to_hex(response)

        ok, err, data = self._parse_c9_ack(
            response=response,
            expected_func=self.FUNC_C9_READ_MEM,
            expected_mem_type=self.MEM_TYPE_EEP,
            expected_addr_words=address,
            expected_size_words=length
        )
        if not ok:
            return False, f"读取失败: {err}", tx_hex, rx_hex

        formatted = ' '.join(f'{b:02X}' for b in data)
        words_detail = self._format_word_lines(address, data)
        return True, f"读取成功 地址(word): {address} 长度(word): {length} 数据: {formatted}\n{words_detail}", tx_hex, rx_hex

    def read_var(self, address: int, length: int) -> Tuple[bool, str, str, str]:
        """
        读取VAR数据（MemType=0x05）
        :param address: 地址（word）
        :param length: 长度（word）
        :return: (成功标志, 数据或错误消息, 发送报文HEX, 接收报文HEX)
        """
        if not self.is_connected:
            return False, "请先连接串口", "", ""
        if not self.is_unlocked:
            return False, "请先解锁设备", "", ""

        if address < 0 or length <= 0:
            return False, "地址和长度必须为正整数（word）", "", ""

        tx = self._build_c9_frame(
            func_code=self.FUNC_C9_READ_MEM,
            mem_type=self.MEM_TYPE_VAR,
            address_words=address,
            size_words=length,
            data=b''
        )

        tx_hex = self._bytes_to_hex(tx)
        success, response = self._send_and_receive(tx, timeout=3.0)
        if not success or not response:
            return False, "读取VAR失败，无响应", tx_hex, "(无响应)"

        rx_hex = self._bytes_to_hex(response)
        ok, err, data = self._parse_c9_ack(
            response=response,
            expected_func=self.FUNC_C9_READ_MEM,
            expected_mem_type=self.MEM_TYPE_VAR,
            expected_addr_words=address,
            expected_size_words=length
        )
        if not ok:
            return False, f"读取VAR失败: {err}", tx_hex, rx_hex

        formatted = ' '.join(f'{b:02X}' for b in data)
        words_detail = self._format_word_lines(address, data)
        return True, f"读取VAR成功 地址(word): {address} 长度(word): {length} 数据: {formatted}\n{words_detail}", tx_hex, rx_hex
    
    def write_eeprom(self, address: int, data: int, timeout: float = 12.0) -> Tuple[bool, str, str, str]:
        """
        写入EEPROM数据
        :param address: 地址
        :param data: 数据
        :param timeout: 超时时间
        :return: (成功标志, 消息)
        """
        if not self.is_connected:
            return False, "请先连接串口", "", ""
        if not self.is_unlocked:
            return False, "请先解锁设备", "", ""

        if address < 0:
            return False, "地址必须为非负整数（word）", "", ""
        if data < 0 or data > 0xFFFF:
            return False, "写入数据必须是0~65535（1个word）", "", ""

        tx = self._build_c9_write_eep_word_frame(address_words=address, word_data=data)
        tx_hex = self._bytes_to_hex(tx)
        success, response = self._send_and_receive(tx, timeout=timeout)
        if not success or not response:
            return False, "写入失败，无响应", tx_hex, "(无响应)"

        rx_hex = self._bytes_to_hex(response)
        ok, detail = self._parse_c9_write_ack(
            response=response,
            expected_mem_type=self.MEM_TYPE_EEP,
            expected_addr_words=address,
            expected_size_bytes=2
        )
        if not ok:
            return False, f"写入失败: {detail}", tx_hex, rx_hex
        return True, f"写入成功\n地址(word): {address}\n数据(word): {data}\n{detail}", tx_hex, rx_hex
    
    def write_conf(self, pn: str, sn: str, kva: str) -> Tuple[bool, str, str, str]:
        """
        写入参数信息
        :param pn: P/N码
        :param sn: S/N序列号 (14位)
        :param kva: 功率
        :return: (成功标志, 消息, 发送报文HEX, 接收报文HEX)
        """
        if not self.is_connected:
            return False, "请先连接串口", "", ""
        if not self.is_unlocked:
            return False, "请先解锁设备", "", ""

        try:
            pn_data = pn.encode('ascii')
            sn_data = sn.encode('ascii')
        except UnicodeEncodeError:
            return False, "P/N和S/N仅支持ASCII字符", "", ""
        try:
            kva_value = int(kva)
        except ValueError:
            return False, "KVA必须是整数", "", ""
        if kva_value < 0 or kva_value > 0xFFFF:
            return False, "KVA超出范围(0~65535)", "", ""

        # PN/SN固定20字节，不足补0，超过截断
        pn_data = pn_data[:20].ljust(20, b'\x00')
        sn_data = sn_data[:20].ljust(20, b'\x00')

        tx_list: List[str] = []
        rx_list: List[str] = []

        for label, addr_word, payload in (
            ("P/N", self.PN_ADDR_WORD, pn_data),
            ("S/N", self.SN_ADDR_WORD, sn_data),
        ):
            tx = self._build_c9_write_mem_data_frame(
                address_words=addr_word,
                mem_type=self.MEM_TYPE_EEP,
                raw_data=payload
            )
            tx_hex = self._bytes_to_hex(tx)
            tx_list.append(f"{label}: {tx_hex}")

            success, response = self._send_and_receive(tx, timeout=5.0)
            if not success or not response:
                return False, f"{label}写入失败，无响应", " | ".join(tx_list), " | ".join(rx_list) if rx_list else "(无响应)"

            rx_hex = self._bytes_to_hex(response)
            rx_list.append(f"{label}: {rx_hex}")

            ok, detail = self._parse_c9_write_ack(
                response=response,
                expected_mem_type=self.MEM_TYPE_EEP,
                expected_addr_words=addr_word,
                expected_size_bytes=len(payload)
            )
            if not ok:
                return False, f"{label}写入失败: {detail}", " | ".join(tx_list), " | ".join(rx_list)

        kva_tx = self._build_c9_write_kva_frame(kva=kva_value, sn_20b=sn_data, pn_20b=pn_data)
        kva_tx_hex = self._bytes_to_hex(kva_tx)
        tx_list.append(f"KVA: {kva_tx_hex}")
        success, response = self._send_and_receive(kva_tx, timeout=5.0)
        if not success or not response:
            return False, "KVA写入失败，无响应", " | ".join(tx_list), " | ".join(rx_list) if rx_list else "(无响应)"
        kva_rx_hex = self._bytes_to_hex(response)
        rx_list.append(f"KVA: {kva_rx_hex}")

        ok, detail = self._parse_c9_write_ack(
            response=response,
            expected_mem_type=self.MEM_TYPE_EEP,
            expected_addr_words=self.KVA_ADDR_WORD,
            expected_size_bytes=4
        )
        if not ok:
            return False, f"KVA写入失败: {detail}", " | ".join(tx_list), " | ".join(rx_list)

        return True, f"参数写入成功\nP/N: {pn}\nS/N: {sn}\nKVA: {kva_value}", " | ".join(tx_list), " | ".join(rx_list)
    
    def factory_reset(self) -> Tuple[bool, str, str, str]:
        """恢复出厂设置 (地址9101, 数据42240)"""
        return self.write_eeprom(9101, 42240, timeout=12.0)
    
    def reset_mcu(self) -> Tuple[bool, str, str, str]:
        """复位MCU (地址150541, 数据42240)"""
        return self.write_eeprom(150541, 42240, timeout=5.0)
