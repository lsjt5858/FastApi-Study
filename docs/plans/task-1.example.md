# task-1: 项目骨架与第一个 FastAPI 应用

> 这是示例模板，展示 docs/plans/task-N.md 应该怎么写。
> 本项目所有 task 的 plan 字段已经在 progress.json 中预填，
> 直接照 plan 执行即可，也可以把更详细的计划落到本目录的 task-N.md 里。
>
> **本项目特色**：20 个 task 共同构建**同一个博客系统**，每个 task 在前一个的基础上扩展。

## 目标
让从未接触过 FastAPI 的学习者在 5 分钟内启动博客项目骨架，理解 FastAPI = 路由 + Pydantic + ASGI，能访问自动文档 /docs。

## 验收标准
- [ ] 教学文档 docs/lessons/01-hello.md 写完，含【新手】/【进阶】分层标注
- [ ] `app/__init__.py` + `app/main.py` 可用 `uvicorn app.main:app --reload` 启动
- [ ] GET / 返回 `{name: "Blog API", version: "0.1.0", docs_url: "/docs"}`
- [ ] GET /health 返回 `{status: "ok"}`
- [ ] GET /posts/{post_id} 从内存 POSTS 列表返回单篇，不存在返回 404
- [ ] /docs 自动文档可访问
- [ ] tests/test_01_hello.py 至少 8 条测试全部通过
- [ ] 后续 task 必须复用 app/main.py 这个骨架（渐进式原则）

## 测试点（至少 8 条）
1. GET / 返回 name 字段为 "Blog API"
2. GET /health 返回 status=ok，200
3. GET /posts/1 返回第一篇文章
4. GET /posts/9999 返回 404
5. GET /docs 返回 200 且 text/html
6. GET /openapi.json 包含 paths 字段
7. 所有 JSON 响应 Content-Type=application/json
8. 并发 50 次请求根路径都稳定返回 200

## 实现要点
- 目录结构：`app/__init__.py` + `app/main.py`（后续 task 直接扩展这个包）
- 用 fastapi.testclient.TestClient 写测试，避免依赖外部进程
- 内存 POSTS 用模块级 list 模拟，task-11 再换成 SQLAlchemy
- 教学文档采用「案例 → 运行结果 → 为什么 → 思考题」四段式
- 在文档顶部加难度标签：【新手】/【进阶】
- README 顶部加完整博客路线图，链到 docs/lessons/
