"""
Locust压测脚本：模拟真实用户对短链接服务的访问模式
"""

import random

from locust import HttpUser, task, between


class ShortenerUser(HttpUser):
    wait_time = between(0.1, 1)

    def on_start(self):
        """每个虚拟用户"上线"时执行一次：先创建一个短链接，后续反复访问它"""
        response = self.client.post(
            "/links", json={"long_url": "https://www.anthropic.com"}
        )
        if response.status_code == 200:
            self.short_code = response.json()["short_code"]
        else:
            self.short_code = None

    @task(10)
    def visit_short_link(self):
        """高频任务：访问已有的短链接(权重10，最常执行)"""
        if self.short_code:
            self.client.get(
                f"/{self.short_code}",
                name="/[short_code]",
                allow_redirects=False,  # 不跟随跳转，只关心我们自己服务的响应
            )

    @task(1)
    def create_new_link(self):
        """低频任务：创建新的短链接(权重1，偶尔执行)"""
        self.client.post(
            "/links",
            json={"long_url": f"https://example.com/{random.randint(1, 100000)}"},
            name="/links [POST]",
        )