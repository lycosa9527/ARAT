"""
专业日志系统配置
参考: MindGraph logging system
功能:
- 多级日志输出 (Console + File)
- 日志轮转 (按大小和时间)
- 结构化日志
- 性能监控
- 安全审计
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime
import json
import time
import functools

# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
DETAILED_FORMAT = logging.Formatter(
    fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

SIMPLE_FORMAT = logging.Formatter(
    fmt='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

JSON_FORMAT = logging.Formatter(
    fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "function": "%(funcName)s", "line": %(lineno)d}',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        # 格式化消息
        result = super().format(record)
        
        # 重置levelname (避免影响其他handler)
        record.levelname = levelname
        
        return result

def setup_logger(
    name: str,
    log_file: str = None,
    level: int = logging.INFO,
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    json_format: bool = False
) -> logging.Logger:
    """
    创建并配置专业日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件名（相对于logs/目录）
        level: 日志级别
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        json_format: 是否使用JSON格式
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # 清除已有的handler
    
    # 控制台Handler (彩色输出)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        # 使用彩色格式化器
        colored_formatter = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(colored_formatter)
        logger.addHandler(console_handler)
    
    # 文件Handler (轮转)
    if file_output and log_file:
        log_path = LOG_DIR / log_file
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        # 选择格式
        if json_format:
            file_handler.setFormatter(JSON_FORMAT)
        else:
            file_handler.setFormatter(DETAILED_FORMAT)
        
        logger.addHandler(file_handler)
    
    return logger

# 全局日志记录器字典
_loggers = {}

def init_logging():
    """
    初始化所有日志记录器
    参考MindGraph的日志架构
    """
    global _loggers
    
    if _loggers:
        return  # 已初始化
    
    # 1. 主应用日志 (app.log)
    app_logger = setup_logger(
        name='app',
        log_file='app.log',
        level=logging.INFO,
        console_output=True,
        file_output=True
    )
    _loggers['app'] = app_logger
    app_logger.info("=" * 80)
    app_logger.info(f"ARAT Application Started at {datetime.now()}")
    app_logger.info("=" * 80)
    
    # 2. 错误日志 (error.log) - 只记录ERROR及以上
    error_logger = setup_logger(
        name='error',
        log_file='error.log',
        level=logging.ERROR,
        console_output=False,
        file_output=True
    )
    _loggers['error'] = error_logger
    
    # 3. LLM调用日志 (llm.log) - 记录所有LLM请求
    llm_logger = setup_logger(
        name='llm',
        log_file='llm.log',
        level=logging.DEBUG,
        console_output=False,
        file_output=True,
        json_format=True  # LLM日志使用JSON格式便于分析
    )
    _loggers['llm'] = llm_logger
    
    # 4. 安全日志 (security.log) - 验证码、限流、反作弊
    security_logger = setup_logger(
        name='security',
        log_file='security.log',
        level=logging.INFO,
        console_output=False,
        file_output=True
    )
    _loggers['security'] = security_logger
    
    # 5. API访问日志 (access.log)
    access_logger = setup_logger(
        name='access',
        log_file='access.log',
        level=logging.INFO,
        console_output=False,
        file_output=True,
        json_format=True  # API访问日志使用JSON便于统计
    )
    _loggers['access'] = access_logger
    
    # 6. 性能监控日志 (performance.log)
    perf_logger = setup_logger(
        name='performance',
        log_file='performance.log',
        level=logging.INFO,
        console_output=False,
        file_output=True,
        json_format=True
    )
    _loggers['performance'] = perf_logger
    
    # 7. 数据库日志 (database.log)
    db_logger = setup_logger(
        name='database',
        log_file='database.log',
        level=logging.INFO,
        console_output=False,
        file_output=True
    )
    _loggers['database'] = db_logger
    
    app_logger.info("Logging system initialized with 7 log files")

def get_logger(name: str = 'app') -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称 (app, error, llm, security, access, performance, database)
    
    Returns:
        日志记录器
    """
    if not _loggers:
        init_logging()
    
    return _loggers.get(name, _loggers['app'])

# Decorators for performance monitoring
def log_performance(logger_name: str = 'performance'):
    """
    性能监控装饰器
    记录函数执行时间
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            logger = get_logger(logger_name)
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"{func.__name__} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            logger = get_logger(logger_name)
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"{func.__name__} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
                raise
        
        # 检查是否为异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def log_llm_call(model: str = "unknown"):
    """
    LLM调用监控装饰器
    记录LLM API调用详情
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            llm_logger = get_logger('llm')
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                llm_logger.info(f"LLM call | model={model} | function={func.__name__} | duration={duration:.3f}s | status=success")
                return result
            except Exception as e:
                duration = time.time() - start_time
                llm_logger.error(f"LLM call | model={model} | function={func.__name__} | duration={duration:.3f}s | status=error | error={str(e)}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            llm_logger = get_logger('llm')
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                llm_logger.info(f"LLM call | model={model} | function={func.__name__} | duration={duration:.3f}s | status=success")
                return result
            except Exception as e:
                duration = time.time() - start_time
                llm_logger.error(f"LLM call | model={model} | function={func.__name__} | duration={duration:.3f}s | status=error | error={str(e)}")
                raise
        
        # 检查是否为异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

