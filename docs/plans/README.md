# 教学内容总体规划（博客渐进式）

## 故事线

20 个 task **共同构建同一个博客系统 API**。task-1 搭骨架，task-2~16 每个 task 引入一个 FastAPI 知识点扩展功能，task-17~19 完成工程化（结构/缓存/部署），task-20 端到端验收。最终交付一个完整可运行的博客系统。

## 渐进式构建路线图

```
task-1   项目骨架 + Hello              app/main.py, GET /posts/{id}
task-2   路径/查询参数 + 枚举           GET /posts?limit&offset&status
task-3   请求体 + Pydantic             POST /posts (PostCreate)
task-4   Header/Cookie/Form/UploadFile POST /posts/{id}/cover
task-5   response_model + 状态码       PostOut 过滤敏感字段
task-6   依赖注入 Depends              分页/会话/当前作者依赖
task-7   Pydantic 校验器               slug 自动生成、tags 去重
task-8   async/await                  GET /stats/aggregate 并发聚合
task-9   中间件                        耗时/CORS/请求ID
task-10  异常处理                      PostNotFound/DuplicateSlug/BizError
task-11  SQLAlchemy 数据库             内存 POSTS → 真实 DB
task-12  OAuth2 + JWT                  作者注册/登录/权限
task-13  BackgroundTasks + APScheduler 发表后邮件+定时统计
task-14  WebSocket                     文章直播评论
task-15  OpenAPI 定制                  tags/examples/deprecated/v1+v2
task-16  测试体系                      conftest + fixture + override
task-17  项目结构                      routers/core/crud/services 重组
task-18  Redis 缓存                    文章列表缓存 + 击穿防护
task-19  Docker 部署                   Dockerfile + compose + Gunicorn
task-20  综合端到端                    完整博客系统验收
```

## 渐进式构建原则（强制）

1. **不要推倒重来**：每个 task 必须复用前一个 task 的代码骨架（`app/main.py`、`schemas/`、`tests/conftest.py` 等），只新增/修改与本知识点直接相关的部分
2. **小步快跑**：每个 task 只引入 1 个新概念，配套 1 篇文档 + ≥8 条测试
3. **真实可跑**：所有代码用最新稳定版（FastAPI 0.115+ / Pydantic 2.x / SQLAlchemy 2.x），测试全绿

## 每个 task 的产出标准

| 产出 | 路径 | 要求 |
|---|---|---|
| 教学文档 | `docs/lessons/NN-<slug>.md` | 含【新手】/【进阶】分层标注，案例 → 运行结果 → 原理 → 思考题 |
| 可运行源码 | `app/` 下扩展 | 复用前 task 骨架，只增量修改 |
| 测试 | `tests/test_NN_<slug>.py` | 至少 8 条 pytest，全绿 |

## 使用方式

1. 任务清单见根目录 `progress.json`（含 goal/conventions/tasks 三段）
2. 每个任务的简短计划写在 `progress.json` 的 `plan` 字段里
3. 详细计划可参照 `task-1.example.md` 写到 `docs/plans/task-N.md`（可选）
4. 运行 `/goal 完成所有 20 个 FastAPI 教学案例` 启动长跑循环

## 最终交付物

完成全部 20 个 task 后，你将获得：
- 一个**完整可运行的博客系统 API**（用户/文章/评论/标签/统计）
- 20 篇教学文档（按难度递增）
- 160+ 条 pytest 测试
- Docker 部署套件
- 完整的项目结构范例
