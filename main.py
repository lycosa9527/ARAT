"""
ARAT - 字词接龙游戏
主应用入口

Author: lyc9527
Team: MTEL Team from Educational Technology, Beijing Normal University
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config.settings import config
from config.logging_config import init_logging, get_logger
from config.database import init_db
from routers import api, pages
from middleware.logging_middleware import log_requests
from middleware.security_middleware import add_security_headers
from services.game_service import game_service

# 初始化日志系统
init_logging()
logger = get_logger('app')

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的处理"""
    # 启动时
    logger.info("=" * 80)
    logger.info("ARAT Application Starting...")
    logger.info(f"Version: {config.VERSION}")
    logger.info(f"Environment: {'Development' if config.DEBUG else 'Production'}")
    logger.info(f"Port: {config.PORT}")
    logger.info("=" * 80)
    
    # 验证配置
    if not config.validate_config():
        logger.error("Configuration validation failed!")
    
    # 初始化数据库
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # 启动游戏服务的清理任务
    try:
        await game_service.start_cleanup_task()
        logger.info("Game service cleanup task started")
    except Exception as e:
        logger.error(f"Failed to start cleanup task: {e}")
    
    logger.info("Application startup complete")
    
    yield  # 应用运行期间
    
    # 关闭时
    logger.info("Application shutting down...")

# 创建FastAPI应用
app = FastAPI(
    title="ARAT - 字词接龙游戏",
    description="Chinese Word Bridge Game for K12 Education",
    version=config.VERSION,
    lifespan=lifespan
)

# CORS中间件 (开发环境允许所有来源)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自定义中间件
app.middleware("http")(log_requests)
app.middleware("http")(add_security_headers)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 路由
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(pages.router, tags=["Pages"])

# 根路径健康检查
@app.get("/health")
async def root_health():
    """根路径健康检查"""
    return {
        "status": "healthy",
        "service": "ARAT",
        "version": config.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Uvicorn server on {config.HOST}:{config.PORT}")
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info"
    )

