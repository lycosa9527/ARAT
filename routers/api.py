"""
API路由
处理所有游戏相关的API请求

Author: lyc9527
Team: MTEL Team from Educational Technology, Beijing Normal University
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional

from services.game_service import game_service
from services.captcha_service import generate_captcha, verify_captcha, check_rate_limit
from config.database import get_db, GameRecord
from config.logging_config import get_logger
from config.settings import config
from models.requests import (
    StartSessionRequest,
    NextPuzzleRequest,
    ClearSessionRequest,
    ValidateAnswerRequest,
    SubmitScoreRequest,
    DemoPasskeyRequest
)

router = APIRouter()
logger = get_logger('app')
security_logger = get_logger('security')

# ============================================================================
# Game Session Endpoints (Catapult Mechanism)
# ============================================================================

@router.post("/game/start_session")
async def start_game_session(data: StartSessionRequest):
    """
    开始游戏会话 - 立即返回第1题，后台预生成5题
    
    使用Catapult预生成机制，确保零等待体验
    """
    try:
        result = await game_service.start_game_session(
            session_id=data.session_id,
            difficulty=data.difficulty,
            language=data.language,
            llm=data.llm
        )
        return result
    except Exception as e:
        logger.error(f"Failed to start game session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/game/next_puzzle")
async def get_next_puzzle(data: NextPuzzleRequest):
    """
    获取下一题 - 从预生成队列获取（零等待）
    
    如果队列 < 3，自动触发补充生成
    """
    try:
        puzzle = await game_service.get_next_puzzle(session_id=data.session_id)
        return puzzle
    except Exception as e:
        logger.error(f"Failed to get next puzzle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/game/clear_session")
async def clear_game_session(data: ClearSessionRequest):
    """
    清理游戏会话队列（游戏结束时调用）
    
    释放内存资源
    """
    try:
        result = game_service.clear_session(data.session_id)
        return result
    except Exception as e:
        logger.error(f"Failed to clear session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Answer Validation Endpoint
# ============================================================================

@router.post("/game/validate")
async def validate_answer(data: ValidateAnswerRequest):
    """
    验证用户答案
    
    两步验证:
    1. 精确匹配（快速路径，无LLM调用）
    2. LLM智能验证（支持一题多解）
    """
    try:
        result = await game_service.validate_answer(
            puzzle_id=data.puzzle_id,
            user_answer=data.answer,
            llm=data.llm
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to validate answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Alias for backward compatibility
@router.post("/game/check_answer")
async def check_answer(data: ValidateAnswerRequest):
    """Alias for /game/validate"""
    return await validate_answer(data)

# ============================================================================
# Demo Endpoint (Development Only) - 需要密钥保护
# ============================================================================

def verify_demo_passkey(passkey: str) -> bool:
    """
    验证Demo访问密钥 (参考MindGraph实现)
    
    Args:
        passkey: 6位数字密钥
    
    Returns:
        bool: 密钥是否有效
    """
    passkey = passkey.strip() if passkey else ""
    expected_passkey = config.DEMO_PASSKEY.strip()
    return passkey == expected_passkey

@router.post("/game/demo/verify")
async def verify_demo_access(request: DemoPasskeyRequest):
    """
    验证Demo访问密钥 (参考MindGraph)
    
    用户必须提供正确的6位数字密钥才能访问demo端点
    """
    logger.info(f"Demo passkey verification attempt - Received: {len(request.passkey)} chars")
    
    if not verify_demo_passkey(request.passkey):
        logger.warning("Demo passkey verification failed - Invalid passkey attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passkey"
        )
    
    logger.info("Demo passkey verified successfully")
    return {
        "status": "verified",
        "message": "Passkey verified. You can now access /game/demo endpoint."
    }

@router.get("/game/demo")
async def get_demo_puzzle(
    difficulty: str = "easy",
    language: str = "zh",
    model: str = "qwen",
    passkey: str = Query(..., min_length=6, max_length=6, description="6-digit demo passkey")
):
    """
    获取Demo题目（开发调试用） - 需要密钥保护
    
    返回完整题目信息包括答案
    
    安全机制 (参考MindGraph):
    - 需要提供6位数字密钥 (配置在DEMO_PASSKEY环境变量)
    - 生产环境可通过DEBUG=False禁用
    - 所有访问都会被记录到安全日志
    """
    # 1. 生产环境检查
    if not config.DEBUG:
        raise HTTPException(
            status_code=403,
            detail="Demo endpoint is disabled in production"
        )
    
    # 2. 验证密钥
    if not verify_demo_passkey(passkey):
        security_logger.warning(f"Unauthorized demo access attempt | passkey_length={len(passkey)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passkey. Demo endpoint requires valid DEMO_PASSKEY."
        )
    
    # 3. 生成Demo题目
    try:
        demo_puzzle = await game_service.get_demo_puzzle(
            difficulty=difficulty,
            language=language,
            llm=model
        )
        
        # 记录合法访问
        security_logger.info(f"Demo endpoint accessed successfully | difficulty={difficulty} | language={language}")
        
        return demo_puzzle
    except Exception as e:
        logger.error(f"Failed to generate demo puzzle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Captcha Endpoint
# ============================================================================

@router.get("/captcha/generate")
async def get_captcha(request: Request):
    """
    生成验证码
    
    包含速率限制（每分钟最多10次）
    """
    client_ip = request.client.host
    
    if not check_rate_limit(client_ip, max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Too many captcha requests. Please try again later."
        )
    
    try:
        captcha_data = generate_captcha()
        return captcha_data
    except Exception as e:
        logger.error(f"Failed to generate captcha: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate captcha")

# ============================================================================
# Score Submission Endpoint
# ============================================================================

@router.post("/game/submit_score")
async def submit_score(
    data: SubmitScoreRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    提交游戏成绩到排行榜 - 简化计分系统（会话级别）
    
    需要验证码验证 (防止机器人刷榜)
    """
    # 1. Verify captcha
    if not verify_captcha(data.captcha_id, data.captcha):
        security_logger.warning(f"Invalid captcha attempt | IP: {request.client.host}")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired captcha code"
        )
    
    # 2. Validate score consistency
    if data.total_score != data.correct_count * 2:
        security_logger.warning(f"Score mismatch | IP: {request.client.host} | correct={data.correct_count} | score={data.total_score}")
        raise HTTPException(
            status_code=400,
            detail="Score calculation mismatch"
        )
    
    # 3. Check rate limit
    client_ip = request.client.host
    if not check_rate_limit(client_ip, max_requests=5, window_seconds=300):
        security_logger.warning(f"Score submission rate limit exceeded | IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")
    
    # 4. Save to database
    try:
        new_record = GameRecord(
            session_id=data.session_id,
            player_name=data.nickname,
            school_name=data.school,
            difficulty=data.difficulty,
            language=data.language,
            correct_count=data.correct_count,
            total_score=data.total_score,
            total_time=data.total_time,
            completed_at=datetime.utcnow()
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        
        # 5. Calculate rank
        rank = db.query(GameRecord)\
            .filter(GameRecord.total_score > data.total_score)\
            .count() + 1
        
        logger.info(f"Score submitted | player={data.nickname} | school={data.school} | score={data.total_score} | rank={rank}")
        
        return {
            "status": "success",
            "rank": rank,
            "player_name": data.nickname,
            "school_name": data.school,
            "score": data.total_score,
            "message": "Score submitted successfully"
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save score: {e}")
        raise HTTPException(status_code=500, detail="Failed to save score")

# ============================================================================
# Leaderboard Endpoint
# ============================================================================

@router.get("/leaderboard")
async def get_leaderboard(
    period: str = "all",  # all, weekly, daily
    limit: int = 100,
    player_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取排行榜
    
    支持:
    - 全部时间 (all)
    - 本周 (weekly)
    - 今日 (daily)
    - 玩家名高亮
    """
    try:
        # Filter by period
        query = db.query(GameRecord)
        if period == "daily":
            query = query.filter(
                GameRecord.created_at >= datetime.utcnow() - timedelta(days=1)
            )
        elif period == "weekly":
            query = query.filter(
                GameRecord.created_at >= datetime.utcnow() - timedelta(days=7)
            )
        
        # Aggregate by player
        leaderboard_data = query.with_entities(
            GameRecord.player_name,
            GameRecord.school_name,
            func.max(GameRecord.total_score).label('best_score'),
            func.count(GameRecord.id).label('games_played')
        ).group_by(GameRecord.player_name, GameRecord.school_name)\
         .order_by(func.max(GameRecord.total_score).desc())\
         .limit(limit)\
         .all()
        
        # Format response
        leaderboard = []
        for idx, (name, school, score, games) in enumerate(leaderboard_data, 1):
            leaderboard.append({
                'rank': idx,
                'player_name': name,
                'school_name': school,
                'best_score': score,
                'games_played': games,
                'is_current_player': (name == player_name) if player_name else False
            })
        
        return {
            'period': period,
            'total_entries': len(leaderboard),
            'leaderboard': leaderboard
        }
    
    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve leaderboard")

# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": config.VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "service": "ARAT-Word-Bridge-Game"
    }

@router.get("/config/share_url")
async def get_share_url():
    """获取分享URL配置"""
    return {
        "share_url": config.EXTERNAL_URL
    }

