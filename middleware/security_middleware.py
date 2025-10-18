"""
安全中间件
基本的安全头和CORS处理
"""

from fastapi import Request
from fastapi.responses import Response

async def add_security_headers(request: Request, call_next):
    """添加安全响应头"""
    response = await call_next(request)
    
    # 基本安全头
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    return response

