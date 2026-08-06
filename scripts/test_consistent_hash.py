"""
验证脚本：证明一致性哈希在"新增节点"时，只有一小部分数据需要重新分布，
而不是像普通哈希取模那样几乎全部重新洗牌。

运行方式（项目根目录下）：
    python -m scripts.test_consistent_hash
"""

from app.consistent_hash import ConsistentHashRing


def simulate_naive_hash_remap(short_codes: list[str], old_node_count: int, new_node_count: int) -> float:
    """模拟"普通哈希取模"方式，节点数变化后，数据重新分布的比例"""
    changed = 0
    for code in short_codes:
        old_node = hash(code) % old_node_count
        new_node = hash(code) % new_node_count
        if old_node != new_node:
            changed += 1
    return changed / len(short_codes) * 100


def simulate_consistent_hash_remap(short_codes: list[str]) -> float:
    """模拟一致性哈希方式，新增一个节点后，数据重新分布的比例"""
    ring = ConsistentHashRing(virtual_node_count=150)
    ring.add_node("redis-node-0")
    ring.add_node("redis-node-1")
    ring.add_node("redis-node-2")

    # 记录扩容前，每个短码分配到哪个节点
    before = {code: ring.get_node(code) for code in short_codes}

    # 新增一个节点(模拟扩容)
    ring.add_node("redis-node-3")

    # 记录扩容后，每个短码分配到哪个节点
    after = {code: ring.get_node(code) for code in short_codes}

    changed = sum(1 for code in short_codes if before[code] != after[code])
    return changed / len(short_codes) * 100


if __name__ == "__main__":
    # 生成10000个模拟短码
    short_codes = [f"shortcode-{i}" for i in range(10000)]

    naive_percent = simulate_naive_hash_remap(short_codes, old_node_count=3, new_node_count=4)
    consistent_percent = simulate_consistent_hash_remap(short_codes)

    print(f"普通哈希取模，节点从3台变4台，需要重新分布的数据比例: {naive_percent:.2f}%")
    print(f"一致性哈希，节点从3台变4台，需要重新分布的数据比例: {consistent_percent:.2f}%")