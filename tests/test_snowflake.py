"""
测试雪花算法和Base62编码——这两个都是纯函数/纯逻辑，不依赖外部服务
"""

from app.snowflake import SnowflakeGenerator, base62_encode


def test_base62_encode_zero():
    """边界情况：0应该编码成字母表的第一个字符"""
    assert base62_encode(0) == "0"


def test_base62_encode_is_deterministic():
    """同样的输入，必须永远得到同样的输出"""
    assert base62_encode(12345) == base62_encode(12345)


def test_base62_encode_different_inputs_differ():
    """不同的输入，编码结果应该不同(不能撞车)"""
    assert base62_encode(1) != base62_encode(2)


def test_snowflake_generates_unique_ids():
    """连续生成多个ID，不应该有重复"""
    generator = SnowflakeGenerator(machine_id=1)
    ids = [generator.next_id() for _ in range(1000)]
    assert len(ids) == len(set(ids))  # 去重后数量应该不变，说明没有重复


def test_snowflake_different_machines_no_collision():
    """不同机器ID的生成器，生成的ID不应该冲突"""
    gen1 = SnowflakeGenerator(machine_id=1)
    gen2 = SnowflakeGenerator(machine_id=2)

    ids1 = {gen1.next_id() for _ in range(100)}
    ids2 = {gen2.next_id() for _ in range(100)}

    assert ids1.isdisjoint(ids2)  # 两个集合没有交集