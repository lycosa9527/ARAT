"""
验证码服务
使用captcha库生成图片验证码，使用自定义字体
"""

import uuid
import time
from typing import Dict
from io import BytesIO
import base64
from captcha.image import ImageCaptcha
from pathlib import Path

from config.logging_config import get_logger

logger = get_logger('app')
security_logger = get_logger('security')

# 验证码存储 (生产环境建议使用Redis)
_captcha_sessions: Dict[str, Dict] = {}

# 速率限制存储
_rate_limit_store: Dict[str, list] = {}

# 字体路径
FONT_PATH = Path(__file__).parent.parent / "static" / "fonts" / "inter-700.ttf"

def generate_captcha() -> Dict:
    """
    生成验证码
    
    Returns:
        {
            'captcha_id': session_id,
            'image': base64_encoded_image
        }
    """
    # 生成4位验证码
    import random
    import string
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    # 生成会话ID
    session_id = f"captcha_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    try:
        # 使用自定义字体生成验证码图片
        image = ImageCaptcha(
            width=200,
            height=80,
            fonts=[str(FONT_PATH)] if FONT_PATH.exists() else None
        )
        
        # 生成图片
        data = image.generate(code)
        
        # 转换为base64
        img_bytes = data.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # 存储验证码信息
        current_time = time.time()
        _captcha_sessions[session_id] = {
            "code": code,
            "expires": current_time + 120,  # 2 minutes
            "attempts": 0
        }
        
        # 清理过期的验证码
        cleanup_expired_captchas()
        
        logger.debug(f"Captcha generated | ID: {session_id}")
        
        return {
            "captcha_id": session_id,
            "image": f"data:image/png;base64,{img_base64}"
        }
    
    except Exception as e:
        logger.error(f"Failed to generate captcha: {e}")
        raise

def verify_captcha(captcha_id: str, user_code: str) -> bool:
    """
    验证验证码
    
    Args:
        captcha_id: 验证码会话ID
        user_code: 用户输入的验证码
    
    Returns:
        bool: 验证是否成功
    """
    session = _captcha_sessions.get(captcha_id)
    
    if not session:
        security_logger.warning(f"Captcha verification failed | ID not found: {captcha_id}")
        return False
    
    # 检查是否过期
    if time.time() > session['expires']:
        del _captcha_sessions[captcha_id]
        security_logger.warning(f"Captcha expired | ID: {captcha_id}")
        return False
    
    # 检查尝试次数 (最多3次)
    if session['attempts'] >= 3:
        del _captcha_sessions[captcha_id]
        security_logger.warning(f"Captcha max attempts exceeded | ID: {captcha_id}")
        return False
    
    # 增加尝试次数
    session['attempts'] += 1
    
    # 验证 (不区分大小写)
    if user_code.upper() == session['code'].upper():
        del _captcha_sessions[captcha_id]
        security_logger.info(f"Captcha verified successfully | ID: {captcha_id}")
        return True
    else:
        security_logger.warning(f"Captcha incorrect | ID: {captcha_id} | Attempts: {session['attempts']}")
        return False

def cleanup_expired_captchas():
    """清理过期的验证码会话"""
    current_time = time.time()
    expired_ids = [
        session_id for session_id, session in _captcha_sessions.items()
        if current_time > session['expires']
    ]
    
    for session_id in expired_ids:
        del _captcha_sessions[session_id]
    
    if expired_ids:
        logger.debug(f"Cleaned up {len(expired_ids)} expired captcha sessions")

def check_rate_limit(client_ip: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """
    检查速率限制
    
    Args:
        client_ip: 客户端IP
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口(秒)
    
    Returns:
        bool: 是否允许请求
    """
    current_time = time.time()
    
    # 获取该IP的请求记录
    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = []
    
    requests = _rate_limit_store[client_ip]
    
    # 清理过期的请求记录
    requests = [req_time for req_time in requests if current_time - req_time < window_seconds]
    _rate_limit_store[client_ip] = requests
    
    # 检查是否超过限制
    if len(requests) >= max_requests:
        security_logger.warning(f"Rate limit exceeded | IP: {client_ip} | Requests: {len(requests)}")
        return False
    
    # 添加当前请求
    requests.append(current_time)
    return True

