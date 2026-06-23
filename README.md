# Python FastAPI 从入门到精通（博客渐进式实战）

一套通过**构建同一个博客系统**完整讲解 FastAPI 的教学项目。20 个 task 渐进式扩展：从 task-1 的最小骨架，到 task-20 的完整博客 API。

## 学习路线图

```
入门基础   task 1-4   骨架 / 参数 / 请求体 / 上传
核心进阶   task 5-8   响应模型 / 依赖注入 / 校验器 / 异步
工程化     task 9-12  中间件 / 异常 / 数据库 / 认证
高级特性   task 13-16 后台任务 / WebSocket / OpenAPI / 测试
项目实战   task 17-20 项目结构 / Redis / Docker / 综合实战
```

每个 task：1 篇教学文档 + 增量源码 + ≥8 条测试。20 个 task 共同构建同一个博客系统。

## 环境准备

```bash
# Python 3.10+
python -m venv .venv
source .venv/bin/activate
pip install "fastapi>=0.115" "uvicorn[standard]" "pydantic>=2" "sqlalchemy>=2" \
            "aiosqlite" "python-jose[cryptography]" "passlib[bcrypt]" \
            "python-multipart" "redis" "apscheduler" \
            "pytest" "httpx" "pytest-asyncio" "pytest-cov"
```

## 如何使用

1. 按顺序阅读 `docs/lessons/NN-xxx.md`
2. 启动应用：`uvicorn app.main:app --reload`
3. 访问自动文档：http://127.0.0.1:8000/docs
4. 跑测试：`pytest -x`
5. 看进度：`python check_progress.py`

## 项目结构（最终形态）

```
FastAPI/
├── app/
│   ├── api/routers/{posts,users,comments,auth}.py
│   ├── core/{config,security,deps}.py
│   ├── crud/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── docs/lessons/         # 20 篇教学文档
├── docs/plans/           # 任务计划
├── tests/                # 20 套测试（160+ 条用例）
├── Dockerfile
├── docker-compose.yml
├── progress.json
├── check_progress.py
└── README.md
```

## 进度

执行 `python check_progress.py` 查看实时进度。完整任务清单见 `progress.json`。
