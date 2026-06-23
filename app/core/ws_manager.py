"""task-14：WebSocket 连接管理器（房间模型）。

- 每个 post_id 一个房间
- broadcast 失败的连接自动清理
- 不区分用户身份（task-15 可加 token）
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket


class ConnectionManager:
    """每个房间是一个 set[WebSocket]；广播时自动清理失败连接。"""

    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, room: str, ws: WebSocket) -> None:
        """accept + 加入房间。"""
        await ws.accept()
        self.rooms[room].add(ws)

    def disconnect(self, room: str, ws: WebSocket) -> None:
        """从房间移除（不存在不报错）。"""
        self.rooms[room].discard(ws)
        if not self.rooms[room]:
            self.rooms.pop(room, None)

    async def broadcast(
        self,
        room: str,
        message: dict,
        exclude: WebSocket | None = None,
    ) -> None:
        """广播消息到房间所有连接。失败的连接被自动清理。"""
        dead: list[WebSocket] = []
        for ws in list(self.rooms.get(room, set())):
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)


# 全局单例
manager = ConnectionManager()
