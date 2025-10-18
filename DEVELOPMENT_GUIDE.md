# ARAT - 字词接龙游戏 - 开发文档
## ARAT - Chinese Word Bridge Game - Development Documentation

**项目名称**: ARAT (字词接龙)  
**技术栈**: FastAPI + Uvicorn + Qwen LLM  
**作者**: lyc9527  
**团队**: MTEL Team from Educational Technology, Beijing Normal University  
**版本**: 0.1.0  
**状态**: ✅ Production Ready

---

## 📋 目录 | Table of Contents

1. [项目概述](#项目概述)
2. [架构设计](#架构设计)
3. [核心功能](#核心功能)
4. [API参考](#api参考)
5. [配置说明](#配置说明)
6. [部署指南](#部署指南)
7. [开发指南](#开发指南)

---

## 项目概述

ARAT是一个面向K12教育的中英文字词接龙游戏，使用LLM技术生成题目并验证答案。

### 主要特性

- 🎮 **双语支持**: 中文(2+1)和英文(3+1)游戏模式
- 🎯 **4级难度**: 小学/初中/高中/大学难度分级
- ⚡ **零等待体验**: Catapult预生成机制，题目即时加载
- 🤖 **智能验证**: 精确匹配 + LLM验证支持多答案
- 🔒 **安全防护**: 图片验证码、速率限制、Demo密钥保护
- 📊 **专业日志**: 7个独立日志文件，彩色控制台输出
- 💾 **用户友好**: localStorage持久化用户信息
- 🏆 **排行榜**: 支持全榜/周榜/日榜，可选学校信息

---

## 架构设计

### 技术栈

```
Frontend:  Vanilla JS + CSS3 + HTML5
Backend:   FastAPI + SQLAlchemy + SQLite
LLM:       Qwen (通义千问) API
Logging:   Python logging + 多文件轮转
Captcha:   captcha + PIL + 自定义字体
```

### 项目结构

```
ARAT/
├── config/                # 配置模块
│   ├── settings.py        # 环境变量管理
│   ├── database.py        # 数据库配置
│   └── logging_config.py  # 专业日志系统
├── models/                # 数据模型
│   └── requests.py        # Pydantic验证模型
├── services/              # 业务逻辑
│   ├── game_service.py    # 游戏核心逻辑 + Catapult
│   ├── llm_service.py     # LLM中间件
│   └── captcha_service.py # 验证码服务
├── clients/               # LLM客户端
│   └── llm.py             # Qwen客户端
├── routers/               # API路由
│   ├── api.py             # 游戏API
│   └── pages.py           # 页面路由
├── middleware/            # 中间件
│   ├── logging_middleware.py  # 访问日志
│   └── security_middleware.py # 安全头
├── templates/             # HTML模板
│   └── index.html         # 主页面
├── static/                # 静态资源
│   ├── css/styles.css     # 样式表
│   ├── js/game.js         # 游戏逻辑
│   ├── js/i18n.js         # 国际化
│   ├── fonts/inter-700.ttf # 验证码字体
│   └── favicon.svg        # 黑猫图标 🐱
├── logs/                  # 日志文件 (自动生成)
├── main.py                # 应用入口
├── .env                   # 环境配置
└── requirements.txt       # 依赖清单
```

---

## 核心功能

### 1. Catapult预生成机制

```python
# 游戏开始时
1. 立即生成第1题 → 返回给用户
2. 后台异步生成5题 → 加入队列

# 用户答题时
1. 从队列取题 (0ms等待)
2. 若队列<3题 → 触发补充生成
```

**优势**: 用户体验零等待，题目源源不断

### 2. 智能答案验证

```python
# 两步验证流程
Step 1: 精确匹配 (快速路径)
  - 用户答案 == 标准答案
  - 响应时间: <10ms
  - 无LLM调用

Step 2: LLM验证 (支持多答案)
  - 调用LLM判断答案合理性
  - 支持一题多解
  - 响应时间: ~2s
```

### 3. 会话管理

```python
# 会话生命周期
Start:  用户点击"开始游戏"
Active: 5分钟游戏时间
End:    用户提交成绩 OR 时间到
TTL:    10分钟自动清理过期会话
```

### 4. 安全机制

- **图片验证码**: 自定义字体，2分钟有效期，最多3次尝试
- **速率限制**: 每分钟最多10次验证码/5次提交
- **Demo保护**: 6位数字密钥 (默认888888)
- **分数验证**: 后端校验 `total_score == correct_count * 2`

---

## API参考

### 游戏API

#### 1. 开始游戏会话
```http
POST /api/game/start_session
Content-Type: application/json

{
  "session_id": "session_1234567890_abc",
  "difficulty": "easy",
  "language": "zh",
  "llm": "qwen"
}

Response 200:
{
  "status": "success",
  "message": "Game session started",
  "first_puzzle": {
    "puzzle_id": "puzzle_123",
    "char1": "学",
    "char2": "园",
    "language": "zh",
    "difficulty": "easy"
  }
}
```

#### 2. 获取下一题
```http
POST /api/game/next_puzzle
Content-Type: application/json

{
  "session_id": "session_1234567890_abc"
}

Response 200:
{
  "puzzle_id": "puzzle_124",
  "char1": "天",
  "char2": "地",
  "language": "zh",
  "difficulty": "easy"
}
```

#### 3. 验证答案
```http
POST /api/game/validate
Content-Type: application/json

{
  "puzzle_id": "puzzle_123",
  "answer": "校",
  "llm": "qwen"
}

Response 200:
{
  "correct": true,
  "match_type": "exact",  // or "llm_verified" or "incorrect"
  "reason": "答案完全正确"
}
```

#### 4. Demo端点 (需要密钥)
```http
GET /api/game/demo?passkey=888888&difficulty=easy&language=zh

Response 200:
{
  "puzzle_id": "demo_puzzle_123",
  "char1": "学",
  "char2": "园",
  "answer": "校",  // ⚠️ Demo模式显示答案
  "word1": "学校",
  "word2": "校园",
  "explanation": "学校和校园都是常见词汇"
}
```

### 验证码API

#### 生成验证码
```http
GET /api/captcha/generate

Response 200:
{
  "captcha_id": "captcha_1234567890_xyz",
  "image": "data:image/png;base64,..."
}
```

### 成绩API

#### 提交成绩
```http
POST /api/game/submit_score
Content-Type: application/json

{
  "captcha_id": "captcha_1234567890_xyz",
  "captcha": "AB3D",
  "nickname": "Player1",
  "school": "Beijing Normal University",
  "session_id": "session_1234567890_abc",
  "correct_count": 25,
  "total_score": 50,
  "total_time": 300.0,
  "difficulty": "medium",
  "language": "zh"
}
```

#### 获取排行榜
```http
GET /api/leaderboard?period=weekly&limit=100

Response 200:
{
  "period": "weekly",
  "total_entries": 50,
  "leaderboard": [
    {
      "rank": 1,
      "player_name": "Player1",
      "school_name": "Beijing Normal University",
      "best_score": 60,
      "games_played": 5
    }
  ]
}
```

### 系统API

#### 健康检查
```http
GET /api/health

Response 200:
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-10-17T22:24:25",
  "service": "ARAT-Word-Bridge-Game"
}
```

---

## 配置说明

### 环境变量 (.env)

```bash
# 服务器配置
HOST=0.0.0.0
PORT=9528
DEBUG=True
EXTERNAL_HOST=localhost

# LLM配置 (必需)
QWEN_API_KEY=sk-your-key-here
QWEN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
QWEN_MODEL_CLASSIFICATION=qwen-turbo
QWEN_MODEL_GENERATION=qwen-plus

# 数据库
DATABASE_URL=sqlite:///./wordbridge.db

# 日志
LOG_LEVEL=INFO
VERBOSE_LOGGING=False

# 游戏设置
GAME_TIME_LIMIT=300  # 5分钟

# Demo模式保护
DEMO_PASSKEY=888888  # 生产环境请修改
```

### 难度配置

在 `services/game_service.py` 中的提示词定义:

- **easy**: 小学词汇 (日常用语)
- **medium**: 初中词汇 (成语、常用词组)
- **hard**: 高中词汇 (文言词汇、深层成语)
- **professional**: 大学词汇 (高级词汇、文化词语)

---

## 部署指南

### 本地开发

```bash
# 1. 克隆项目
cd ARAT

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入QWEN_API_KEY

# 4. 运行应用
python main.py

# 5. 访问应用
# 浏览器打开: http://localhost:9528
```

### 生产部署

```bash
# 1. 更新配置
DEBUG=False
DEMO_PASSKEY=your-secure-passkey

# 2. 使用Uvicorn (单进程)
uvicorn main:app --host 0.0.0.0 --port 9528 --workers 1

# 3. 或使用Gunicorn (多进程)
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9528

# 4. 配置反向代理 (Nginx)
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:9528;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static {
        alias /path/to/ARAT/static;
    }
}
```

---

## 开发指南

### 添加新LLM提供商

1. 在 `clients/llm.py` 中添加新客户端类
2. 在 `services/llm_service.py` 中注册客户端
3. 更新 `.env` 添加API配置

### 修改游戏规则

编辑 `services/game_service.py`:
- 修改 `GENERATE_PUZZLE_SYSTEM_PROMPT_*` 调整题目生成逻辑
- 修改 `VALIDATE_ANSWER_PROMPT_*` 调整答案验证逻辑
- 修改难度描述文字

### 自定义UI

编辑 `static/css/styles.css`:
- CSS变量在 `:root` 中定义
- 修改 `--primary-gradient` 等变量更改主题色
- 修改 `.word-box` 样式更改题目框样式

### 添加新语言

1. 在 `static/js/i18n.js` 添加翻译字典
2. 在 `services/game_service.py` 添加对应语言的提示词
3. 更新前端支持新语言切换

---

## 日志系统

### 日志文件说明

```
logs/
├── app.log          # 主应用日志 (INFO+)
├── error.log        # 错误日志 (ERROR+)
├── llm.log          # LLM调用日志 (JSON格式)
├── security.log     # 安全事件日志 (验证码、限流)
├── access.log       # API访问日志 (JSON格式)
├── performance.log  # 性能监控日志 (JSON格式)
└── database.log     # 数据库操作日志
```

### 日志级别

- **DEBUG**: 详细调试信息
- **INFO**: 一般信息 (默认)
- **WARNING**: 警告信息 (如速率限制触发)
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

### 查看日志

```bash
# 实时查看应用日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 查看LLM调用记录
cat logs/llm.log | jq '.'

# 查看安全事件
grep "Rate limit" logs/security.log
```

---

## 性能优化

### Catapult机制优化

- **队列大小**: 默认6题 (可调整)
- **预生成触发**: 队列<3题时触发
- **并发控制**: `asyncio.Lock()` 防止竞争
- **会话清理**: 10分钟TTL自动清理

### 数据库优化

- **索引**: session_id, player_name, created_at
- **查询优化**: 使用聚合查询减少数据传输
- **连接池**: SQLAlchemy自动管理

### 缓存策略

- **localStorage**: 用户昵称和学校信息
- **内存缓存**: 活跃题目和会话数据
- **LLM响应**: 不缓存 (保证多样性)

---

## 故障排查

### 常见问题

#### 1. LLM API 401错误
```
错误: Qwen API error: 401
解决: 检查.env中的QWEN_API_KEY是否正确
```

#### 2. 验证码不显示
```
错误: Failed to generate captcha
解决: 确保static/fonts/inter-700.ttf存在
```

#### 3. 数据库连接失败
```
错误: Database initialization failed
解决: 检查DATABASE_URL配置，确保有写入权限
```

#### 4. Demo端点401错误
```
错误: Invalid passkey
解决: 检查URL中的passkey参数是否为888888
```

---

## 安全建议

### 生产环境

1. **更改密钥**
   ```bash
   DEMO_PASSKEY=您的6位数字密钥
   ```

2. **禁用DEBUG模式**
   ```bash
   DEBUG=False
   ```

3. **配置CORS**
   ```python
   # main.py
   allow_origins=["https://yourdomain.com"]  # 替换为实际域名
   ```

4. **使用HTTPS**
   ```nginx
   # Nginx配置
   listen 443 ssl;
   ssl_certificate /path/to/cert.pem;
   ssl_certificate_key /path/to/key.pem;
   ```

5. **设置速率限制**
   - 验证码: 10次/分钟
   - 成绩提交: 5次/5分钟
   - API调用: 可配置

---

## 许可与致谢

**Author**: lyc9527  
**Team**: MTEL Team  
**Institution**: Educational Technology, Beijing Normal University

**License**: 请联系团队获取授权

**参考项目**: MindGraph (Multi-LLM Diagram Generation)

---

## 更新日志

### v0.1.0 (2025-10-17)
- ✅ 初始版本发布
- ✅ 双语支持 (中文/英文)
- ✅ 4级难度系统
- ✅ Catapult预生成机制
- ✅ 智能答案验证
- ✅ 专业日志系统
- ✅ 安全防护 (验证码/限流/密钥)
- ✅ 排行榜系统
- ✅ localStorage用户持久化
- ✅ 黑猫Favicon 🐱
- ✅ 跳过功能 (取代提示按钮)

---

## 支持与反馈

如有问题或建议，请联系开发团队:
- **Email**: [团队邮箱]
- **GitHub**: [项目地址]
- **文档**: 本文件

---

**Made with ❤️ by MTEL Team**
