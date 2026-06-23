# 第 12 课 · 认证与授权 OAuth2 + JWT

> 难度：【进阶】为主。
>
> 学完本节，你能用 OAuth2PasswordBearer 实现登录、用 JWT 签发/校验 access token、用 passlib bcrypt 哈希密码、用 `Depends(get_current_author)` 守卫需要登录的路由。

---

## 12.1 【新手】认证 vs 授权

| 概念 | 中文 | 回答的问题 |
|---|---|---|
| Authentication | 认证 | 你是谁？ |
| Authorization | 授权 | 你能做什么？ |
| 鉴权 | 一起做 | 你是谁 + 能不能做 |

本课先解决"认证"（你是谁）。授权（scope/owner 检查）下节再扩展。

---

## 12.2 【新手】密码哈希为什么用 bcrypt

**禁止明文存密码**。一旦 DB 泄露，所有用户密码就曝光。哈希是把密码变成不可逆字符串：

```python
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

hashed = pwd_ctx.hash("mypass123")     # 存 DB
ok = pwd_ctx.verify("mypass123", hashed)  # True
ok = pwd_ctx.verify("wrongpass", hashed)  # False
```

bcrypt 的特点：
- **慢**（约 200ms/次）：暴力破解成本高
- **自动 salt**：相同密码哈希结果不同，防彩虹表
- **可调 cost**：硬件升级后可以调慢

---

## 12.3 【新手】JWT 结构

JWT（JSON Web Token）= `header.payload.signature`：

- `header`：`{"alg": "HS256", "typ": "JWT"}`
- `payload`：业务数据，如 `{"sub": "1", "exp": 1730000000}`
- `signature`：`HMAC-SHA256(header + "." + payload, SECRET_KEY)`

三段都用 base64url 编码，用 `.` 连接：

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzMwMDAwMDAwfQ.signature
```

服务端拿到 token 后：
1. 用同样的 SECRET_KEY 重算签名
2. 跟 token 里的 signature 比对
3. 验证 exp 没过期

只要 SECRET_KEY 不泄露，token 就不能伪造。

---

## 12.4 【新手】OAuth2PasswordBearer

FastAPI 提供的 OAuth2 实现，自动从 `Authorization: Bearer <token>` 取 token：

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

@app.get("/me")
async def me(token: Annotated[str, Depends(oauth2_scheme)]):
    # token 已自动从 header 抽出
    ...
```

`tokenUrl` 让 /docs 出现绿色 "Authorize" 按钮，方便手动测试。

---

## 12.5 【进阶】完整 JWT 工具

```python
# app/core/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

def create_access_token(subject: str, expires_minutes: int = 60, secret: str = "") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(401, "Invalid or expired token") from e
```

**关键点**：
- `exp` 用 UTC 时间戳（不要用本地时间）
- `algorithms` 必须传列表，否则 jose 报错（安全：防止 alg=none 攻击）
- 任何 JWT 错误都转 401

---

## 12.6 【进阶】依赖链：oauth2_scheme -> decode_token -> DB

```python
async def get_current_jwt_author(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Author:
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token, settings.SECRET_KEY)
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(401, "Invalid token payload")
    author = await get_author_by_id(db, int(sub))
    if author is None:
        raise HTTPException(401, "Author not found")
    return author

@app.get("/me")
async def me(author: Annotated[Author, Depends(get_current_jwt_author)]):
    return author
```

错误码细分：
- 没 token → 401 "Not authenticated"
- token 签名错/过期 → 401 "Invalid or expired token"
- payload 里没 sub → 401 "Invalid token payload"
- sub 对应的 author 不存在（用户被删）→ 401 "Author not found"

---

## 12.7 【进阶】登录端点的 form 字段

OAuth2 标准要求登录端点接收 form-urlencoded：

```python
@router.post("/token")
async def login(
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
):
    ...
```

而不是 JSON。原因：浏览器原生表单只能发 form-urlencoded；OAuth2 客户端库都按这个标准来。

---

## 12.8 【进阶】refresh token（不在本课代码）

access token 短期（1 小时），refresh token 长期（30 天）。客户端用 access 调 API；过期后用 refresh 换新的 access。

设计：
- `/auth/token` 返回 `access_token` + `refresh_token`
- `/auth/refresh` 接 refresh_token，发新 access_token
- refresh_token 通常存 Redis 黑名单（撤销）

---

## 12.9 思考题

1. JWT 与 session（cookie + 服务端存）有什么区别？哪个更适合微服务？
2. SECRET_KEY 泄露了怎么办？（提示：rotate key + 客户端强制重登）
3. 为什么 access_token 不能存敏感数据（如手机号）？

---

## 12.10 本节交付物

| 文件 | 作用 |
|---|---|
| `app/core/security.py` | hash_password / verify_password / create_access_token / decode_token |
| `app/core/config.py` | Settings（SECRET_KEY / ACCESS_TOKEN_EXPIRE_MINUTES） |
| `app/crud/authors.py` | Author CRUD + authenticate |
| `app/api/auth.py` | /auth/register / /auth/token / get_current_jwt_author 依赖 |
| `app/main.py` | 挂载 auth_router + 加 /me 路由 |
| `app/models/__init__.py` | Author 加 hashed_password 字段 |
| `app/schemas/author.py` | AuthorCreate 加 password 字段 |
| `tests/test_12_auth.py` | 8 条测试 |
| `docs/lessons/12-auth.md` | 本文 |

---

## 12.11 下一节预告

第 13 课我们引入 **BackgroundTasks 与定时任务**：POST /posts 创建成功后异步发邮件，APScheduler 启动时注册定时任务统计热门文章。
