"""
LLM服务中间件
功能: 重试、性能追踪、错误处理
"""

import asyncio
import time
import json
from typing import Dict, List
from collections import defaultdict

from clients.llm import qwen_generation_client, qwen_classification_client
from config.logging_config import get_logger, log_llm_call

logger = get_logger('llm')
app_logger = get_logger('app')

class LLMService:
    """LLM统一服务层"""
    
    def __init__(self):
        self.clients = {
            'qwen': qwen_generation_client,
            'qwen_generation': qwen_generation_client,
            'qwen_classification': qwen_classification_client
        }
        
        # 性能指标
        self.metrics = defaultdict(lambda: {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_time': 0
        })
    
    async def chat_completion(self, model: str, messages: List[Dict], 
                             temperature: float = None,
                             max_tokens: int = 2000,
                             retries: int = 3) -> str:
        """
        调用LLM (带重试逻辑)
        
        Args:
            model: 'qwen', 'qwen_generation', 'qwen_classification'
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            retries: 重试次数
        """
        client = self.clients.get(model)
        if not client:
            logger.error(f"Unknown model: {model}")
            # 降级到默认模型
            client = self.clients['qwen']
            app_logger.warning(f"Unknown model {model}, falling back to qwen")
        
        # 记录指标
        self.metrics[model]['total_requests'] += 1
        start_time = time.time()
        
        for attempt in range(retries):
            try:
                result = await client.chat_completion(messages, temperature, max_tokens)
                
                # 成功
                duration = time.time() - start_time
                self.metrics[model]['successful_requests'] += 1
                self.metrics[model]['total_time'] += duration
                
                logger.info(f"LLM call success | model={model} | duration={duration:.2f}s | attempt={attempt + 1}")
                return result
            
            except Exception as e:
                logger.warning(f"LLM call failed | model={model} | attempt={attempt + 1} | error={str(e)}")
                
                if attempt < retries - 1:
                    # 指数退避
                    await asyncio.sleep(2 ** attempt)
                else:
                    # 最后一次失败
                    self.metrics[model]['failed_requests'] += 1
                    logger.error(f"LLM call final failure | model={model} | attempts={retries}")
                    raise
        
        raise Exception(f"LLM {model} failed after {retries} attempts")
    
    def get_performance_metrics(self, model: str = None) -> Dict:
        """获取性能指标"""
        if model:
            return self.metrics.get(model, {})
        return dict(self.metrics)

# 全局服务实例
llm_service = LLMService()

