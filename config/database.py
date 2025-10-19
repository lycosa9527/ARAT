"""
数据库配置
使用SQLAlchemy + SQLite
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

# Base类
Base = declarative_base()

# 数据模型 - 简化计分系统 (会话级别记录)
class GameRecord(Base):
    """游戏记录表 - 记录每次游戏会话的统计"""
    __tablename__ = "game_records"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)  # 游戏会话ID
    player_name = Column(String, index=True)  # 玩家名 (来自localStorage，无需注册)
    school_name = Column(String, nullable=True, index=True)  # 学校名 (可选)
    
    # 游戏统计
    difficulty = Column(String, index=True)  # 难度等级
    language = Column(String, default='zh')  # 语言模式 (zh/en)
    correct_count = Column(Integer, default=0)  # 答对题数
    total_score = Column(Integer, default=0)  # 总得分 = correct_count * 2
    total_time = Column(Float, default=300.0)  # 游戏总时间 (秒) - 固定5分钟
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

class PuzzleHistory(Base):
    """题目历史表 - 记录每个答题的详细信息"""
    __tablename__ = "puzzle_history"
    
    id = Column(Integer, primary_key=True, index=True)
    puzzle_id = Column(String, index=True)  # 题目ID
    session_id = Column(String, index=True)  # 所属会话ID
    
    # 题目内容
    difficulty = Column(String, index=True)  # 难度等级
    language = Column(String, index=True)  # 语言模式
    
    # 中文题目字段
    char1 = Column(String, nullable=True)  # 字1
    char2 = Column(String, nullable=True)  # 字2
    pattern = Column(Integer, nullable=True)  # 模式 (1/2/3)
    
    # 英文题目字段
    word1 = Column(String, nullable=True)  # 单词1
    word2 = Column(String, nullable=True)  # 单词2
    word3 = Column(String, nullable=True)  # 单词3
    
    # 答案和结果
    correct_answer = Column(String)  # 正确答案
    user_answer = Column(String, nullable=True)  # 用户答案
    is_correct = Column(Integer, default=0)  # 是否正确 (0=错误, 1=正确, 2=跳过)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

# 数据库引擎和会话（延迟初始化）
engine = None
SessionLocal = None

def init_db():
    """初始化数据库"""
    global engine, SessionLocal
    
    # 获取配置
    from config.settings import config
    from config.logging_config import get_logger
    
    logger = get_logger('database')
    
    # 创建引擎
    SQLALCHEMY_DATABASE_URL = config.DATABASE_URL
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
    )
    
    # 会话工厂
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")
    
    return engine

def get_db():
    """获取数据库会话"""
    if SessionLocal is None:
        init_db()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

