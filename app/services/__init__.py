"""博客项目的服务层。

服务层封装"与外部世界打交道的逻辑"，例如：
- upload.py：文件保存与校验（task-4）
- email.py：发送邮件（task-13）
- cache.py：Redis 缓存（task-18）

路由层只做"接收 HTTP / 调用 service / 返回响应"，业务逻辑放在 service。
"""
