# WordBridge - 字词接龙游戏

<div align="center">

🎮 **Chinese Word Bridge Puzzle Game**  
使用LLM技术的智能字词接龙游戏

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-purple.svg)](LICENSE)

**Author**: lycosa9527 | **Team**: MindSpring Team

</div>

---

## 📖 项目简介

WordBridge 是一款创新的中文字词接龙游戏，通过多个大语言模型(LLM)生成智能题目，让玩家在游戏中学习和巩固中文词汇。

### 核心玩法

给定两个汉字，玩家需要输入第三个字，使其能够与前两个字分别组成有效的中文词语。

**示例**:
```
题目: 海 —— 拔
答案: 高

验证:
✓ 海拔 (地理术语)
✓ 拔高 (提升之意)
```

---

## ✨ 主要特性

- 🤖 **4-LLM支持**: 集成Qwen、DeepSeek、Kimi、Hunyuan四个大模型
- 🎯 **多难度等级**: 简单、中等、困难三档
- 💡 **智能提示系统**: 三级提示帮助玩家
- 🏆 **排行榜系统**: 全球/每日挑战排名
- ⚡ **高性能架构**: 支持4,000+并发连接
- 🔐 **安全认证**: JWT-based用户系统
- 📊 **性能监控**: LLM调用指标追踪

---

## 🏗️ 技术架构

### 技术栈

- **后端框架**: FastAPI + Uvicorn (ASGI)
- **异步编程**: asyncio + aiohttp
- **数据验证**: Pydantic v2
- **数据库**: SQLAlchemy + SQLite
- **认证**: python-jose (JWT)
- **LLM集成**: 4 Models (Dashscope API + Hunyuan)

### 架构特点

```
┌─────────────────────────────────────────┐
│         Frontend (Browser)              │
│         HTML + JavaScript               │
└────────────────┬────────────────────────┘
                 │ HTTP/REST API
┌────────────────▼────────────────────────┐
│      FastAPI Application (Async)        │
│  ┌───────────────────────────────────┐  │
│  │  Routers (API Endpoints)          │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│  ┌───────────▼───────────────────────┐  │
│  │  Services (Business Logic)        │  │
│  │  • GameService  • LLMService      │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│  ┌───────────▼───────────────────────┐  │
│  │  LLM Clients (Middleware)         │  │
│  │  Qwen | DeepSeek | Kimi | Hunyuan│  │
│  └───────────┬───────────────────────┘  │
└──────────────┼─────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼────┐ ┌──▼──┐ ┌────▼─────┐
│ SQLite │ │ LLM │ │  Logging │
│   DB   │ │ APIs│ │   Files  │
└────────┘ └─────┘ └──────────┘
```

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- pip 或 conda
- LLM API密钥 (Qwen/Dashscope)

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/wordbridge.git
cd wordbridge

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入你的API密钥

# 5. 初始化数据库
python -c "from config.database import init_db; init_db()"

# 6. 运行应用
python main.py
```

### 访问应用

打开浏览器访问: `http://localhost:9527`

---

## 📚 API文档

### 核心端点

#### 1. 生成新题目
```http
POST /api/game/new_puzzle
Content-Type: application/json

Request:
{
    "difficulty": "easy",
    "llm": "qwen"
}

Response:
{
    "puzzle_id": "puzzle_a1b2c3d4e5f6",
    "char1": "海",
    "char2": "拔",
    "difficulty": "easy",
    "created_at": 1704067200
}
```

#### 2. 验证答案
```http
POST /api/game/check_answer
Content-Type: application/json

Request:
{
    "puzzle_id": "puzzle_a1b2c3d4e5f6",
    "answer": "高",
    "time_taken": 15.5
}

Response:
{
    "correct": true,
    "word1": "海拔",
    "word2": "拔高",
    "word1_valid": true,
    "word2_valid": true,
    "explanation": "'海拔'是地理术语，'拔高'是提升的意思",
    "score": 10
}
```

#### 3. 获取提示
```http
POST /api/game/get_hint
Content-Type: application/json

Request:
{
    "puzzle_id": "puzzle_a1b2c3d4e5f6",
    "level": 1
}

Response:
{
    "hint": "这个字和高度、提升有关",
    "level": 1,
    "cost": 10
}
```

完整API文档: 访问 `http://localhost:9527/docs` (Swagger UI)

---

## 📁 项目结构

```
WordBridge/
├── clients/                # LLM客户端实现
│   ├── llm.py             # 多模型客户端
│   └── omni_client.py     # (可选)语音支持
├── config/                 # 配置管理
│   ├── settings.py        # 环境变量配置
│   └── database.py        # 数据库配置
├── models/                 # Pydantic数据模型
│   ├── requests.py        # 请求模型
│   ├── responses.py       # 响应模型
│   └── auth.py            # 认证模型
├── routers/                # FastAPI路由
│   ├── api.py             # 游戏API
│   ├── auth.py            # 认证路由
│   └── pages.py           # HTML页面
├── services/               # 业务逻辑层
│   ├── llm_service.py     # LLM中间件
│   └── game_service.py    # 游戏逻辑
├── prompts/                # LLM提示词
│   └── game_prompts.py    # 游戏提示词模板
├── static/                 # 静态资源
│   ├── css/
│   ├── js/
│   └── fonts/
├── templates/              # HTML模板
│   ├── index.html         # 游戏主页
│   └── auth.html          # 登录页
├── logs/                   # 日志目录
├── tests/                  # 测试文件
├── main.py                 # 应用入口
├── requirements.txt        # 依赖列表
├── .env                    # 环境变量
└── README.md               # 本文件
```

---

## 🎮 游戏规则

### 难度等级

| 难度 | 词语类型 | 基础分 | 示例 |
|------|---------|--------|------|
| 简单 | 日常常用词 | 10分 | 学-校-园 (学校、校园) |
| 中等 | 成语、常用词组 | 20分 | 天-地-人 (天地、地人) |
| 困难 | 文言、生僻词 | 30分 | 望-穿-秋 (望穿、穿秋) |

### 计分规则

```
基础分 = 难度对应分数
时间奖励 = max(0, 30 - 用时秒数)
连胜加成 = 1.0 + (连胜次数 × 0.1) [最高3倍]
提示扣分 = 提示等级 × 10

最终得分 = (基础分 + 时间奖励 - 提示扣分) × 连胜加成
```

### 提示系统

| 等级 | 扣分 | 内容示例 |
|------|------|---------|
| 1级 | 10分 | "这个字和地理概念有关" |
| 2级 | 20分 | "这个字的偏旁是'高'" |
| 3级 | 30分 | "答案是: A.高 B.低 C.大" |

---

## 🔧 配置说明

### 环境变量 (.env)

```bash
# Server Configuration
HOST=0.0.0.0
PORT=9527
DEBUG=True
EXTERNAL_HOST=localhost

# LLM Configuration
QWEN_API_KEY=your_api_key_here
QWEN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
QWEN_MODEL_CLASSIFICATION=qwen-turbo
QWEN_MODEL_GENERATION=qwen-plus
DEEPSEEK_MODEL=deepseek-v3.1
KIMI_MODEL=Moonshot-Kimi-K2-Instruct

# Hunyuan Configuration
HUNYUAN_API_KEY=your_hunyuan_key_here

# Database
DATABASE_URL=sqlite:///./wordbridge.db

# Security
SECRET_KEY=your_secret_key_here_generate_with_openssl
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Logging
LOG_LEVEL=INFO
VERBOSE_LOGGING=False

# Game Settings
GAME_TIME_LIMIT=30
HINT_COST_LEVEL1=10
HINT_COST_LEVEL2=20
HINT_COST_LEVEL3=30
```

---

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_game_service.py

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

---

## 📦 部署

### Docker部署

```bash
# 构建镜像
docker build -t wordbridge:latest .

# 运行容器
docker run -d \
  -p 9527:9527 \
  -e QWEN_API_KEY=your_key \
  -v $(pwd)/logs:/app/logs \
  --name wordbridge \
  wordbridge:latest
```

### Docker Compose

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 生产环境 (Gunicorn + Uvicorn)

```bash
# 安装Gunicorn
pip install gunicorn

# 启动应用 (4个worker)
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:9527 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log
```

---

## 🔒 安全性

### 已实现的安全措施

- ✅ JWT令牌认证
- ✅ 密码bcrypt加密
- ✅ SQL注入防护 (SQLAlchemy ORM)
- ✅ XSS防护 (Jinja2自动转义)
- ✅ CORS配置
- ✅ 请求速率限制

### 建议的额外措施

- [ ] HTTPS/TLS加密 (生产环境必需)
- [ ] API密钥轮换策略
- [ ] 用户输入验证和过滤
- [ ] DDoS防护 (使用Cloudflare等)
- [ ] 定期安全审计

---

## 📈 性能指标

### 设计目标

- **并发连接**: 4,000+ (参考MindGraph实测)
- **响应时间**: <2秒 (LLM调用)
- **可用性**: 99.9%
- **数据库查询**: <100ms

### 优化策略

1. **异步编程**: 全异步I/O操作
2. **连接池**: 复用HTTP连接
3. **缓存**: Redis缓存热点数据
4. **CDN**: 静态资源加速
5. **熔断器**: 防止级联失败

---

## 🤝 贡献指南

### 如何贡献

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 代码规范

- 遵循PEP 8
- 每个文件不超过500行 [[user_rule]]
- 添加类型注解
- 编写单元测试
- 更新文档

---

## 📝 开发路线图

### v0.1.0 (MVP)
- [x] 项目结构搭建
- [x] 基础游戏逻辑
- [x] LLM集成
- [x] 简单UI

### v0.2.0 (增强)
- [ ] 用户认证系统
- [ ] 排行榜功能
- [ ] 多难度等级
- [ ] 提示系统

### v0.3.0 (优化)
- [ ] 性能优化
- [ ] 缓存系统
- [ ] 管理后台
- [ ] 数据统计

### v1.0.0 (正式版)
- [ ] 移动端适配
- [ ] 社交功能
- [ ] 成就系统
- [ ] 国际化支持

---

## 🐛 常见问题

### Q: LLM返回的JSON格式不正确怎么办？
**A**: 在服务层添加清理函数处理响应:
```python
def clean_llm_response(response: str) -> str:
    response = response.strip()
    if response.startswith('```'):
        response = response.split('\n', 1)[1]
    if response.endswith('```'):
        response = response.rsplit('\n', 1)[0]
    return response.strip()
```

### Q: 如何提高LLM调用的成功率？
**A**: 
1. 实现重试机制 (3次)
2. 使用多模型failover
3. 降低temperature参数
4. 简化提示词

### Q: SQLite并发性能不足怎么办？
**A**: 
1. 开启WAL模式
2. 增加timeout时间
3. 考虑迁移到PostgreSQL

---

## 📄 许可证

本项目采用 **AGPLv3** 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 👥 作者与团队

**Author**: lycosa9527  
**Team**: MindSpring Team  
**参考项目**: [MindGraph](https://github.com/yourusername/mindgraph)

---

## 🙏 致谢

- FastAPI团队 - 优秀的Python Web框架
- Dashscope - 稳定的LLM API服务
- MindGraph项目 - 架构设计参考

---

## 📞 联系方式

- **Issue**: [GitHub Issues](https://github.com/yourusername/wordbridge/issues)
- **Email**: your-email@example.com
- **Discord**: [加入我们的社区](https://discord.gg/yourserver)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个Star！**

Made with ❤️ by MindSpring Team

</div>

