# task-12: 认证与授权 OAuth2 + JWT

## 目标
为博客加作者认证：注册/登录（OAuth2PasswordBearer），JWT 签发/校验（PyJWT），密码哈希（passlib bcrypt），scope/owner 权限。

## 涉及文件
- `app/core/security.py`（哈希 + JWT 工具）
- `app/core/config.py`（Settings.SECRET_KEY）
- `app/api/auth.py`（register/token 路由）
- `app/core/deps.py`（升级 get_current_author 走 JWT）
- `app/main.py`（注册 auth router）
- `docs/lessons/12-auth.md`
- `tests/test_12_auth.py`

## 验收标准
- [ ] POST /auth/register 注册新作者（密码哈希）
- [ ] POST /auth/token OAuth2PasswordBearer 登录返回 access_token
- [ ] get_current_author 依赖解析 JWT 拿 author
- [ ] GET /me 返回当前作者信息
- [ ] DELETE /posts/{id} 校验只能删自己文章
- [ ] 重复注册 409
- [ ] 密码错误 401 / token 过期 401 / 伪造 token 401
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_register_success`：注册 201 + 返回 AuthorOut
2. `test_register_duplicate_409`：重复 username 409
3. `test_login_returns_token`：登录 200 + access_token
4. `test_login_wrong_password_401`：密码错误 401
5. `test_me_without_token_401`：无 token 401
6. `test_me_with_expired_token_401`：过期 token 401
7. `test_me_with_forged_token_401`：伪造 token 401
8. `test_delete_others_post_403`：删他人文章 403

## 实现要点
```python
# app/core/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str: return pwd_ctx.hash(p)
def verify_password(p: str, hashed: str) -> bool: return pwd_ctx.verify(p, hashed)

def create_access_token(subject: str, expires_minutes: int = 60, secret: str = "...") -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(401, "Invalid token") from e

# app/api/auth.py
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=AuthorOut, status_code=201)
async def register(payload: AuthorCreate, db = Depends(get_db)):
    existing = await crud_authors.get_by_username(db, payload.username)
    if existing:
        raise DuplicateSlug("Username taken")
    author = await crud_authors.create(db, payload)
    return author

@router.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    author = await crud_authors.authenticate(db, form.username, form.password)
    if not author:
        raise HTTPException(401, "Bad credentials")
    token = create_access_token(str(author.id), secret=settings.SECRET_KEY)
    return {"access_token": token, "token_type": "bearer"}
```
- `OAuth2PasswordBearer(tokenUrl="/auth/token")` 让 /docs 出现 Authorize 按钮
- 密码必须哈希，禁止明文存
- JWT 默认放 Authorization: Bearer <token>

## 教学文档大纲
1. 【新手】认证 vs 授权 vs 鉴权
2. 【新手】密码哈希为什么用 bcrypt
3. 【新手】JWT 结构（header.payload.signature）
4. 【新手】OAuth2PasswordBearer
5. 【进阶】scope 与细粒度权限
6. 【进阶】refresh token 与 access token
7. 【进阶】token 撤销（黑名单）
8. 思考题：JWT 与 session 的取舍？
