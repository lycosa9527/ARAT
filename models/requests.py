"""
Pydantic数据模型
用于API请求验证
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional

class SubmitScoreRequest(BaseModel):
    """提交成绩请求 - 简化计分系统（会话级别）"""
    captcha_id: str = Field(..., description="Captcha session ID")
    captcha: str = Field(..., min_length=4, max_length=4, description="4-character captcha code")
    nickname: str = Field(..., min_length=1, max_length=20, description="玩家昵称")
    school: Optional[str] = Field(None, max_length=50, description="学校名称(可选)")
    session_id: str = Field(..., description="游戏会话ID")
    correct_count: int = Field(..., ge=0, description="答对题数")
    total_score: int = Field(..., ge=0, description="总得分 (= correct_count * 2)")
    total_time: float = Field(..., ge=0, le=300, description="游戏总时长(秒)，应为~300s")
    difficulty: str = Field(..., description="难度等级")
    language: str = Field(default='zh', description="语言模式 (zh/en)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "nickname": "Player1",
                "school": "Beijing Normal University",
                "session_id": "session_1705650000_abc123",
                "correct_count": 25,
                "total_score": 50,
                "total_time": 300.0,
                "difficulty": "medium",
                "language": "zh",
                "captcha": "AB3D",
                "captcha_id": "captcha_1234567890_5678"
            }
        }

class StartSessionRequest(BaseModel):
    """开始游戏会话请求"""
    session_id: str = Field(..., description="游戏会话ID（前端生成）")
    difficulty: str = Field(default="easy", description="难度等级")
    language: str = Field(default="zh", description="语言模式 (zh/en)")
    llm: str = Field(default="qwen", description="LLM模型")

class NextPuzzleRequest(BaseModel):
    """获取下一题请求"""
    session_id: str = Field(..., description="游戏会话ID")
    difficulty: str = Field(default="easy", description="难度等级")
    language: str = Field(default="zh", description="语言模式 (zh/en)")
    llm: str = Field(default="qwen", description="LLM模型")

class ClearSessionRequest(BaseModel):
    """清理会话请求"""
    session_id: str = Field(..., description="游戏会话ID")

class ValidateAnswerRequest(BaseModel):
    """验证答案请求"""
    puzzle_id: str = Field(..., description="题目ID")
    answer: str = Field(..., min_length=1, max_length=50, description="用户答案")
    llm: str = Field(default="qwen", description="LLM模型")

class GetAnswerRequest(BaseModel):
    """获取题目答案请求 (用于跳过和Demo模式)"""
    puzzle_id: str = Field(..., description="题目ID")

class DemoPasskeyRequest(BaseModel):
    """Demo模式密钥验证请求 (参考MindGraph)"""
    passkey: str = Field(..., min_length=6, max_length=6, description="6位数字密钥")
    
    @field_validator('passkey')
    @classmethod
    def validate_passkey(cls, v):
        """验证6位数字密钥"""
        if not v.isdigit():
            raise ValueError("Passkey must contain only digits")
        if len(v) != 6:
            raise ValueError("Passkey must be exactly 6 digits")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "passkey": "888888"
            }
        }

