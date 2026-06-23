"""task-14：WebSocket 评论路由。

/ws/posts/{post_id}/comments
- 连接时自动 accept + 加入房间
- 收到 type==ping -> 回 pong（心跳）
- 收到 type==comment -> 广播给整个房间（包括发送者）
- 断开 -> 从房间移除 + 广播 leave
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/posts/{post_id}/comments")
async def ws_comments(websocket: WebSocket, post_id: int) -> None:
    """文章评论 WebSocket。"""
    room = f"post:{post_id}"
    await manager.connect(room, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            # 其他消息广播到整个房间（含发送者）
            await manager.broadcast(room, data)
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
        await manager.broadcast(room, {"type": "leave", "room": room})
        logger.info("ws disconnected: room=%s", room)
