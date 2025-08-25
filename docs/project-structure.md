# 项目目录结构

```
trademe/
├── README.md                           # 项目说明文档
├── docker-compose.yml                  # Docker容器编排配置
├── .env.example                        # 环境变量示例文件
├── package.json                        # 根级项目配置
├── .gitignore                          # Git忽略文件
├── .github/                            # GitHub Actions配置
│   └── workflows/
│       ├── ci.yml                      # 持续集成
│       └── deploy.yml                  # 部署流水线
│
├── docs/                               # 项目文档
│   ├── project-structure.md            # 项目结构说明
│   ├── api-documentation.md            # API接口文档
│   ├── database-schema.md              # 数据库设计文档
│   ├── deployment-guide.md             # 部署指南
│   └── development-guide.md            # 开发指南
│
├── database/                           # 数据库相关
│   ├── init.sql                        # 数据库初始化脚本
│   ├── migrations/                     # 数据库迁移文件
│   └── seeds/                          # 测试数据
│
├── nginx/                              # Nginx配置
│   ├── nginx.conf                      # Nginx主配置
│   └── ssl/                           # SSL证书
│
├── scripts/                            # 工具脚本
│   ├── setup.sh                       # 项目初始化脚本
│   ├── deploy.sh                      # 部署脚本
│   └── backup.sh                      # 数据备份脚本
│
├── backend/                            # 后端服务
│   ├── shared/                         # 共享模块
│   │   ├── types/                      # 通用类型定义
│   │   ├── utils/                      # 工具函数
│   │   ├── constants/                  # 常量定义
│   │   └── validators/                 # 数据验证器
│   │
│   ├── user-service/                   # 用户服务 (Node.js)
│   │   ├── src/
│   │   │   ├── controllers/            # 控制器
│   │   │   │   ├── auth.controller.ts
│   │   │   │   ├── user.controller.ts
│   │   │   │   └── profile.controller.ts
│   │   │   ├── services/               # 业务逻辑服务
│   │   │   │   ├── auth.service.ts
│   │   │   │   ├── user.service.ts
│   │   │   │   ├── email.service.ts
│   │   │   │   └── jwt.service.ts
│   │   │   ├── middleware/             # 中间件
│   │   │   │   ├── auth.middleware.ts
│   │   │   │   ├── validation.middleware.ts
│   │   │   │   └── error.middleware.ts
│   │   │   ├── routes/                 # 路由定义
│   │   │   │   ├── auth.routes.ts
│   │   │   │   ├── user.routes.ts
│   │   │   │   └── index.ts
│   │   │   ├── models/                 # 数据模型
│   │   │   │   ├── user.model.ts
│   │   │   │   └── session.model.ts
│   │   │   ├── config/                 # 配置文件
│   │   │   │   ├── database.ts
│   │   │   │   ├── redis.ts
│   │   │   │   └── jwt.ts
│   │   │   ├── utils/                  # 工具函数
│   │   │   │   ├── encryption.ts
│   │   │   │   ├── validation.ts
│   │   │   │   └── logger.ts
│   │   │   └── app.ts                  # 应用入口
│   │   ├── prisma/                     # Prisma配置
│   │   │   ├── schema.prisma           # 数据库模式
│   │   │   └── seed.ts                 # 种子数据
│   │   ├── tests/                      # 测试文件
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── __mocks__/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── Dockerfile
│   │   └── .env.example
│   │
│   ├── trading-service/                # 交易服务 (Python)
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                 # FastAPI应用入口
│   │   │   ├── config/                 # 配置
│   │   │   │   ├── __init__.py
│   │   │   │   ├── settings.py
│   │   │   │   └── database.py
│   │   │   ├── api/                    # API路由
│   │   │   │   ├── __init__.py
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── strategies.py
│   │   │   │   │   ├── backtests.py
│   │   │   │   │   ├── trades.py
│   │   │   │   │   └── live_trading.py
│   │   │   │   └── deps.py             # 依赖注入
│   │   │   ├── core/                   # 核心业务逻辑
│   │   │   │   ├── __init__.py
│   │   │   │   ├── strategy_engine.py  # 策略引擎
│   │   │   │   ├── backtest_engine.py  # 回测引擎
│   │   │   │   ├── trading_engine.py   # 交易引擎
│   │   │   │   └── risk_manager.py     # 风控管理
│   │   │   ├── services/               # 服务层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── exchange_service.py # 交易所服务
│   │   │   │   ├── strategy_service.py # 策略服务
│   │   │   │   └── data_service.py     # 数据服务
│   │   │   ├── models/                 # 数据模型
│   │   │   │   ├── __init__.py
│   │   │   │   ├── strategy.py
│   │   │   │   ├── trade.py
│   │   │   │   └── backtest.py
│   │   │   ├── schemas/                # Pydantic模式
│   │   │   │   ├── __init__.py
│   │   │   │   ├── strategy.py
│   │   │   │   ├── trade.py
│   │   │   │   └── common.py
│   │   │   ├── strategies/             # 策略实现
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_strategy.py
│   │   │   │   ├── ema_cross.py
│   │   │   │   ├── rsi_strategy.py
│   │   │   │   └── bollinger_bands.py
│   │   │   ├── utils/                  # 工具函数
│   │   │   │   ├── __init__.py
│   │   │   │   ├── indicators.py       # 技术指标
│   │   │   │   ├── helpers.py
│   │   │   │   └── logger.py
│   │   │   └── tasks/                  # 异步任务
│   │   │       ├── __init__.py
│   │   │       ├── celery_app.py
│   │   │       └── trading_tasks.py
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── .env.example
│   │
│   ├── ai-service/                     # AI服务 (Python)
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── chat.py
│   │   │   │   │   ├── analysis.py
│   │   │   │   │   └── strategy_gen.py
│   │   │   ├── core/                   # AI核心逻辑
│   │   │   │   ├── llm_client.py       # LLM客户端
│   │   │   │   ├── strategy_generator.py # 策略生成
│   │   │   │   ├── trade_analyzer.py   # 交易分析
│   │   │   │   └── chat_handler.py     # 对话处理
│   │   │   ├── services/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   └── utils/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── .env.example
│   │
│   └── market-service/                 # 市场数据服务 (Python)
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── config/
│       │   ├── api/
│       │   │   ├── v1/
│       │   │   │   ├── market.py
│       │   │   │   ├── klines.py
│       │   │   │   └── ticker.py
│       │   ├── core/                   # 市场数据核心
│       │   │   ├── data_collector.py   # 数据采集器
│       │   │   ├── websocket_manager.py # WebSocket管理
│       │   │   └── data_processor.py   # 数据处理
│       │   ├── services/
│       │   ├── models/
│       │   ├── schemas/
│       │   └── utils/
│       ├── tests/
│       ├── requirements.txt
│       ├── Dockerfile
│       └── .env.example
│
├── frontend/                           # 前端应用 (Next.js + React)
│   ├── public/                         # 静态资源
│   │   ├── images/
│   │   ├── icons/
│   │   └── favicon.ico
│   ├── src/
│   │   ├── app/                        # Next.js App Router
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # 首页
│   │   │   ├── login/
│   │   │   │   └── page.tsx           # 登录页
│   │   │   ├── dashboard/             # 用户首页
│   │   │   │   └── page.tsx
│   │   │   ├── trading/               # 图表交易
│   │   │   │   └── page.tsx
│   │   │   ├── strategies/            # 策略交易
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── api-keys/              # API管理
│   │   │   │   └── page.tsx
│   │   │   ├── insights/              # 交易心得
│   │   │   │   └── page.tsx
│   │   │   ├── account/               # 账户中心
│   │   │   │   └── page.tsx
│   │   │   └── membership/            # 会员续费
│   │   │       └── page.tsx
│   │   ├── components/                # 组件库
│   │   │   ├── ui/                    # 基础UI组件
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   └── index.ts
│   │   │   ├── charts/                # 图表组件
│   │   │   │   ├── KlineChart.tsx
│   │   │   │   ├── PerformanceChart.tsx
│   │   │   │   └── index.ts
│   │   │   ├── forms/                 # 表单组件
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   ├── StrategyForm.tsx
│   │   │   │   └── index.ts
│   │   │   ├── layout/                # 布局组件
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Layout.tsx
│   │   │   │   └── index.ts
│   │   │   └── features/              # 功能组件
│   │   │       ├── trading/
│   │   │       ├── strategies/
│   │   │       ├── ai-chat/
│   │   │       └── index.ts
│   │   ├── hooks/                     # 自定义Hooks
│   │   │   ├── useAuth.ts
│   │   │   ├── useApi.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── index.ts
│   │   ├── lib/                       # 库和工具
│   │   │   ├── api.ts                 # API客户端
│   │   │   ├── auth.ts                # 认证工具
│   │   │   ├── utils.ts               # 工具函数
│   │   │   ├── constants.ts           # 常量
│   │   │   └── types.ts               # 类型定义
│   │   ├── store/                     # 状态管理
│   │   │   ├── auth.store.ts
│   │   │   ├── trading.store.ts
│   │   │   ├── ui.store.ts
│   │   │   └── index.ts
│   │   └── styles/                    # 样式文件
│   │       ├── globals.css
│   │       └── components.css
│   ├── tests/                         # 测试文件
│   │   ├── __tests__/
│   │   ├── __mocks__/
│   │   └── setup.ts
│   ├── .storybook/                    # Storybook配置
│   ├── next.config.js                 # Next.js配置
│   ├── tailwind.config.js             # Tailwind配置
│   ├── package.json
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── .env.example
│
└── logs/                              # 日志文件
    ├── user-service.log
    ├── trading-service.log
    ├── ai-service.log
    └── market-service.log
```

## 目录说明

### 后端服务架构

1. **user-service**: Node.js + TypeScript + Express
   - 负责用户认证、权限管理、用户信息管理
   - 使用Prisma ORM连接MySQL数据库
   - JWT令牌管理和会话处理

2. **trading-service**: Python + FastAPI
   - 策略管理、回测引擎、实盘交易执行
   - 集成多个交易所API (CCXT)
   - 复杂的数据处理和计算任务

3. **ai-service**: Python + FastAPI + LangChain
   - AI对话、策略生成、智能分析
   - 集成OpenAI GPT和其他AI服务
   - 自然语言处理和代码生成

4. **market-service**: Python + FastAPI + WebSocket
   - 实时行情数据采集和分发
   - 历史数据管理和查询
   - WebSocket连接管理

### 前端应用架构

- **Next.js 14** with App Router
- **TypeScript** 类型安全
- **Tailwind CSS** 样式框架
- **Zustand** 状态管理
- **TanStack Query** 数据获取和缓存
- **ECharts** 图表可视化

### 开发工具和配置

- **Docker** 容器化部署
- **Nginx** 反向代理和负载均衡
- **GitHub Actions** CI/CD自动化
- **ESLint + Prettier** 代码规范
- **Jest** 单元测试
- **Storybook** 组件文档

此架构支持：
- 微服务独立开发和部署
- 水平扩展能力
- 服务间解耦
- 高可用性和容错能力
- 完整的开发工具链