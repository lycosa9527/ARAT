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
from typing import Dict, Optional
from collections import deque

from services.llm_service import llm_service
from config.logging_config import get_logger

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
        
        # 队列锁 (防止并发问题)
        self.queue_lock = asyncio.Lock()
        
        # 清理任务引用
        self._cleanup_task = None
        
        logger.info("GameService initialized")
    
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
            
            # 更新时间戳
            self.session_timestamps[session_id] = time.time()
        
        # 生成第一题 (立即返回)
        first_puzzle = await self._generate_single_puzzle(difficulty, language, llm)
        
        # 将第一题加入队列
        async with self.queue_lock:
            self.active_sessions[session_id]['puzzle_queue'].append(first_puzzle)
        
        # 异步预生成5题 (catapult机制)
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
                
                puzzle = await self._generate_single_puzzle(difficulty, language, llm)
                
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
                session['llm']
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
    
    async def _generate_single_puzzle(self, difficulty: str, language: str, llm: str = "qwen") -> Dict:
        """
        生成单个题目
        
        Args:
            difficulty: 难度等级
            language: 语言模式
            llm: LLM模型
        
        Returns:
            Dict: 完整题目数据 (包含答案)
        """
        start_time = time.time()
        
        try:
            # 选择提示词和随机pattern
            import random
            if language == 'zh':
                pattern = random.choice([1, 2, 3])  # 随机选择pattern
                system_prompt = GENERATE_PUZZLE_SYSTEM_PROMPT_CHINESE
                user_prompt = f"请生成一个{difficulty}难度的中文字词接龙题目，使用Pattern {pattern}。记住要确保词汇多样性。"
            else:
                system_prompt = GENERATE_PUZZLE_SYSTEM_PROMPT_ENGLISH
                user_prompt = f"Generate an {difficulty} difficulty English word association puzzle. Remember to ensure vocabulary diversity."
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 调用LLM
            response = await llm_service.chat_completion(
                model=llm,
                messages=messages,
                temperature=0.9,  # 高温度以增加多样性
                max_tokens=2000
            )
            
            # 解析JSON
            puzzle_data = self._parse_llm_response(response, language)
            
            # 生成puzzle_id
            puzzle_id = f"puzzle_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # 构建完整题目数据
            full_puzzle = {
                'puzzle_id': puzzle_id,
                'difficulty': difficulty,
                'language': language,
                **puzzle_data,
                'created_at': int(time.time())
            }
            
            # 存储到全局缓存
            self.active_puzzles[puzzle_id] = full_puzzle
            
            duration = time.time() - start_time
            perf_logger.info(f"Puzzle generated | puzzle_id={puzzle_id} | duration={duration:.2f}s")
            
            return full_puzzle
        
        except Exception as e:
            logger.error(f"Failed to generate puzzle | difficulty={difficulty} | language={language} | error={e}")
            raise
    
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
            
            # 解析验证结果
            result = self._parse_llm_response(response, 'validation')
            
            logger.info(f"LLM validation result | puzzle_id={puzzle_id} | correct={result.get('correct', False)}")
            
            return {
                'correct': result.get('correct', False),
                'match_type': 'llm_verified' if result.get('correct', False) else 'incorrect',
                'reason': result.get('reason', '')
            }
        
        except Exception as e:
            logger.error(f"LLM validation failed | puzzle_id={puzzle_id} | error={e}")
            # 降级：只接受精确匹配
            return {
                'correct': False,
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
        
        logger.info(f"Session cleared | session_id={session_id}")
        return {'status': 'success', 'message': 'Session cleared'}

# 全局游戏服务实例
game_service = GameService()

