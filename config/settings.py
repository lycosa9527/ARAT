"""
配置管理
使用环境变量 + 缓存机制
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

# 配置单例类
class Config:
    _instance = None
    _cache = {}
    _cache_timestamp = 0
    _cache_duration = 300  # 5分钟缓存
    _version = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    @property
    def VERSION(self) -> str:
        """从VERSION文件读取版本"""
        if self._version is None:
            try:
                version_file = Path(__file__).parent.parent / 'VERSION'
                self._version = version_file.read_text().strip()
            except Exception:
                self._version = "0.1.0"
        return self._version
    
    def _get_cached_value(self, key: str, default=None):
        """缓存环境变量"""
        import time
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_duration:
            self._cache.clear()
            self._cache_timestamp = current_time
        if key not in self._cache:
            self._cache[key] = os.environ.get(key, default)
        return self._cache[key]
    
    # Server Configuration
    @property
    def HOST(self) -> str:
        return self._get_cached_value('HOST', '0.0.0.0')
    
    @property
    def PORT(self) -> int:
        try:
            return int(self._get_cached_value('PORT', '9528'))
        except ValueError:
            return 9528
    
    @property
    def DEBUG(self) -> bool:
        return self._get_cached_value('DEBUG', 'False').lower() == 'true'
    
    @property
    def EXTERNAL_HOST(self) -> str:
        return self._get_cached_value('EXTERNAL_HOST', 'localhost')
    
    @property
    def EXTERNAL_URL(self) -> str:
        """外部访问URL (用于分享功能)"""
        external_url = self._get_cached_value('EXTERNAL_URL', '')
        if external_url:
            return external_url
        # 自动构建URL
        protocol = 'https' if not self.DEBUG else 'http'
        host = self.EXTERNAL_HOST
        port = self.PORT
        if (protocol == 'http' and port == 80) or (protocol == 'https' and port == 443):
            return f"{protocol}://{host}"
        return f"{protocol}://{host}:{port}"
    
    # LLM Configuration
    @property
    def QWEN_API_KEY(self) -> str:
        return self._get_cached_value('QWEN_API_KEY', '')
    
    @property
    def QWEN_API_URL(self) -> str:
        return self._get_cached_value('QWEN_API_URL', 
            'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    
    @property
    def QWEN_MODEL_CLASSIFICATION(self) -> str:
        return self._get_cached_value('QWEN_MODEL_CLASSIFICATION', 'qwen-turbo')
    
    @property
    def QWEN_MODEL_GENERATION(self) -> str:
        return self._get_cached_value('QWEN_MODEL_GENERATION', 'qwen-plus')
    
    @property
    def DEEPSEEK_MODEL(self) -> str:
        return self._get_cached_value('DEEPSEEK_MODEL', 'deepseek-v3.1')
    
    @property
    def KIMI_MODEL(self) -> str:
        return self._get_cached_value('KIMI_MODEL', 'Moonshot-Kimi-K2-Instruct')
    
    @property
    def HUNYUAN_API_KEY(self) -> str:
        return self._get_cached_value('HUNYUAN_API_KEY', '')
    
    # Database
    @property
    def DATABASE_URL(self) -> str:
        return self._get_cached_value('DATABASE_URL', 'sqlite:///./wordbridge.db')
    
    # Logging
    @property
    def LOG_LEVEL(self) -> str:
        return self._get_cached_value('LOG_LEVEL', 'INFO')
    
    @property
    def VERBOSE_LOGGING(self) -> bool:
        return self._get_cached_value('VERBOSE_LOGGING', 'False').lower() == 'true'
    
    # Game Settings
    @property
    def GAME_TIME_LIMIT(self) -> int:
        try:
            return int(self._get_cached_value('GAME_TIME_LIMIT', '300'))
        except ValueError:
            return 300
    
    # Demo Mode Security
    @property
    def DEMO_PASSKEY(self) -> str:
        """Demo模式访问密钥 (6位数字)"""
        return self._get_cached_value('DEMO_PASSKEY', '888888')
    
    def validate_config(self) -> bool:
        """验证必要配置"""
        from config.logging_config import get_logger
        logger = get_logger('app')
        
        if not self.QWEN_API_KEY:
            logger.error("QWEN_API_KEY not configured")
            return False
        return True

# 全局配置实例
config = Config()

