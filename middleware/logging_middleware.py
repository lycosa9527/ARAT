"""
日志中间件
记录所有API请求和响应
"""

import time
import json
from fastapi import Request
from config.logging_config import get_logger

access_logger = get_logger('access')

async def log_requests(request: Request, call_next):
    """记录所有API请求"""
    start_time = time.time()
    
    # 记录请求
    request_info = {
        'method': request.method,
        'path': str(request.url.path),
        'client_ip': request.client.host if request.client else 'unknown',
        'user_agent': request.headers.get('user-agent', 'unknown')
    }
    
    # 处理请求
    response = await call_next(request)
    
    # 记录响应
    duration = time.time() - start_time
    response_info = {
        **request_info,
        'status_code': response.status_code,
        'duration_ms': round(duration * 1000, 2)
    }
    
    access_logger.info(json.dumps(response_info))
    
    return response

