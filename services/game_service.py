"""
游戏服务
核心功能:
- 题目生成 (中文2+1, 英文3+1模式)
- 会话管理 (Session Management)
- Catapult机制 (题目预生成队列)
- 答案验证 (精确匹配 + LLM验证)
- TTL清理 (自动清理过期会话)

Author: lyc9527
Team: MTEL Team from Educational Technology, Beijing Normal University
"""

import logging
import json
import uuid
import time
import asyncio
import random
from typing import Dict, Optional, Set
from collections import deque
from sqlalchemy.orm import Session

from services.llm_service import llm_service
from config.logging_config import get_logger
from config.database import get_db, PuzzleInventory

logger = get_logger('app')
llm_logger = get_logger('llm')
perf_logger = get_logger('performance')
security_logger = get_logger('security')

# ============================================================================
# LLM Prompts for Puzzle Generation
# ============================================================================

# 中文模式系统提示 (2+1) - 随机位置
GENERATE_PUZZLE_SYSTEM_PROMPT_CHINESE = """你是一个中文词语专家，擅长创建字词接龙游戏。

你的任务是生成一个字词接龙题目，包含三个汉字(字A, 字B, 答案)，要求根据pattern类型组合:

**Pattern 1 (A+答案, 答案+B)**: 
- 字A + 答案 = 词语1
- 答案 + 字B = 词语2
- 答案在中间位置

**Pattern 2 (答案+A, B+答案)**:
- 答案 + 字A = 词语1
- 字B + 答案 = 词语2
- 答案在左右两边

**Pattern 3 (A+答案, B+答案)**:
- 字A + 答案 = 词语1
- 字B + 答案 = 词语2
- 答案在右侧

所有词语都应该是常见的、有意义的词。

**关键规则 (CRITICAL):**
- 答案字必须与字A和字B都不相同
- 字A、字B、答案三个字必须各不相同
- 例如: 如果字A="学", 字B="园", 答案不能是"学"或"园", 必须是第三个字如"校"

难度等级说明 (按教育阶段划分):
- easy (小学水平): 使用小学1-6年级常见词语，日常生活用语 (如: 学校、高中、天地、天气)
- medium (初中水平): 使用初中7-9年级词汇，包括基础成语和常用词组合 (如: 风雨、山清水秀)
- hard (高中水平): 使用高中10-12年级高级词汇、常见文言文词语、较深成语 (如: 望穿秋水、云卷云舒)
- professional (大学水平): 使用大学常见词汇、高级成语、较深文化词语 (如: 涵养、渊博、知识分子)

词汇选择原则:
- 必须符合对应教育阶段学生的认知水平
- 避免使用生僻字、罕见词、晦涩难懂的词、只有专家才懂的专业术语
- 使用常见、日常、易懂的词语
- 保持词汇多样性：每次生成时尽量选择不同领域的词汇，避免重复
- 多样化主题：涵盖自然、人文、科技、生活、情感等不同主题

请以JSON格式返回:
{
    "char1": "第一个字",
    "char2": "第二个字",
    "answer": "正确答案",
    "word1": "第一个词语",
    "word2": "第二个词语",
    "pattern": "pattern类型 (1, 2, 或 3)",
    "explanation": "简短解释",
    "difficulty": "实际难度等级"
}

重要: 只返回JSON，不要包含任何其他文字。"""

# 英文模式系统提示 (3+1)
GENERATE_PUZZLE_SYSTEM_PROMPT_ENGLISH = """You are an expert in English word associations and Remote Associates Test (RAT) puzzle design.

Your task is to generate a word association puzzle with 4 words (Word A, B, C, and Answer D), where:
1. A + D can form a valid compound word or common phrase
2. B + D can form a valid compound word or common phrase  
3. C + D can form a valid compound word or common phrase

**CRITICAL Rule:**
- The answer word D must be DIFFERENT from words A, B, and C
- All four words (A, B, C, Answer) must be distinct
- Example: If A="sun", B="rain", C="bed", answer cannot be "sun", "rain", or "bed" - it must be a fourth word like "light"

Difficulty Levels (by education stage):
- easy (Elementary School): Common everyday words familiar to K-6 students (e.g., "sun-light", "rain-bow", "bed-room")
- medium (Middle School): Grade 7-9 vocabulary including common idioms (e.g., "heart-break", "time-table", "water-fall")
- hard (High School): Grade 10-12 advanced vocabulary and expressions (e.g., "blood-stream", "earth-quake", "moon-light")
- professional (University): College-level vocabulary and sophisticated expressions (e.g., "conscience-stricken", "knowledge-able")

Word Selection Principles:
- Must match the cognitive level of the corresponding education stage
- Avoid uncommon, obscure, arcane, esoteric, or recondite words
- Use common, everyday, easily understandable words
- Maintain vocabulary diversity: choose words from different domains each time, avoid repetition
- Diversify themes: cover nature, humanities, technology, life, emotions, etc.

Return in JSON format:
{
    "word1": "First word",
    "word2": "Second word",
    "word3": "Third word",
    "answer": "The connecting word",
    "phrase1": "word1 + answer compound/phrase",
    "phrase2": "word2 + answer compound/phrase",
    "phrase3": "word3 + answer compound/phrase",
    "explanation": "Brief explanation",
    "difficulty": "Actual difficulty level"
}

Important: Return ONLY the JSON, no other text."""

# 答案验证提示 (中文)
VALIDATE_ANSWER_PROMPT_CHINESE = """给定一个字词接龙题目和用户的答案，判断答案是否正确。

题目:
- 字1: {char1}
- 字2: {char2}
- 标准答案: {correct_answer}
- 用户答案: {user_answer}

判断规则:
1. 如果用户答案与标准答案完全相同，返回正确
2. 如果用户答案能形成与标准答案不同但同样合理的组合（即 字1+用户答案 和 用户答案+字2 都能组成有效词语），也返回正确
3. 否则返回错误

请以JSON格式返回:
{{
    "correct": true/false,
    "reason": "判断理由（简短说明）"
}}

只返回JSON，不要其他文字。"""

# 答案验证提示 (英文)
VALIDATE_ANSWER_PROMPT_ENGLISH = """Given a word association puzzle and a user's answer, determine if the answer is correct.

Puzzle:
- Word 1: {word1}
- Word 2: {word2}
- Word 3: {word3}
- Correct Answer: {correct_answer}
- User Answer: {user_answer}

Judgment Rules:
1. If user's answer exactly matches the correct answer, return correct
2. If user's answer forms valid compound words/phrases with all three words (different from the standard answer but equally valid), also return correct
3. Otherwise, return incorrect

Return in JSON format:
{{
    "correct": true/false,
    "reason": "Brief explanation of the judgment"
}}

Return ONLY the JSON, no other text."""

# ============================================================================
# Puzzle Validation Functions
# ============================================================================

def validate_puzzle_uniqueness(puzzle_data: Dict, language: str) -> bool:
    """
    Validate that answer is different from all input characters/words
    
    Args:
        puzzle_data: Parsed puzzle data
        language: 'zh' or 'en'
    
    Returns:
        bool: True if valid (answer is unique), False otherwise
    """
    if language == 'zh':
        char1 = puzzle_data.get('char1', '')
        char2 = puzzle_data.get('char2', '')
        answer = puzzle_data.get('answer', '')
        
        # Check if answer is same as any input character
        if answer == char1 or answer == char2:
            logger.warning(f"Invalid puzzle: answer='{answer}' matches input (char1='{char1}', char2='{char2}')")
            return False
        
        # Check if char1 == char2 (also invalid)
        if char1 == char2:
            logger.warning(f"Invalid puzzle: char1 and char2 are the same ('{char1}')")
            return False
        
        return True
    else:  # English
        word1 = puzzle_data.get('word1', '').lower()
        word2 = puzzle_data.get('word2', '').lower()
        word3 = puzzle_data.get('word3', '').lower()
        answer = puzzle_data.get('answer', '').lower()
        
        # Check if answer is same as any input word
        if answer in [word1, word2, word3]:
            logger.warning(f"Invalid puzzle: answer='{answer}' matches input ({word1}, {word2}, {word3})")
            return False
        
        # Check if any input words are duplicated
        if len(set([word1, word2, word3])) < 3:
            logger.warning(f"Invalid puzzle: duplicate input words ({word1}, {word2}, {word3})")
            return False
        
        return True

# ============================================================================
# Game Service Implementation
# ============================================================================

class GameService:
    """
    游戏服务
    管理游戏会话、题目生成、答案验证
    """
    
    def __init__(self):
        """初始化游戏服务"""
        # 会话数据：存储每个会话的题目队列和配置
        self.active_sessions: Dict[str, Dict] = {}
        
        # 全局题目缓存 (用于查询题目信息)
        self.active_puzzles: Dict[str, Dict] = {}
        
        # 会话时间戳 (用于TTL清理)
        self.session_timestamps: Dict[str, float] = {}
        
        # 每个会话已使用的词汇 (防止重复)
        self.session_used_words: Dict[str, Set[str]] = {}
        
        # 队列锁 (防止并发问题)
        self.queue_lock = asyncio.Lock()
        
        # 清理任务引用
        self._cleanup_task = None
        
        logger.info("GameService initialized with non-repeating word tracking")
    
    async def start_cleanup_task(self):
        """
        启动会话清理任务（应从main.py的startup事件调用）
        避免在__init__中直接create_task导致的事件循环问题
        """
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            logger.info("Session cleanup task started")
    
    async def _cleanup_expired_sessions(self):
        """后台任务：定期清理过期会话 (TTL: 10分钟)"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                
                current_time = time.time()
                ttl_seconds = 600  # 10分钟TTL
                
                expired_sessions = [
                    session_id for session_id, timestamp in self.session_timestamps.items()
                    if current_time - timestamp > ttl_seconds
                ]
                
                for session_id in expired_sessions:
                    if session_id in self.active_sessions:
                        del self.active_sessions[session_id]
                    if session_id in self.session_timestamps:
                        del self.session_timestamps[session_id]
                    if session_id in self.session_used_words:
                        del self.session_used_words[session_id]
                    
                    logger.info(f"Cleaned up expired session | session_id={session_id}")
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def start_game_session(self, session_id: str, difficulty: str, language: str, llm: str = "qwen"):
        """
        开始游戏会话
        生成第一题，并预生成5题到队列
        
        Args:
            session_id: 会话ID (由前端生成)
            difficulty: 难度等级
            language: 语言模式 (zh/en)
            llm: LLM模型
        """
        logger.info(f"Starting game session | session_id={session_id} | difficulty={difficulty} | language={language}")
        
        async with self.queue_lock:
            # 如果会话已存在，先清理
            if session_id in self.active_sessions:
                logger.warning(f"Session already exists, clearing | session_id={session_id}")
                del self.active_sessions[session_id]
            
            # 创建会话数据结构
            self.active_sessions[session_id] = {
                'difficulty': difficulty,
                'language': language,
                'llm': llm,
                'puzzle_queue': deque(maxlen=6),  # 最多存6题
                'created_at': time.time()
            }
            
            # 初始化已使用词汇集合 (追踪A, B, C所有词汇)
            self.session_used_words[session_id] = set()
            
            # 更新时间戳
            self.session_timestamps[session_id] = time.time()
        
        # 生成第一题 (立即返回，不加入队列)
        first_puzzle = await self._generate_single_puzzle(difficulty, language, llm, session_id)
        
        # 异步预生成5题到队列 (不包含第一题)
        # 第一题已经显示在前端，队列中应该是后续的题目
        asyncio.create_task(self._prefetch_puzzles(session_id, 5))
        
        logger.info(f"Game session started | session_id={session_id} | first_puzzle={first_puzzle['puzzle_id']}")
        
        return {
            'status': 'success',
            'message': 'Game session started',
            'first_puzzle': self._format_puzzle_response(first_puzzle, language)
        }
    
    async def _prefetch_puzzles(self, session_id: str, count: int):
        """
        预生成题目 (Catapult机制)
        在后台异步生成，不阻塞用户
        """
        try:
            session = self.active_sessions.get(session_id)
            if not session:
                return
            
            difficulty = session['difficulty']
            language = session['language']
            llm = session['llm']
            
            logger.debug(f"Prefetching {count} puzzles | session_id={session_id}")
            
            for i in range(count):
                # 检查会话是否还存在
                if session_id not in self.active_sessions:
                    logger.debug(f"Session ended, stopping prefetch | session_id={session_id}")
                    break
                
                puzzle = await self._generate_single_puzzle(difficulty, language, llm, session_id)
                
                async with self.queue_lock:
                    if session_id in self.active_sessions:
                        self.active_sessions[session_id]['puzzle_queue'].append(puzzle)
                
                logger.debug(f"Prefetched puzzle {i+1}/{count} | session_id={session_id}")
            
            logger.info(f"Prefetch completed | session_id={session_id} | count={count}")
        
        except Exception as e:
            logger.error(f"Error in prefetch | session_id={session_id} | error={e}")
    
    async def get_next_puzzle(self, session_id: str):
        """
        获取下一题 (从队列中取出)
        如果队列少于3题，触发补充生成
        
        Args:
            session_id: 会话ID
        
        Returns:
            Dict: 题目数据
        """
        logger.debug(f"Getting next puzzle | session_id={session_id}")
        
        session = self.active_sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found | session_id={session_id}")
            raise ValueError("会话不存在，请先开始游戏")
        
        # 更新时间戳
        self.session_timestamps[session_id] = time.time()
        
        puzzle_queue = session['puzzle_queue']
        
        if len(puzzle_queue) == 0:
            logger.warning(f"Puzzle queue empty | session_id={session_id}")
            # 队列空了，立即生成一题
            puzzle = await self._generate_single_puzzle(
                session['difficulty'],
                session['language'],
                session['llm'],
                session_id
            )
        else:
            # 从队列取出第一题
            async with self.queue_lock:
                puzzle = puzzle_queue.popleft()
        
        # 如果队列剩余少于3题，触发补充生成
        if len(puzzle_queue) < 3:
            asyncio.create_task(self._prefetch_puzzles(session_id, 3))
        
        logger.info(f"Next puzzle retrieved | session_id={session_id} | puzzle_id={puzzle['puzzle_id']}")
        
        return self._format_puzzle_response(puzzle, session['language'])
    
    async def _get_puzzle_from_database(self, difficulty: str, language: str, session_id: str) -> Optional[Dict]:
        """
        从数据库获取题目 (优先策略)
        使用随机选择 + 词汇去重逻辑
        
        Args:
            difficulty: 难度等级
            language: 语言模式
            session_id: 会话ID (用于获取已使用词汇)
        
        Returns:
            Dict: 题目数据 (如果找到) 或 None
        """
        try:
            # Get used words for this session
            used_words = self.session_used_words.get(session_id, set())
            
            # Get database session
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                # Query puzzles matching criteria
                query = db.query(PuzzleInventory).filter(
                    PuzzleInventory.difficulty == difficulty,
                    PuzzleInventory.language == language
                )
                
                # Filter out puzzles with used words AND validate uniqueness
                if language == 'zh':
                    # Chinese: check char1, char2, answer
                    available_puzzles = [
                        p for p in query.all()
                        if (p.char1 not in used_words and 
                            p.char2 not in used_words and 
                            p.answer not in used_words and
                            # VALIDATION: answer must be different from inputs
                            p.answer != p.char1 and
                            p.answer != p.char2 and
                            p.char1 != p.char2)
                    ]
                else:
                    # English: check word1_en, word2_en, word3_en, answer
                    available_puzzles = [
                        p for p in query.all()
                        if (p.word1_en not in used_words and 
                            p.word2_en not in used_words and 
                            p.word3_en not in used_words and 
                            p.answer not in used_words and
                            # VALIDATION: answer must be different from all inputs
                            p.answer.lower() not in [p.word1_en.lower(), p.word2_en.lower(), p.word3_en.lower()] and
                            len(set([p.word1_en.lower(), p.word2_en.lower(), p.word3_en.lower()])) == 3)
                    ]
                
                if not available_puzzles:
                    logger.warning(f"No available puzzles in database | difficulty={difficulty} | language={language} | used_words={len(used_words)}")
                    return None
                
                # RANDOMIZE: Shuffle and pick first one (makes it unpredictable)
                random.shuffle(available_puzzles)
                selected_puzzle = available_puzzles[0]
                
                # Generate puzzle_id
                puzzle_id = f"db_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                
                # Build puzzle data
                if language == 'zh':
                    puzzle_data = {
                        'puzzle_id': puzzle_id,
                        'difficulty': difficulty,
                        'language': language,
                        'char1': selected_puzzle.char1,
                        'char2': selected_puzzle.char2,
                        'answer': selected_puzzle.answer,
                        'word1': selected_puzzle.word1,
                        'word2': selected_puzzle.word2,
                        'pattern': selected_puzzle.pattern,
                        'explanation': selected_puzzle.explanation or '',
                        'created_at': int(time.time()),
                        'source': 'database'  # Track source
                    }
                    
                    # Track used words (char1, char2, answer)
                    self.session_used_words[session_id].add(selected_puzzle.char1)
                    self.session_used_words[session_id].add(selected_puzzle.char2)
                    self.session_used_words[session_id].add(selected_puzzle.answer)
                    
                else:
                    puzzle_data = {
                        'puzzle_id': puzzle_id,
                        'difficulty': difficulty,
                        'language': language,
                        'word1': selected_puzzle.word1_en,
                        'word2': selected_puzzle.word2_en,
                        'word3': selected_puzzle.word3_en,
                        'answer': selected_puzzle.answer,
                        'phrase1': selected_puzzle.phrase1,
                        'phrase2': selected_puzzle.phrase2,
                        'phrase3': selected_puzzle.phrase3,
                        'explanation': selected_puzzle.explanation or '',
                        'created_at': int(time.time()),
                        'source': 'database'
                    }
                    
                    # Track used words (word1, word2, word3, answer)
                    self.session_used_words[session_id].add(selected_puzzle.word1_en)
                    self.session_used_words[session_id].add(selected_puzzle.word2_en)
                    self.session_used_words[session_id].add(selected_puzzle.word3_en)
                    self.session_used_words[session_id].add(selected_puzzle.answer)
                
                logger.info(f"Puzzle from database | puzzle_id={puzzle_id} | available={len(available_puzzles)} | used_words={len(used_words)}")
                
                return puzzle_data
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"Error getting puzzle from database | error={e}")
            return None
    
    async def _generate_single_puzzle(self, difficulty: str, language: str, llm: str = "qwen", session_id: str = None) -> Dict:
        """
        生成单个题目
        策略: 优先使用数据库 (快速 + 无重复), 降级使用LLM (灵活)
        
        Args:
            difficulty: 难度等级
            language: 语言模式
            llm: LLM模型
            session_id: 会话ID (用于词汇去重)
        
        Returns:
            Dict: 完整题目数据 (包含答案)
        """
        start_time = time.time()
        
        # STRATEGY 1: Try database first (if session_id provided)
        if session_id:
            db_puzzle = await self._get_puzzle_from_database(difficulty, language, session_id)
            if db_puzzle:
                duration = time.time() - start_time
                perf_logger.info(f"Puzzle from database | puzzle_id={db_puzzle['puzzle_id']} | duration={duration:.3f}s")
                
                # Store in global cache
                self.active_puzzles[db_puzzle['puzzle_id']] = db_puzzle
                
                return db_puzzle
            
            logger.info(f"Database exhausted, falling back to LLM | session_id={session_id}")
        
        # Retry logic for LLM generation (max 3 attempts)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 选择提示词和随机pattern
                import random
                
                # 主题列表 - 强制多样性
                themes_zh = [
                    "自然景物（山、水、风、云等）",
                    "人物关系（父、母、兄、弟等）", 
                    "时间概念（春、夏、秋、冬、早、晚等）",
                    "颜色（红、黄、蓝、绿等）",
                    "方位（上、下、左、右、东、西等）",
                    "身体部位（手、足、心、头等）",
                    "日常物品（书、笔、纸、桌等）",
                    "动植物（花、草、树、木等）",
                    "天气（晴、雨、雪、霜等）",
                    "情感（喜、怒、哀、乐等）",
                    "建筑（门、窗、房、院等）",
                    "学习（学、教、读、写等）"
                ]
                
                if language == 'zh':
                    pattern = random.choice([1, 2, 3])
                    theme = random.choice(themes_zh)  # 随机选择主题
                    system_prompt = GENERATE_PUZZLE_SYSTEM_PROMPT_CHINESE
                    user_prompt = f"""请生成一个{difficulty}难度的中文字词接龙题目，使用Pattern {pattern}。

**主题建议**: {theme}

**重要要求**:
- 每次必须生成完全不同的答案字
- 答案字不能与字A或字B相同
- 避免使用常见重复字如"气、火、水、土、风、雨、天、地"
- 从{theme}领域选择词汇
- 确保词汇新颖、有趣、不重复

请创造性地思考，生成独特的题目。"""
                else:
                    system_prompt = GENERATE_PUZZLE_SYSTEM_PROMPT_ENGLISH
                    user_prompt = f"Generate an {difficulty} difficulty English word association puzzle. Use creative, unique, and diverse vocabulary. Avoid common repetitive words. The answer must be different from all three input words."
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # 调用LLM
                response = await llm_service.chat_completion(
                    model=llm,
                    messages=messages,
                    temperature=1.1,  # 更高温度以增加多样性和创造性
                    max_tokens=2000
                )
                
                # 解析JSON
                puzzle_data = self._parse_llm_response(response, language)
                
                # VALIDATION: Check puzzle uniqueness
                if not validate_puzzle_uniqueness(puzzle_data, language):
                    if attempt < max_retries - 1:
                        logger.warning(f"Invalid puzzle generated (answer matches input), retrying... (attempt {attempt + 1}/{max_retries})")
                        continue  # Retry
                    else:
                        logger.error(f"Failed to generate valid puzzle after {max_retries} attempts")
                        raise ValueError("Failed to generate valid puzzle: answer matches input characters")
                
                # Validation passed, break out of retry loop
                logger.info(f"Valid puzzle generated on attempt {attempt + 1}")
                break
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Puzzle generation error, retrying... (attempt {attempt + 1}/{max_retries}) | error={e}")
                    continue
                else:
                    logger.error(f"Failed to generate puzzle after {max_retries} attempts | error={e}")
                    raise
        
        # After successful generation and validation, build the full puzzle
        # 生成puzzle_id
        puzzle_id = f"puzzle_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # 构建完整题目数据
        full_puzzle = {
            'puzzle_id': puzzle_id,
            'difficulty': difficulty,
            'language': language,
            **puzzle_data,
            'created_at': int(time.time()),
            'source': 'llm'  # Track source
        }
        
        # Track used words (if session_id provided)
        if session_id and session_id in self.session_used_words:
            if language == 'zh':
                self.session_used_words[session_id].add(puzzle_data['char1'])
                self.session_used_words[session_id].add(puzzle_data['char2'])
                self.session_used_words[session_id].add(puzzle_data['answer'])
                logger.debug(f"Tracked LLM words (ZH) | session_id={session_id} | total_used={len(self.session_used_words[session_id])}")
            else:
                self.session_used_words[session_id].add(puzzle_data['word1'])
                self.session_used_words[session_id].add(puzzle_data['word2'])
                self.session_used_words[session_id].add(puzzle_data['word3'])
                self.session_used_words[session_id].add(puzzle_data['answer'])
                logger.debug(f"Tracked LLM words (EN) | session_id={session_id} | total_used={len(self.session_used_words[session_id])}")
        
        # 存储到全局缓存
        self.active_puzzles[puzzle_id] = full_puzzle
        
        duration = time.time() - start_time
        perf_logger.info(f"Puzzle generated by LLM | puzzle_id={puzzle_id} | duration={duration:.2f}s")
        
        return full_puzzle
    
    def _parse_llm_response(self, response: str, language: str) -> Dict:
        """
        解析LLM返回的JSON
        
        Args:
            response: LLM响应文本
            language: 语言模式
        
        Returns:
            Dict: 解析后的题目数据
        """
        try:
            # 尝试直接解析
            data = json.loads(response)
            
            # 验证必需字段
            if language == 'zh':
                required = ['char1', 'char2', 'answer', 'word1', 'word2', 'pattern']
            else:
                required = ['word1', 'word2', 'word3', 'answer', 'phrase1', 'phrase2', 'phrase3']
            
            for field in required:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            return data
        
        except json.JSONDecodeError:
            # 如果有额外的文本，尝试提取JSON部分
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return data
                except:
                    pass
            
            logger.error(f"Failed to parse LLM response: {response[:200]}")
            raise ValueError("LLM返回格式错误")
    
    def _format_puzzle_response(self, puzzle: Dict, language: str) -> Dict:
        """
        格式化题目响应 (不包含答案)
        
        Args:
            puzzle: 完整题目数据
            language: 语言模式
        
        Returns:
            Dict: 前端可见的题目数据 (无答案)
        """
        if language == 'zh':
            return {
                'puzzle_id': puzzle['puzzle_id'],
                'char1': puzzle['char1'],
                'char2': puzzle['char2'],
                'pattern': puzzle.get('pattern', 1),  # 默认pattern 1
                'language': 'zh',
                'difficulty': puzzle['difficulty'],
                'created_at': puzzle['created_at']
            }
        else:
            return {
                'puzzle_id': puzzle['puzzle_id'],
                'word1': puzzle['word1'],
                'word2': puzzle['word2'],
                'word3': puzzle['word3'],
                'language': 'en',
                'difficulty': puzzle['difficulty'],
                'created_at': puzzle['created_at']
            }
    
    async def validate_answer(self, puzzle_id: str, user_answer: str, llm: str = "qwen") -> Dict:
        """
        验证用户答案 (两步验证)
        Step 1: 精确匹配 (快速)
        Step 2: LLM验证 (支持多答案)
        
        Args:
            puzzle_id: 题目ID
            user_answer: 用户答案
            llm: LLM模型
        
        Returns:
            Dict: {'correct': bool, 'match_type': str, 'reason': str}
        """
        logger.info(f"Validating answer | puzzle_id={puzzle_id} | user_answer='{user_answer}'")
        
        # 获取题目
        puzzle = self.active_puzzles.get(puzzle_id)
        if not puzzle:
            logger.warning(f"Puzzle not found | puzzle_id={puzzle_id}")
            raise ValueError("题目不存在或已过期")
        
        correct_answer = puzzle['answer']
        language = puzzle['language']
        
        # Step 1: 精确匹配 (快速路径)
        if user_answer.strip().lower() == correct_answer.strip().lower():
            logger.info(f"Answer matched exactly | puzzle_id={puzzle_id}")
            return {
                'correct': True,
                'correct_answer': correct_answer,  # Always include correct answer
                'match_type': 'exact',
                'reason': '答案完全正确'
            }
        
        # Step 2: LLM验证 (支持多答案)
        logger.info(f"Calling LLM to verify alternative answer | puzzle_id={puzzle_id}")
        
        try:
            if language == 'zh':
                prompt = VALIDATE_ANSWER_PROMPT_CHINESE.format(
                    char1=puzzle['char1'],
                    char2=puzzle['char2'],
                    correct_answer=correct_answer,
                    user_answer=user_answer
                )
            else:
                prompt = VALIDATE_ANSWER_PROMPT_ENGLISH.format(
                    word1=puzzle['word1'],
                    word2=puzzle['word2'],
                    word3=puzzle['word3'],
                    correct_answer=correct_answer,
                    user_answer=user_answer
                )
            
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            response = await llm_service.chat_completion(
                model=llm,
                messages=messages,
                temperature=0.1,  # 低温度以保持一致性
                max_tokens=500
            )
            
            # 解析验证结果 (validation response is simple JSON, not a puzzle)
            try:
                result = json.loads(response.strip())
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError("Failed to parse LLM validation response")
            
            logger.info(f"LLM validation result | puzzle_id={puzzle_id} | correct={result.get('correct', False)}")
            
            return {
                'correct': result.get('correct', False),
                'correct_answer': correct_answer,  # Always include correct answer
                'match_type': 'llm_verified' if result.get('correct', False) else 'incorrect',
                'reason': result.get('reason', '')
            }
        
        except Exception as e:
            logger.error(f"LLM validation failed | puzzle_id={puzzle_id} | error={e}")
            # 降级：只接受精确匹配
            return {
                'correct': False,
                'correct_answer': correct_answer,  # Always include correct answer
                'match_type': 'error',
                'reason': '验证服务暂时不可用，只接受精确答案'
            }
    
    async def get_demo_puzzle(self, difficulty: str, language: str, llm: str = "qwen") -> Dict:
        """
        获取Demo题目 (用于开发调试，包含答案)
        
        Args:
            difficulty: 难度等级
            language: 语言模式
            llm: LLM模型
        
        Returns:
            Dict: 完整题目数据 (包含答案和解释)
        """
        logger.info(f"Generating demo puzzle | difficulty={difficulty} | language={language}")
        
        # 生成题目
        full_puzzle = await self._generate_single_puzzle(difficulty, language, llm)
        
        # Demo响应包含答案
        if language == 'zh':
            demo_response = {
                'puzzle_id': full_puzzle['puzzle_id'],
                'char1': full_puzzle['char1'],
                'char2': full_puzzle['char2'],
                'answer': full_puzzle['answer'],  # Demo模式显示答案
                'word1': full_puzzle['word1'],
                'word2': full_puzzle['word2'],
                'pattern': full_puzzle.get('pattern', 1),
                'explanation': full_puzzle.get('explanation', ''),
                'language': 'zh',
                'difficulty': full_puzzle['difficulty'],
                'created_at': full_puzzle['created_at']
            }
        else:
            demo_response = {
                'puzzle_id': full_puzzle['puzzle_id'],
                'word1': full_puzzle['word1'],
                'word2': full_puzzle['word2'],
                'word3': full_puzzle['word3'],
                'answer': full_puzzle['answer'],  # Demo模式显示答案
                'phrase1': full_puzzle['phrase1'],
                'phrase2': full_puzzle['phrase2'],
                'phrase3': full_puzzle['phrase3'],
                'explanation': full_puzzle.get('explanation', ''),
                'language': 'en',
                'difficulty': full_puzzle['difficulty'],
                'created_at': full_puzzle['created_at']
            }
        
        # 记录安全日志
        security_logger.warning(f"DEMO endpoint accessed | puzzle={full_puzzle['puzzle_id']} | answer_revealed='{full_puzzle['answer']}' | language={language}")
        
        return demo_response
    
    def clear_session(self, session_id: str):
        """
        清理游戏会话
        
        Args:
            session_id: 会话ID
        """
        logger.info(f"Clearing session | session_id={session_id}")
        
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.session_timestamps:
            del self.session_timestamps[session_id]
        if session_id in self.session_used_words:
            del self.session_used_words[session_id]
        
        logger.info(f"Session cleared | session_id={session_id}")
        return {'status': 'success', 'message': 'Session cleared'}

# 全局游戏服务实例
game_service = GameService()

