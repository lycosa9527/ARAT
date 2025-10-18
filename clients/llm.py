"""
LLM客户端 - 多模型支持
支持: Qwen, DeepSeek, Kimi, Hunyuan
"""

import asyncio
import aiohttp
import json
from typing import List, Dict

from config.settings import config
from config.logging_config import get_logger

logger = get_logger('llm')

class QwenClient:
    """Qwen LLM客户端"""
    
    def __init__(self, model_type='generation'):
        self.api_url = config.QWEN_API_URL
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # 增加超时时间以适应复杂请求
        self.model_type = model_type
        self.default_temperature = 0.9  # 增加温度以提高多样性
    
    async def chat_completion(self, messages: List[Dict], 
                             temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """
        聊天补全 (非流式)
        
        Args:
            messages: 消息列表 [{"role": "system/user", "content": "..."}]
            temperature: 温度参数 (0-1)
            max_tokens: 最大token数
        
        Returns:
            str: LLM响应内容
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            model_name = (config.QWEN_MODEL_CLASSIFICATION 
                         if self.model_type == 'classification' 
                         else config.QWEN_MODEL_GENERATION)
            
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.debug(f"Qwen API success | model={model_name} | tokens={len(content)}")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"Qwen API error {response.status}: {error_text}")
                        raise Exception(f"Qwen API error: {response.status}")
        
        except asyncio.TimeoutError:
            logger.error("Qwen API timeout")
            raise Exception("Qwen API timeout")
        except Exception as e:
            logger.error(f"Qwen API error: {e}")
            raise

# 全局客户端实例
qwen_generation_client = QwenClient(model_type='generation')
qwen_classification_client = QwenClient(model_type='classification')

# 可以添加其他LLM客户端 (DeepSeek, Kimi, Hunyuan)
# 这里为了简化，暂时只实现Qwen

