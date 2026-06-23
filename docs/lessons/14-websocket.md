# 第 14 课 · WebSocket 实时通信

> 难度：【进阶】为主。
>
> 学完本节，你能用 FastAPI 的 `@app.websocket` 建立全双工长连接、用 ConnectionManager 管理多房间、做心跳保活、断线清理。

---

## 14.1 【新手】WebSocket vs HTTP 轮询

| 场景 | HTTP 轮询 | WebSocket |
|---|---|---|
| 客户端要"实时"看新评论 | 每 2s GET 一次 | 一次握手，服务器推 |
| 服务端推送 | 做不到（必须客户端先问） | 服务端随时发 |
| 协议开销 | 每次都带 header | 帧头 2~14 字节 |
| 实现复杂度 | 简单 | 中等 |

聊天室、协同编辑、推送通知、行情、直播弹幕都适合 WS。

---

## 14.2 【新手】FastAPI WebSocket 基础

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/posts/{post_id}/comments")
async def ws_comments(websocket: WebSocket, post_id: int):
    await websocket.accept()      # 握手
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"echo": data})
    except WebSocketDisconnect:
        ...
```

注意：
- 路径参数解析和 HTTP 路由一样（`post_id: int`）
- 必须先 `await websocket.accept()` 才能收发
- `WebSocketDisconnect` 是正常关闭，要处理（不然日志全是 traceback）

---

## 14.3 【新手】accept / send_json / receive_json

```python
await websocket.accept()                              # 握手
await websocket.send_json({"type": "welcome"})        # 发 JSON
await websocket.send_text("hello")                    # 发字符串
data = await websocket.receive_json()                 # 收 JSON
text = await websocket.receive_text()                 # 收字符串
await websocket.close(code=1000)                      # 主动关
```

底层都是 `send_bytes` / `receive_bytes` 的封装。

---

## 14.4 【进阶】ConnectionManager 与房间模型

```python
class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms[room].add(ws)

    def disconnect(self, room: str, ws: WebSocket) -> None:
        self.rooms[room].discard(ws)

    async def broadcast(self, room: str, message: dict) -> None:
        dead = []
        for ws in self.rooms[room]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)
```

**关键点**：broadcast 时一定要 try/except 收集 dead 连接，否则断开的 ws 永远留在 set 里，下次广播还会再抛。

---

## 14.5 【进阶】心跳保活

中间件 / 反向代理（nginx）默认会断开 60s 不活跃的连接。客户端定时发 ping，服务端回 pong：

```python
data = await websocket.receive_json()
if data.get("type") == "ping":
    await websocket.send_json({"type": "pong"})
    continue
```

通常 30s 一次心跳；连续 3 次 pong 没回来 → 客户端重连。

---

## 14.6 【进阶】断线重连（前端视角）

浏览器原生 WebSocket 没有自动重连，得自己写：

```javascript
function connect() {
  const ws = new WebSocket(url);
  ws.onclose = () => {
    setTimeout(connect, 2000);  // 2s 后重连
  };
  ws.onmessage = (e) => { /* render */ };
}
connect();
```

加上指数退避（1s → 2s → 4s → max 30s）更稳。

---

## 14.7 【进阶】WebSocket 鉴权

WebSocket 不能像 HTTP 那样塞 Authorization 头（浏览器 API 不支持），通常有两种方式：

1. **query 参数**：`ws://x/y?token=xxx`，服务端在 `websocket.query_params` 取
2. **subprotocol**：`new WebSocket(url, ["bearer", token])`，服务端在 `websocket.headers["sec-websocket-protocol"]` 取

```python
@router.websocket("/ws/...")
async def ws_handler(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token or not verify_jwt(token):
        await websocket.close(code=4401)  # 自定义 close code
        return
    await websocket.accept()
```

---

## 14.8 思考题

1. uvicorn --workers 4 时，WS 连接分布在不同 worker，怎么跨 worker 广播？（提示：Redis Pub/Sub）
2. broadcast 是 `await ws.send_json(...)` 串行的，房间 1000 人会不会慢？怎么并发？（提示：`asyncio.gather`）
3. WebSocket 的 close code 1000/1006/1011 分别表示什么？

---

## 14.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/core/ws_manager.py` | ConnectionManager + 全局 manager |
| `app/api/ws_comments.py` | /ws/posts/{id}/comments 路由 + ping/pong |
| `app/main.py` | include ws_router |
| `tests/test_14_websocket.py` | 8 条测试 |
| `docs/lessons/14-websocket.md` | 本文 |

---

## 14.10 下一节预告

第 15 课我们引入 **OpenAPI 自定义**：tags 分组、response 多状态码示例、securityscheme 配置（让 /docs 出现登录按钮）。
