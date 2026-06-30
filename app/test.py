# 题目背景：
# 你正在开发一个简单的图书管理系统，需要实现一个 API 来管理图书信息。
# 训练目标：
# 熟练掌握 FastAPI 的基本路由、Path 参数、Request Body 以及响应模型的使用。
# 难度等级：基础巩固
# 涉及知识点：
# FastAPI 路由、Path 参数、Request Body、Pydantic 模型、响应模型
# 接口需求：
# 实现一个 GET 请求的路由，路径为/books/{book_id}，用于获取指定图书的信息。
# 实现一个 POST 请求的路由，路径为/books，用于创建一本新的图书。
# 定义图书信息的 Pydantic 模型，包含title（书名）、author（作者）、isbn（ISBN 号）等字段。
# 对于 GET 请求，返回指定图书的详细信息；对于 POST 请求，返回创建成功的图书信息。
# 输入输出示例：
# GET 请求/books/1，假设图书 ID 为 1 的图书信息为{"title": "Python Crash Course", "author": "Eric Matthes", "isbn": "9781593279288"}，则返回该图书信息。
# POST 请求/books，请求体为{"title": "FastAPI实战", "author": "张三", "isbn": "9781234567890"}，返回创建成功的图书信息{"title": "FastAPI实战", "author": "张三", "isbn": "9781234567890"}。

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 1. 初始化应用
app = FastAPI(title="图书管理系统")

# 2. 定义Pydantic图书模型（请求体 + 响应模型通用）
class Book(BaseModel):
    title: str
    author: str
    isbn: str

# 3. 模拟内存数据库
books_db = {
    1: Book(title="Python Crash Course", author="Eric Matthes", isbn="9781593279288")
}
next_id = 2

# 4. GET接口：根据book_id获取图书，路径参数
@app.get("/books/{book_id}", response_model=Book)
def get_book(book_id: int):
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="图书不存在")
    return books_db[book_id]

# 5. POST接口：创建图书，接收Request Body
@app.post("/books", response_model=Book)
def create_book(book: Book):
    global next_id
    books_db[next_id] = book
    next_id += 1
    return book


