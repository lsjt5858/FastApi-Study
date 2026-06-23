"""task-13：模拟邮件发送 + 类级 log（便于测试断言）。"""

from __future__ import annotations

import asyncio


class EmailLog:
    """类级邮件日志，方便测试观察 BackgroundTasks 是否真的跑了。

    生产场景应该写日志文件/DB/外发 SMTP；这里只演示流程。
    """

    entries: list[dict] = []

    @classmethod
    def append(cls, to: str, subject: str) -> None:
        cls.entries.append({"to": to, "subject": subject})

    @classmethod
    def reset(cls) -> None:
        cls.entries = []


async def send_welcome_email(to: str, post_title: str) -> None:
    """模拟发邮件：sleep 一段 + 写 log。

    被路由用 BackgroundTasks.add_task 调起，在响应之后才执行。
    """
    await asyncio.sleep(0.02)  # 模拟 SMTP 往返
    EmailLog.append(to, subject=f"New post published: {post_title}")
