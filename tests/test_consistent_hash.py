"""
测试一致性哈希——同样是纯逻辑，不依赖任何外部服务
"""

from app.consistent_hash import ConsistentHashRing


def test_same_key_always_maps_to_same_node():
    """同一个key，多次查询应该始终落到同一个节点"""
    ring = ConsistentHashRing(virtual_node_count=100)
    ring.add_node("node0")
    ring.add_node("node1")

    result1 = ring.get_node("some-short-code")
    result2 = ring.get_node("some-short-code")

    assert result1 == result2


def test_adding_node_only_affects_partial_data():
    """扩容时，只有一部分数据的归属会变化，不应该是全部或者一个都不变"""
    ring = ConsistentHashRing(virtual_node_count=150)
    ring.add_node("node0")
    ring.add_node("node1")
    ring.add_node("node2")

    keys = [f"key-{i}" for i in range(1000)]
    before = {key: ring.get_node(key) for key in keys}

    ring.add_node("node3")

    after = {key: ring.get_node(key) for key in keys}

    changed_count = sum(1 for key in keys if before[key] != after[key])

    # 断言：确实有一部分变化了(不是完全没变)，但也不是全部都变了
    assert 0 < changed_count < len(keys)


def test_empty_ring_raises_error():
    """环上还没有任何节点时，查询应该抛出明确的异常，而不是静默返回错误结果"""
    ring = ConsistentHashRing()
    try:
        ring.get_node("some-key")
        assert False, "应该抛出异常，但没有"
    except RuntimeError:
        pass