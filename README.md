# 灵犀（Lingxi）— A股大白话量化回测系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

零门槛A股量化回测平台。**用大白话描述策略**，AI自动解析执行，秒级全市场回测。

> "MACD金叉买入，死叉卖出" → 一键回测 → 收益率 + 夏普比率 + 资金曲线

## 核心功能

| 功能 | 说明 |
|------|------|
| 🗣️ **大白话策略** | 自然语言描述，LLM自动解析为交易信号 |
| 📊 **经典策略回测** | 13个内置策略（MACD/KDJ/RSI/布林带/均线） |
| 🔍 **策略发现** | 69个技术信号 x 全市场，排名最优信号组合 |
| 🏥 **策略体检** | 信号触发率/胜率/年度分布，A股日历效应 |
| 📈 **模拟交易** | 虚拟账户 + 持仓跟踪 + 权益曲线 |
| 🔀 **策略对比** | 多策略同框对比，一键选最优 |
| 🎯 **网格搜索** | 参数空间遍历，热力图可视化最优参数 |
| 📄 **PDF报告** | 一键导出完整回测报告 |
| 🔐 **用户系统** | 注册/登录/JWT认证 |

## 技术架构

```
前端: Vite + React 18 + TypeScript + MUI + Tailwind CSS
后端: FastAPI + Pydantic + SQLAlchemy + akshare + pandas
AI: DeepSeek V3 (可切换 OpenAI)
数据: TDX本地 / akshare云端 / Parquet缓存 / Mock降级
部署: Docker + docker-compose + Nginx
```

### 数据降级链
```
TDX本地文件 → Parquet缓存 → akshare在线拉取 → Mock随机数据
(最快)                                (兜底永远不会空白)
```

## 快速启动

### Docker 一键部署（推荐）
```bash
cp .env.example .env  # 填写 JWT_SECRET_KEY 和 LLM_API_KEY
docker-compose up -d
# 访问 http://localhost:3000
```

### 本地开发
```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 项目结构

```
discoverer/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── models/              # Pydantic Schema + DB模型
│   ├── routers/             # API路由（14个端点）
│   ├── services/            # 核心服务（回测引擎/数据/LLM/信号）
│   └── tests/               # 集成测试
├── frontend/
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 通用组件
│   │   ├── hooks/           # API Hook
│   │   └── contexts/        # 认证/应用状态
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `JWT_SECRET_KEY` | JWT签名密钥 | 必须修改 |
| `LLM_API_KEY` | DeepSeek/OpenAI API Key | - |
| `LLM_BASE_URL` | LLM API地址 | `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `TDX_DATA_DIR` | 通达信数据路径 | `data/hsjday/hsjday` |

## 鸣谢

- [akshare](https://github.com/akfamily/akshare) — A股数据接口
- [FastAPI](https://fastapi.tiangolo.com/) — 后端框架
- [MUI](https://mui.com/) — React组件库
- [DeepSeek](https://deepseek.com/) — LLM服务

## License

MIT © 2026 灵犀（Lingxi）
