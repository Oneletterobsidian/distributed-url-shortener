"""
一致性哈希：模拟多Redis/多DB节点分片

核心解决的问题：普通哈希取模(hash % 节点数)在节点数量变化时，
几乎所有数据都要重新分布；一致性哈希通过把节点和数据都映射到
一个环上，节点变化时只影响环上局部一小段区间的数据。
"""

import bisect
import hashlib


class ConsistentHashRing:
    def __init__(self, virtual_node_count: int = 150):
        self.virtual_node_count = virtual_node_count
        self.sorted_positions: list[int] = []       # 排好序的位置列表，方便二分查找
        self.position_to_node: dict[int, str] = {}  # 位置 -> 物理节点名

    def _hash(self, key: str) -> int:
        """把任意字符串，转换成环上的一个位置(0 ~ 2^32-1)"""
        digest = hashlib.md5(key.encode("utf-8")).digest()
        return int.from_bytes(digest, byteorder="big") % (2**32)

    def add_node(self, node_name: str) -> None:
        """添加一个物理节点，同时在环上安插多个虚拟节点"""
        for i in range(self.virtual_node_count):
            virtual_key = f"{node_name}-{i}"
            position = self._hash(virtual_key)

            self.position_to_node[position] = node_name
            bisect.insort(self.sorted_positions, position)

    def remove_node(self, node_name: str) -> None:
        """移除一个物理节点，同时清理它在环上的所有虚拟节点"""
        for i in range(self.virtual_node_count):
            virtual_key = f"{node_name}-{i}"
            position = self._hash(virtual_key)

            if position in self.position_to_node:
                del self.position_to_node[position]
                self.sorted_positions.remove(position)

    def get_node(self, data_key: str) -> str:
        """给定一个数据的key(比如短码)，找到它该归属的物理节点"""
        if not self.sorted_positions:
            raise RuntimeError("哈希环上还没有任何节点")

        position = self._hash(data_key)

        # bisect_left找到"第一个 >= position 的位置"对应的下标
        index = bisect.bisect_left(self.sorted_positions, position)

        # 如果超出了列表末尾，说明要"绕回"环的起点(这就是"环"的意义所在)
        if index == len(self.sorted_positions):
            index = 0

        found_position = self.sorted_positions[index]
        return self.position_to_node[found_position]