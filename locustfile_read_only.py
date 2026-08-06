"""
专门压测GET跳转路径的Locust脚本——不掺杂创建请求，避免被限流规则干扰，
纯粹测试"读路径"（缓存命中场景为主）在不同并发下的真实承载能力。
"""

import random

from locust import HttpUser, task, between, events

# 共享的短码池，所有虚拟用户复用，避免每个用户各自触发限流
SHARED_SHORT_CODES = []


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """整个压测开始前，只执行一次：预先创建20个短链接备用"""
    import httpx

    host = environment.host
    with httpx.Client(base_url=host) as client:
        for i in range(20):
            response = client.post(
                "/links", json={"long_url": f"https://example.com/preload-{i}"}
            )
            if response.status_code == 200:
                SHARED_SHORT_CODES.append(response.json()["short_code"])

    print(f"预创建了 {len(SHARED_SHORT_CODES)} 个短链接供压测使用")


class ReadOnlyUser(HttpUser):
    wait_time = between(0.01, 0.1)  # 更短的等待，模拟更高强度的访问

    @task
    def visit_short_link(self):
        if SHARED_SHORT_CODES:
            code = random.choice(SHARED_SHORT_CODES)
            self.client.get(f"/{code}", name="/[short_code]", allow_redirects=False)