# task-14: WebSocket 实时通信

## 目标
为博客加文章直播评论：WS /ws/posts/{post_id}/comments，多人房间广播 + 心跳 + 断线清理。

## 涉及文件
- `app/core/ws_manager.py`（ConnectionManager）
- `app/api/ws_comments.py`（WebSocket 路由）
- `app/main.py`（注册 ws 路由）
- `docs/lessons/14-websocket.md`
- `tests/test_14_websocket.py`

## 验收标准
- [ ] WS /ws/posts/{post_id}/comments 连接成功
- [ ] 客户端发 JSON 评论消息广播给同房间所有人
- [ ] 发送人也收到自己的消息
- [ ] 心跳 ping/pong 维持连接
- [ ] 断开后房间内其他人收到 leave 通知
- [ ] 不同 post_id 的房间不互通
- [ ] ConnectionManager 线程安全
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_ws_connect_success`：WS 连接成功
2. `test_ws_send_and_receive`：发送消息收到回执
3. `test_ws_broadcast_to_others`：A 发消息 B 能收到
4. `test_ws_sender_also_receives`：发送人也收到
5. `test_ws_leave_notification`：A 断开 B 收到 leave
6. `test_ws_json_protocol`：JSON 解析与回写
7. `test_ws_ping_pong_heartbeat`：心跳响应
8. `test_ws_room_isolation`：不同 post_id 不互通

## 实现要点
```python
# app/core/ws_manager.py
from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, room: str, ws: WebSocket):
        await ws.accept()
        self.rooms[room].add(ws)

    def disconnect(self, room: str, ws: WebSocket):
        self.rooms[room].discard(ws)

    async def broadcast(self, room: str, message: dict, exclude: WebSocket | None = None):
        dead = []
        for ws in self.rooms[room]:
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)

manager = ConnectionManager()

# app/api/ws_comments.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/posts/{post_id}/comments")
async def ws_comments(websocket: WebSocket, post_id: int):
    room = f"post:{post_id}"
    await manager.connect(room, websocket)
    await manager.broadcast(room, {"type": "join", "user": "..."}, exclude=websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            await manager.broadcast(room, {"type": "comment", **data})
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
        await manager.broadcast(room, {"type": "leave"})
```
- 测试用 `fastapi.testclient.TestClient` 的 `with client.websocket_connect(...) as ws`
- 注意 broadcast 时收集 dead 连接，避免无限增长

## 教学文档大纲
1. 【新手】WebSocket vs HTTP 轮询
2. 【新手】FastAPI WebSocket 基础
3. 【新手】accept / send_json / receive_json
4. 【进阶】ConnectionManager 与房间模型
5. 【进阶】心跳保活
6. 【进阶】断线重连（前端视角）
7. 【进阶】WebSocket 鉴权（query token / subprotocol）
8. 思考题：多 worker 部署时 WebSocket 怎么广播（Redis Pub/Sub）？
