"""
短码生成算法：雪花算法（Snowflake）生成全局唯一ID + Base62编码压缩成短字符串

雪花算法64位结构：
    1位符号位（固定0） | 41位时间戳 | 10位机器ID | 12位序列号
"""

import time
import threading

# 起始时间点（自己定义的纪元，不是1970年）：这里用项目大致启动的时间
# 换算成毫秒时间戳，比如 2026-01-01 00:00:00 UTC
EPOCH = 1767225600000  # 2026-01-01 00:00:00 UTC 对应的毫秒时间戳

# 各段占用的位数
MACHINE_ID_BITS = 10
SEQUENCE_BITS = 12

MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1     # 1023
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1          # 4095

MACHINE_ID_SHIFT = SEQUENCE_BITS                          # 机器ID要左移12位
TIMESTAMP_SHIFT = SEQUENCE_BITS + MACHINE_ID_BITS          # 时间戳要左移22位


class SnowflakeGenerator:
    """
    每个FastAPI实例启动时，实例化一个SnowflakeGenerator，
    传入自己的machine_id（对应docker-compose.yml里的INSTANCE_ID）。
    """

    def __init__(self, machine_id: int):
        if machine_id < 0 or machine_id > MAX_MACHINE_ID:
            raise ValueError(f"machine_id 必须在 0~{MAX_MACHINE_ID} 之间")

        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1

        # 加锁：防止同一个实例内，多个并发请求同时调用生成方法时，
        # 序列号被同时读写导致的竞态条件（race condition）
        self.lock = threading.Lock()

    def _current_millis(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_timestamp: int) -> int:
        """如果同一毫秒内序列号已经用完(4096个)，就自旋等到下一毫秒"""
        timestamp = self._current_millis()
        while timestamp <= last_timestamp:
            timestamp = self._current_millis()
        return timestamp

    def next_id(self) -> int:
        with self.lock:
            timestamp = self._current_millis()

            if timestamp < self.last_timestamp:
                # 系统时钟被人为往回调了，这是雪花算法的一个已知风险点
                raise RuntimeError("系统时钟回退，拒绝生成ID")

            if timestamp == self.last_timestamp:
                # 同一毫秒内，序列号+1
                self.sequence = (self.sequence + 1) & MAX_SEQUENCE
                if self.sequence == 0:
                    # 序列号用完了(超过4095)，等到下一毫秒
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                # 进入新的一毫秒，序列号归零
                self.sequence = 0

            self.last_timestamp = timestamp

            # 核心拼接：把时间戳、机器ID、序列号，通过左移+或运算拼成一个64位整数
            snowflake_id = (
                ((timestamp - EPOCH) << TIMESTAMP_SHIFT)
                | (self.machine_id << MACHINE_ID_SHIFT)
                | self.sequence
            )
            return snowflake_id


# Base62编码：把雪花算法生成的大整数，压缩成短字符串
BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base62_encode(num: int) -> str:
    if num == 0:
        return BASE62_ALPHABET[0]

    chars = []
    base = len(BASE62_ALPHABET)  # 62

    while num > 0:
        num, remainder = divmod(num, base)
        chars.append(BASE62_ALPHABET[remainder])

    # 因为是从低位开始不断取余数，所以最后要把结果反转过来
    return "".join(reversed(chars))


def generate_short_code(machine_id: int, generator: SnowflakeGenerator) -> str:
    """对外暴露的入口函数：生成一个雪花ID，再编码成短码字符串"""
    snowflake_id = generator.next_id()
    return base62_encode(snowflake_id)