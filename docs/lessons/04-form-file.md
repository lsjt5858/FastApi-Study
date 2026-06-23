# 第 4 课 · Header / Cookie / Form / 文件上传

> 难度：【新手】为主，含【进阶】延伸。
>
> 学完本节，你能为接口同时接收文件、表单、Header、Cookie 四种"非 JSON"输入，并安全地处理大文件上传。

---

## 4.1 【新手】为什么上传文件不能用 JSON

JSON 不能直接装二进制。如果要传一张图片，要么：
1. **Base64 编码**塞进 JSON —— 体积膨胀 33%，慢
2. **multipart/form-data** —— HTTP 原生的多部分表单，每段可以是文本或二进制 ✅

所以 FastAPI 的 `UploadFile` / `Form` 都基于 `multipart/form-data`。

```
POST /posts/1/cover HTTP/1.1
Content-Type: multipart/form-data; boundary=----xxx

------xxx
Content-Disposition: form-data; name="file"; filename="cover.png"
Content-Type: image/png

<binary>
------xxx
Content-Disposition: form-data; name="alt_text"

A cover
------xxx--
```

---

## 4.2 【新手】UploadFile vs bytes

| 写法 | 行为 |
|---|---|
| `file: UploadFile` | 流式对象，可分块 `await file.read(N)`，适合大文件 |
| `file: bytes = File(...)` | 整个文件一次性读到内存，适合小文件 |

本课用 `UploadFile`，因为它能**边读边校验大小**——超过 5MB 时立刻抛 413，避免被恶意大文件 OOM。

---

## 4.3 【新手】Form 与 Query 的区别

```python
# 这是查询参数（出现在 URL ?q=...）
def f(q: str = Query(...)): ...

# 这是 Form 字段（出现在 multipart 请求体里）
def f(q: Annotated[str, Form(...)]): ...
```

虽然函数签名相似，但 FastAPI 看你用了 `Form(...)` 来区分。

---

## 4.4 【新手】Header 参数的"小写规则"

```python
async def upload(
    x_upload_token: Annotated[str | None, Header()] = None,
):
    ...
```

HTTP Header 名大小写不敏感（`X-Upload-Token` ≡ `x-upload-token`）。
FastAPI 把 Python 参数名里的下划线 `_` 自动转成 `-`，并**不区分大小写**地匹配。

所以 `x_upload_token` 能匹配请求头里的 `X-Upload-Token`、`x-upload-token`、`X-UPLOAD-TOKEN` 任意写法。

---

## 4.5 【进阶】Cookie 的安全性

```python
upload_session_id: Annotated[str | None, Cookie()] = None
```

Cookie 自动从请求的 `Cookie:` 头里解析。生产环境设置 Cookie 时建议：

| 属性 | 作用 |
|---|---|
| `HttpOnly` | JS 无法读取，防 XSS 偷 token |
| `Secure` | 只走 HTTPS |
| `SameSite=Lax/Strict` | 防 CSRF |

FastAPI 设置 Cookie 用 `response.set_cookie(key=..., httponly=True, secure=True, samesite="lax")`。

---

## 4.6 【进阶】分块读取大文件

```python
async def validate_and_read(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Unsupported media type")
    total = 0
    chunks = []
    while chunk := await file.read(64 * 1024):  # 64KB / chunk
        total += len(chunk)
        if total > MAX_SIZE:
            raise HTTPException(413, "File too large")
        chunks.append(chunk)
    return b"".join(chunks)
```

关键点：
- **海象运算符 `:=`** 在 while 条件里既赋值又判断（Python 3.8+）
- 64KB chunk 是性能/内存的折中（太小开销大，太大失去流式意义）
- 超 MAX_SIZE 立刻抛错，**不再继续读**，节省带宽

---

## 4.7 【进阶】多文件上传

```python
async def upload_covers(
    post_id: int,
    files: Annotated[list[UploadFile], File()],
):
    for f in files:
        await validate_and_read(f)
```

`list[UploadFile]` 让 FastAPI 接受**同名字段**的多个文件（前端 `<input type="file" multiple>` 或多次 append 同 key）。

---

## 4.8 思考题

1. 如果想限制"每个用户每小时只能上传 10 个文件"，应该在哪一层做？
2. 上传文件后立刻返回 vs 异步处理（背景任务转码），各有什么取舍？
3. 上传 10GB 大文件时，分块读取还够用吗？（提示：seek + 流式落盘 + presigned URL）

---

## 4.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/services/__init__.py` | 服务层包初始化 |
| `app/services/upload.py` | `validate_and_read`：类型白名单 + 流式大小校验 |
| `app/main.py` | 新增 `POST /posts/{id}/cover`（单文件）+ `/covers`（多文件） |
| `tests/test_04_form_file.py` | 8 条测试 |
| `docs/lessons/04-form-file.md` | 本文 |

---

## 4.10 下一节预告

第 5 课我们引入 **响应模型 response_model**：定义 `PostOut` 过滤敏感字段，演示 `response_model_exclude` / `_include` / 状态码 / `JSONResponse`。
