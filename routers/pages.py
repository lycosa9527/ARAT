"""
页面路由
处理HTML页面请求
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()

# 模板目录
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request):
    """Demo页面 - 显示答案的开发模式"""
    return templates.TemplateResponse("demo.html", {"request": request})

