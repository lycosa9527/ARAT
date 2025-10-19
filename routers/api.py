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
import asyncio

from services.game_service import game_service
from services.captcha_service import generate_captcha, verify_captcha, check_rate_limit
from config.database import get_db, GameRecord, PuzzleHistory
from config.logging_config import get_logger
from config.settings import config
from models.requests import (
    StartSessionRequest,
    NextPuzzleRequest,
    ClearSessionRequest,
    ValidateAnswerRequest,
    GetAnswerRequest,
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

@router.post("/game/get_answer")
async def get_puzzle_answer(data: GetAnswerRequest):
    """
    获取题目答案 (用于跳过按钮和Demo模式)
    
    Args:
        data: GetAnswerRequest with puzzle_id
    
    Returns:
        Dict: {'answer': str}
    """
    try:
        puzzle = game_service.active_puzzles.get(data.puzzle_id)
        
        if not puzzle:
            logger.warning(f"Puzzle not found when getting answer | puzzle_id={data.puzzle_id}")
            raise HTTPException(status_code=404, detail="题目不存在或已过期")
        
        logger.info(f"Answer retrieved | puzzle_id={data.puzzle_id} | answer={puzzle['answer']}")
        
        return {
            'answer': puzzle['answer']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

# ============================================================================
# Inventory Status Endpoint (Admin/Monitoring)
# ============================================================================

# Disabled: Inventory replenishment not implemented
# @router.post("/admin/inventory_replenish")
# async def trigger_inventory_replenish(difficulty: str = None, language: str = None, count: int = 100):
#     """Disabled: Requires PuzzleInventory model and _replenish_inventory_batch method"""
#     raise HTTPException(status_code=501, detail="Inventory management not implemented")

@router.get("/admin/config_check")
async def check_config():
    """
    检查当前配置（用于诊断）
    
    Returns:
        Dict: 配置信息
    """
    from config.settings import config
    import os
    import time
    
    return {
        'status': 'success',
        'config': {
            'DEMO_PASSKEY': config.DEMO_PASSKEY,
            'DEMO_PASSKEY_from_env': os.environ.get('DEMO_PASSKEY', 'NOT_SET'),
            'QWEN_API_KEY_configured': bool(config.QWEN_API_KEY),
            'QWEN_API_KEY_length': len(config.QWEN_API_KEY) if config.QWEN_API_KEY else 0,
            'cache_timestamp': config._cache_timestamp,
            'cache_age_seconds': time.time() - config._cache_timestamp if config._cache_timestamp > 0 else 0
        }
    }

# ============================================================================
# Admin Panel Endpoints
# ============================================================================

@router.get("/admin/database/records")
async def get_database_records(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    language: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    获取LLM生成的题库（Admin面板 - Database Manager）
    显示puzzle_inventory表中的A+B=C格式，支持过滤
    
    Args:
        limit: 返回记录数量
        offset: 偏移量（分页）
        language: 过滤语言 (zh/en)
        difficulty: 过滤难度 (easy/medium/hard)
        db: 数据库会话
    
    Returns:
        Dict: 包含题目列表和总数
    """
    try:
        # Query puzzle_inventory table directly
        from sqlalchemy import text
        
        # Build WHERE clause based on filters
        where_clauses = []
        params = {"limit": limit, "offset": offset}
        
        if language:
            where_clauses.append("language = :language")
            params['language'] = language
        
        if difficulty:
            where_clauses.append("difficulty = :difficulty")
            params['difficulty'] = difficulty
        
        where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Get total count with filters
        total_query = text(f"SELECT COUNT(*) FROM puzzle_inventory{where_clause}")
        total = db.execute(total_query, {k: v for k, v in params.items() if k not in ['limit', 'offset']}).scalar()
        
        # Get puzzles with filters
        puzzles_query = text(f"""
            SELECT id, puzzle_id, difficulty, language, 
                   char1, char2, pattern, word1_en, word2_en, word3_en,
                   answer, is_used, created_at
            FROM puzzle_inventory
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = db.execute(puzzles_query, params)
        puzzles = result.fetchall()
        
        # Convert to dict
        puzzle_list = []
        for p in puzzles:
            if p.language == 'zh':
                word_pair = f"{p.char1} + {p.char2}"
                pattern_desc = f"Pattern {p.pattern}"
            else:
                word_pair = f"{p.word1_en}, {p.word2_en}, {p.word3_en}"
                pattern_desc = "English"
            
            puzzle_list.append({
                'id': p.id,
                'puzzle_id': p.puzzle_id,
                'difficulty': p.difficulty,
                'language': p.language,
                'word_pair': word_pair,
                'pattern': pattern_desc,
                'answer': p.answer,
                'is_used': p.is_used,
                'created_at': p.created_at
            })
        
        logger.info(f"Admin: Retrieved {len(puzzle_list)} puzzle inventory records (total: {total})")
        
        return {
            'status': 'success',
            'total': total,
            'limit': limit,
            'offset': offset,
            'puzzles': puzzle_list
        }
    except Exception as e:
        logger.error(f"Failed to get puzzle inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/diversity/stats")
async def get_diversity_stats(db: Session = Depends(get_db)):
    """
    获取题目多样性统计（Admin面板 - Inventory Status）
    分析puzzle_inventory表中每个难度等级使用的字符/单词多样性
    
    Returns:
        Dict: 多样性统计信息
    """
    try:
        from sqlalchemy import text
        stats_by_difficulty = {}
        
        # Analyze for each difficulty
        for difficulty in ['easy', 'medium', 'hard']:
            # Chinese puzzles
            zh_query = text("""
                SELECT char1, char2, answer 
                FROM puzzle_inventory 
                WHERE difficulty = :difficulty AND language = 'zh'
            """)
            zh_result = db.execute(zh_query, {"difficulty": difficulty})
            zh_puzzles = zh_result.fetchall()
            
            # Count unique characters used
            unique_chars = set()
            for p in zh_puzzles:
                if p.char1:
                    unique_chars.add(p.char1)
                if p.char2:
                    unique_chars.add(p.char2)
                if p.answer:
                    unique_chars.add(p.answer)
            
            # English puzzles
            en_query = text("""
                SELECT word1_en, word2_en, word3_en, answer
                FROM puzzle_inventory 
                WHERE difficulty = :difficulty AND language = 'en'
            """)
            en_result = db.execute(en_query, {"difficulty": difficulty})
            en_puzzles = en_result.fetchall()
            
            # Count unique words used
            unique_words = set()
            for p in en_puzzles:
                if p.word1_en:
                    unique_words.add(p.word1_en.lower())
                if p.word2_en:
                    unique_words.add(p.word2_en.lower())
                if p.word3_en:
                    unique_words.add(p.word3_en.lower())
                if p.answer:
                    unique_words.add(p.answer.lower())
            
            # Estimate total possible combinations
            # Chinese: ~3000 common characters, English: ~1000 common words
            zh_total_estimate = 3000
            en_total_estimate = 1000
            
            zh_percentage = (len(unique_chars) / zh_total_estimate * 100) if zh_total_estimate > 0 else 0
            en_percentage = (len(unique_words) / en_total_estimate * 100) if en_total_estimate > 0 else 0
            
            stats_by_difficulty[difficulty] = {
                'chinese': {
                    'unique_chars': len(unique_chars),
                    'total_puzzles': len(zh_puzzles),
                    'percentage': round(zh_percentage, 2),
                    'diversity_score': 'High' if zh_percentage > 10 else 'Medium' if zh_percentage > 5 else 'Low'
                },
                'english': {
                    'unique_words': len(unique_words),
                    'total_puzzles': len(en_puzzles),
                    'percentage': round(en_percentage, 2),
                    'diversity_score': 'High' if en_percentage > 15 else 'Medium' if en_percentage > 8 else 'Low'
                }
            }
        
        logger.info(f"Admin: Diversity stats calculated from puzzle_inventory")
        
        return {
            'status': 'success',
            'stats_by_difficulty': stats_by_difficulty
        }
    except Exception as e:
        logger.error(f"Failed to get diversity stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/inventory/status")
async def get_inventory_status():
    """
    获取库存状态（Admin面板 - Inventory Status）
    显示当前活跃题目
    
    Returns:
        Dict: 会话和题库统计信息
    """
    try:
        sessions = game_service.game_sessions
        puzzles = game_service.active_puzzles
        
        # Calculate stats
        active_sessions = len(sessions)
        cached_puzzles = len(puzzles)
        total_queue_size = sum(len(s['puzzle_queue']) for s in sessions.values())
        avg_queue_size = total_queue_size / active_sessions if active_sessions > 0 else 0
        
        # Get session details
        session_list = []
        for session_id, session_data in sessions.items():
            session_list.append({
                'session_id': session_id,
                'difficulty': session_data.get('difficulty', 'unknown'),
                'language': session_data.get('language', 'unknown'),
                'queue_size': len(session_data['puzzle_queue']),
                'created_at': session_data.get('created_at', 0)
            })
        
        # Get sample of active puzzles (max 20 most recent)
        puzzle_samples = []
        sorted_puzzles = sorted(
            puzzles.items(), 
            key=lambda x: x[1].get('created_at', 0), 
            reverse=True
        )[:20]
        
        for puzzle_id, puzzle_data in sorted_puzzles:
            if puzzle_data.get('language') == 'zh':
                puzzle_samples.append({
                    'puzzle_id': puzzle_id,
                    'char1': puzzle_data.get('char1', '?'),
                    'char2': puzzle_data.get('char2', '?'),
                    'answer': puzzle_data.get('answer', '?'),
                    'pattern': puzzle_data.get('pattern', 1),
                    'language': 'zh',
                    'difficulty': puzzle_data.get('difficulty', 'unknown')
                })
            else:
                puzzle_samples.append({
                    'puzzle_id': puzzle_id,
                    'word1': puzzle_data.get('word1', '?'),
                    'word2': puzzle_data.get('word2', '?'),
                    'word3': puzzle_data.get('word3', '?'),
                    'answer': puzzle_data.get('answer', '?'),
                    'language': 'en',
                    'difficulty': puzzle_data.get('difficulty', 'unknown')
                })
        
        logger.info(f"Admin: Inventory status - {active_sessions} sessions, {cached_puzzles} puzzles")
        
        return {
            'status': 'success',
            'active_sessions': active_sessions,
            'cached_puzzles': cached_puzzles,
            'total_queue_size': total_queue_size,
            'avg_queue_size': avg_queue_size,
            'sessions': session_list,
            'puzzle_samples': puzzle_samples
        }
    except Exception as e:
        logger.error(f"Failed to get inventory status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Puzzle Inventory Management Endpoints (Edit/Delete Database)
# ============================================================================

@router.post("/admin/puzzle_inventory/update")
async def update_puzzle_inventory(request: Request, db: Session = Depends(get_db)):
    """
    更新puzzle_inventory表中的题目（Admin面板 - Database Manager）
    
    Args:
        request: Request body containing puzzle id and updated fields
        db: Database session
    
    Returns:
        Dict: Success/failure status
    """
    try:
        from sqlalchemy import text
        data = await request.json()
        puzzle_id = data.get('id')
        
        if not puzzle_id:
            raise HTTPException(status_code=400, detail="id is required")
        
        # Build update query
        updates = []
        params = {"id": puzzle_id}
        
        if 'char1' in data:
            updates.append("char1 = :char1")
            params['char1'] = data['char1']
        if 'char2' in data:
            updates.append("char2 = :char2")
            params['char2'] = data['char2']
        if 'word1_en' in data:
            updates.append("word1_en = :word1_en")
            params['word1_en'] = data['word1_en']
        if 'word2_en' in data:
            updates.append("word2_en = :word2_en")
            params['word2_en'] = data['word2_en']
        if 'word3_en' in data:
            updates.append("word3_en = :word3_en")
            params['word3_en'] = data['word3_en']
        if 'answer' in data:
            updates.append("answer = :answer")
            params['answer'] = data['answer']
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_query = text(f"UPDATE puzzle_inventory SET {', '.join(updates)} WHERE id = :id")
        db.execute(update_query, params)
        db.commit()
        
        logger.info(f"Admin: Puzzle inventory updated | id={puzzle_id}")
        
        return {
            'status': 'success',
            'message': 'Puzzle updated successfully',
            'id': puzzle_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update puzzle inventory: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/puzzle_inventory/delete")
async def delete_puzzle_inventory(request: Request, db: Session = Depends(get_db)):
    """
    从puzzle_inventory表中删除题目（Admin面板 - Database Manager）
    
    Args:
        request: Request body containing puzzle id
        db: Database session
    
    Returns:
        Dict: Success/failure status
    """
    try:
        from sqlalchemy import text
        data = await request.json()
        puzzle_id = data.get('id')
        
        if not puzzle_id:
            raise HTTPException(status_code=400, detail="id is required")
        
        delete_query = text("DELETE FROM puzzle_inventory WHERE id = :id")
        result = db.execute(delete_query, {"id": puzzle_id})
        db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Puzzle not found")
        
        logger.info(f"Admin: Puzzle inventory deleted | id={puzzle_id}")
        
        return {
            'status': 'success',
            'message': 'Puzzle deleted successfully',
            'id': puzzle_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete puzzle inventory: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Puzzle Validation Admin Endpoint
# ============================================================================

@router.get("/admin/puzzle_inventory/validate")
async def validate_puzzle_inventory(db: Session = Depends(get_db)):
    """
    检查puzzle_inventory表中的无效题目
    无效题目定义：答案与输入字符相同（A=C或B=C）
    
    Returns:
        Dict: 无效题目列表和统计信息
    """
    try:
        from sqlalchemy import text
        
        # Get all puzzles
        query = text("""
            SELECT id, puzzle_id, difficulty, language, 
                   char1, char2, answer, 
                   word1_en, word2_en, word3_en
            FROM puzzle_inventory
        """)
        result = db.execute(query)
        all_puzzles = result.fetchall()
        
        invalid_puzzles = []
        stats = {
            'total': len(all_puzzles),
            'invalid_zh': 0,
            'invalid_en': 0,
            'valid': 0
        }
        
        for p in all_puzzles:
            is_invalid = False
            reason = ""
            
            if p.language == 'zh':
                # Check Chinese puzzles
                if p.answer == p.char1:
                    is_invalid = True
                    reason = f"答案'{p.answer}'与字A相同"
                elif p.answer == p.char2:
                    is_invalid = True
                    reason = f"答案'{p.answer}'与字B相同"
                elif p.char1 == p.char2:
                    is_invalid = True
                    reason = f"字A和字B相同: '{p.char1}'"
                
                if is_invalid:
                    stats['invalid_zh'] += 1
                    invalid_puzzles.append({
                        'id': p.id,
                        'puzzle_id': p.puzzle_id,
                        'language': 'zh',
                        'difficulty': p.difficulty,
                        'char1': p.char1,
                        'char2': p.char2,
                        'answer': p.answer,
                        'reason': reason
                    })
            
            elif p.language == 'en':
                # Check English puzzles
                answer_lower = p.answer.lower() if p.answer else ''
                word1_lower = p.word1_en.lower() if p.word1_en else ''
                word2_lower = p.word2_en.lower() if p.word2_en else ''
                word3_lower = p.word3_en.lower() if p.word3_en else ''
                
                if answer_lower == word1_lower:
                    is_invalid = True
                    reason = f"Answer '{p.answer}' same as word1"
                elif answer_lower == word2_lower:
                    is_invalid = True
                    reason = f"Answer '{p.answer}' same as word2"
                elif answer_lower == word3_lower:
                    is_invalid = True
                    reason = f"Answer '{p.answer}' same as word3"
                elif len(set([word1_lower, word2_lower, word3_lower])) < 3:
                    is_invalid = True
                    reason = f"Duplicate input words"
                
                if is_invalid:
                    stats['invalid_en'] += 1
                    invalid_puzzles.append({
                        'id': p.id,
                        'puzzle_id': p.puzzle_id,
                        'language': 'en',
                        'difficulty': p.difficulty,
                        'word1': p.word1_en,
                        'word2': p.word2_en,
                        'word3': p.word3_en,
                        'answer': p.answer,
                        'reason': reason
                    })
        
        stats['valid'] = stats['total'] - stats['invalid_zh'] - stats['invalid_en']
        stats['invalid_total'] = stats['invalid_zh'] + stats['invalid_en']
        
        logger.info(f"Admin: Validated puzzle inventory | total={stats['total']} | invalid={stats['invalid_total']}")
        
        return {
            'status': 'success',
            'stats': stats,
            'invalid_puzzles': invalid_puzzles
        }
    
    except Exception as e:
        logger.error(f"Failed to validate puzzle inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/puzzle_inventory/cleanup")
async def cleanup_invalid_puzzles(db: Session = Depends(get_db)):
    """
    自动清理puzzle_inventory表中的所有无效题目
    无效题目定义：答案与输入字符相同（A=C或B=C）
    
    这个操作会永久删除无效题目，请谨慎使用！
    
    Returns:
        Dict: 删除统计和被删除的题目列表
    """
    try:
        from sqlalchemy import text
        
        # Get all puzzles
        query = text("""
            SELECT id, puzzle_id, difficulty, language, 
                   char1, char2, answer, 
                   word1_en, word2_en, word3_en
            FROM puzzle_inventory
        """)
        result = db.execute(query)
        all_puzzles = result.fetchall()
        
        invalid_ids = []
        deleted_puzzles = []
        stats = {
            'total_before': len(all_puzzles),
            'deleted_zh': 0,
            'deleted_en': 0,
            'remaining': 0
        }
        
        for p in all_puzzles:
            is_invalid = False
            reason = ""
            
            if p.language == 'zh':
                # Check Chinese puzzles
                if p.answer == p.char1:
                    is_invalid = True
                    reason = f"答案'{p.answer}'与字A相同"
                elif p.answer == p.char2:
                    is_invalid = True
                    reason = f"答案'{p.answer}'与字B相同"
                elif p.char1 == p.char2:
                    is_invalid = True
                    reason = f"字A和字B相同: '{p.char1}'"
                
                if is_invalid:
                    stats['deleted_zh'] += 1
                    invalid_ids.append(p.id)
                    deleted_puzzles.append({
                        'id': p.id,
                        'puzzle_id': p.puzzle_id,
                        'language': 'zh',
                        'difficulty': p.difficulty,
                        'puzzle': f"{p.char1} | {p.char2} = {p.answer}",
                        'reason': reason
                    })
            
            elif p.language == 'en':
                # Check English puzzles
                answer_lower = p.answer.lower() if p.answer else ''
                word1_lower = p.word1_en.lower() if p.word1_en else ''
                word2_lower = p.word2_en.lower() if p.word2_en else ''
                word3_lower = p.word3_en.lower() if p.word3_en else ''
                
                if answer_lower == word1_lower:
                    is_invalid = True
                    reason = f"Answer '{p.answer}' same as word1"
                elif answer_lower == word2_lower:
                    is_invalid = True
                    reason = f"Answer '{p.answer}' same as word2"
                elif answer_lower == word3_lower:
                    is_invalid = True
                    reason = f"Answer '{p.answer}' same as word3"
                elif len(set([word1_lower, word2_lower, word3_lower])) < 3:
                    is_invalid = True
                    reason = f"Duplicate input words"
                
                if is_invalid:
                    stats['deleted_en'] += 1
                    invalid_ids.append(p.id)
                    deleted_puzzles.append({
                        'id': p.id,
                        'puzzle_id': p.puzzle_id,
                        'language': 'en',
                        'difficulty': p.difficulty,
                        'puzzle': f"{p.word1_en}, {p.word2_en}, {p.word3_en} = {p.answer}",
                        'reason': reason
                    })
        
        # Delete invalid puzzles in batch
        if invalid_ids:
            delete_query = text("DELETE FROM puzzle_inventory WHERE id IN :ids")
            db.execute(delete_query, {"ids": tuple(invalid_ids)})
            db.commit()
            
            logger.warning(f"Admin: Deleted {len(invalid_ids)} invalid puzzles from inventory")
        
        stats['total_deleted'] = stats['deleted_zh'] + stats['deleted_en']
        stats['remaining'] = stats['total_before'] - stats['total_deleted']
        
        security_logger.warning(
            f"ADMIN: Puzzle inventory cleanup completed | "
            f"deleted={stats['total_deleted']} (zh={stats['deleted_zh']}, en={stats['deleted_en']}) | "
            f"remaining={stats['remaining']}"
        )
        
        return {
            'status': 'success',
            'message': f"Successfully deleted {stats['total_deleted']} invalid puzzles",
            'stats': stats,
            'deleted_puzzles': deleted_puzzles
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to cleanup invalid puzzles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Inventory Admin Endpoints (Disabled - requires PuzzleInventory model)
# ============================================================================
# These endpoints are commented out because PuzzleInventory model doesn't exist
# in the current database schema. They were meant for advanced puzzle inventory
# management features that are not implemented yet.

# @router.get("/admin/inventory_duplicates")
# async def check_inventory_duplicates(db: Session = Depends(get_db)):
#     """Disabled: Requires PuzzleInventory model"""
#     raise HTTPException(status_code=501, detail="Inventory management not implemented")

# @router.get("/admin/inventory_status")
# async def get_inventory_status_old(db: Session = Depends(get_db)):
#     """Disabled: Requires PuzzleInventory model"""
#     raise HTTPException(status_code=501, detail="Inventory management not implemented")

