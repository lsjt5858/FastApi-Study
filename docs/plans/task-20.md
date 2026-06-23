# task-20: 综合实战：博客系统端到端

## 目标
把前 19 个知识点串成完整博客系统，跑端到端测试：注册→登录→发文章→上传封面→他人评论→WebSocket 直播→收藏→统计聚合→缓存命中→管理员删除→定时统计。

## 涉及文件
- `app/`（整合前面所有代码，按 task-17 的结构）
- `docs/lessons/20-blog-final.md`（架构总览 + 模块关系图 + checklist）
- `tests/test_20_blog_e2e.py`（端到端测试）
- `docs/architecture.md`（可选：架构图 + 表设计图）

## 验收标准
- [ ] 用户注册 → 登录 → 拿 JWT 全流程
- [ ] 登录后发文章（title 自动 strip + slug 生成 + tags 去重）
- [ ] 文章 404 走自定义异常体系
- [ ] 他人可评论，评论触发 WebSocket 广播
- [ ] 列表接口缓存命中（第二次走 redis）
- [ ] /stats/aggregate 异步聚合阅读/评论/点赞
- [ ] 管理员 scope 才能删除任意文章
- [ ] 8 条端到端测试全绿
- [ ] docs/lessons/20-blog-final.md 含架构图

## 测试点（至少 8 条端到端）
1. `test_e2e_register_then_login`：注册 → 登录拿 token
2. `test_e2e_create_post_with_auth`：带 token 发文章 201
3. `test_e2e_get_post_404_custom_error`：访问不存在文章返回自定义错误结构
4. `test_e2e_other_user_comments`：第二用户评论成功
5. `test_e2e_comment_triggers_websocket`：WS 连接后收到评论广播
6. `test_e2e_list_cache_hit_on_second_call`：第二次列表查询 DB 不被调用
7. `test_e2e_stats_aggregate`：/stats/aggregate 返回三个指标
8. `test_e2e_admin_can_delete_others_post`：管理员 scope 删除他人文章

## 实现要点
```python
# tests/test_20_blog_e2e.py
import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_e2e_register_then_login(client):
    # 1. 注册
    r = client.post("/auth/register", json={
        "username": "alice", "email": "alice@example.com",
        "password": "secret123"
    })
    assert r.status_code == 201
    # 2. 登录
    r = client.post("/auth/token", data={
        "username": "alice", "password": "secret123"
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

@pytest.mark.asyncio
async def test_e2e_create_post_with_auth(client):
    token = _login(client, "alice", "secret123")
    r = client.post(
        "/posts",
        json={"title": "  Hello World  ", "content": "...", "tags": ["PY", "py", "fastapi"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "hello-world"
    assert body["tags"] == ["py", "fastapi"]  # 去重 + 小写

# ... 其他 6 条
```
- 端到端测试模拟真实用户行为：注册→登录→操作
- 用 conftest.py 的 client fixture + test_db fixture 隔离
- WS 测试用 `with client.websocket_connect(...) as ws`

## 教学文档大纲（docs/lessons/20-blog-final.md）
1. 整体架构图（ASCII 或 mermaid）
2. 模块关系（router → service → crud → model → db）
3. 完整数据流（一个 HTTP 请求穿过中间件 → 依赖 → 路由 → 服务 → 缓存 → DB → 响应过滤）
4. 关键决策清单
   - 认证：JWT + bcrypt
   - 缓存：旁路 + 单飞
   - 异步：路由 async + 服务层 async
   - 错误：统一 BizError + handler
5. 性能 checklist（缓存命中率 / N+1 / async）
6. 安全 checklist（哈希 / secret / scope / CORS）
7. 可观测性 checklist（request_id / 日志 / metrics）
8. 进阶路线（消息队列 / 服务化 / k8s）
9. 全部 20 篇 lesson 链接索引

## 最终交付物
完成本任务后，整个项目交付：
- ✅ 20 篇教学文档（docs/lessons/）
- ✅ 1 个完整可运行的博客 API（app/）
- ✅ 160+ 条 pytest 测试（tests/）
- ✅ Docker 部署套件（Dockerfile + docker-compose.yml）
- ✅ 完整项目结构范例
