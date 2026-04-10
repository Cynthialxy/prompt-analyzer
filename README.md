# Tripo Prompt 分析平台

> 全栈数据分析与可视化平台，用于深度分析 Tripo AI 3D 模型生成服务中用户提交的 Prompt 数据

![Tech](https://img.shields.io/badge/Backend-Flask%20%7C%20Python%203.10%2B-blue)
![Tech](https://img.shields.io/badge/Frontend-React%2019%20%7C%20TypeScript-blue)
![Tech](https://img.shields.io/badge/Data-AWS%20Athena%20%7C%20SQLite-orange)
![Tech](https://img.shields.io/badge/AI-Claude%20API%20%7C%20FAISS-purple)

## 📖 简介

基于 AWS Athena 实时数据 + NLP + LLM 的 Prompt 分析平台，提供 11 个分析维度：

- **📊 总览** — 核心 KPI、AI 洞察、类别/语言分布、每日趋势
- **🏷️ 分类标签** — 类别/风格/用途/颜色分布 + 交叉热力图
- **🧩 主题聚类** — LDA + t-SNE 散点图
- **📈 趋势分析** — 每日量、类别趋势、热词、词云
- **🌍 语言与质量** — 多语言识别 + Prompt 质量评分
- **🎯 意图分析** — 基于语义的用户需求意图识别（6 大类/20 子类）
- **📋 数据浏览** — 可筛选分页的 Prompt 表格 + CSV 导出
- **🌿 创作路径** — 用户创作序列桑基图
- **⚡ 效果分析** — 爆款挖掘 + 特征-效果 Spearman 相关性
- **🗂️ 主题分析** — BERTopic/LDA 主题树图 + 效果散点图
- **🔥 爆款模板** — 高点赞 Prompt 模板挖掘与复用

## 🏗️ 架构

```
Browser (React 19 + ECharts)
    ↓ /api/*
Flask Backend (Python)
    ↓
AWS Athena (silver.clean_tripo_project)
    ↓
Claude API (意图/质量/洞察)
    ↓
FAISS (向量相似检索)
```

详见 [`docs/technical-design.md`](docs/technical-design.md)。

## 🚀 快速开始

### 前置依赖

- **Python 3.10+**
- **Node.js 18+**
- **AWS 账号**（需要访问 Athena 的 IAM 密钥）
- **Claude API Key**（或 API Router 代理）

### 1️⃣ 克隆项目

```bash
git clone <REPO_URL>
cd agents-d835735d71
```

### 2️⃣ 后端启动

```bash
cd backend

# 安装依赖
pip3 install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 用编辑器打开 .env 填入你的凭证（见下方说明）

# 启动服务
python3 run.py
```

后端运行在 `http://localhost:5000`。

#### `.env` 配置说明

```env
# AWS Athena
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=<你的 AWS Access Key>
AWS_SECRET_ACCESS_KEY=<你的 AWS Secret>
ATHENA_WORKGROUP=tripo-analyst
ATHENA_OUTPUT_LOCATION=s3://tripo-telescope/data-agent/athena-results/

# Claude API（可选，不填则 AI 洞察/质量评估不可用）
CLAUDE_API_KEY=<你的 Claude API Key>
CLAUDE_BASE_URL=https://co.yes.vg/team   # 如果用 API Router
CLAUDE_MODEL=claude-sonnet-4-6

# 本地缓存
CACHE_DB_PATH=./cache/analysis_cache.db
```

> 💡 AWS 凭证找团队管理员申请，Claude API Key 找平台管理员申请。

### 3️⃣ 前端启动

**新开一个终端窗口：**

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 `http://localhost:3000`，打开浏览器访问即可。

### 4️⃣ 首次使用流程

1. 打开 `http://localhost:3000`
2. 点击右上角「**同步数据**」按钮（从 Athena 拉取最近 7 天数据）
3. 点击「**运行分析**」按钮启动 22 步分析管线（约 5-10 分钟）
4. 管线完成后，浏览各个分析页面查看结果

## 📚 文档

- [`docs/technical-design.md`](docs/technical-design.md) — 完整技术设计文档（架构、API、数据模型、变更历史）
- [`docs/technical-guide.md`](docs/technical-guide.md) — 技术使用手册（部署、配置）
- [`docs/user-guide.md`](docs/user-guide.md) — 产品使用指南（面向领导/产品/运营）

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19 + TypeScript + Vite + Ant Design 6 + ECharts 5 + TanStack Query |
| 后端 | Flask + Python + Pydantic Settings |
| 数据 | AWS Athena（数据源）+ SQLite（本地缓存）|
| AI | Claude Sonnet 4.6 + sentence-transformers + FAISS |
| NLP | scikit-learn（TF-IDF/LDA/t-SNE）+ jieba + langdetect |
| 数据建模 | dbt（可选，Athena adapter）|

## 📁 目录结构

```
.
├── backend/                    # Flask 后端
│   ├── app/
│   │   ├── config.py          # 配置管理
│   │   ├── routes/            # API 路由
│   │   ├── services/          # 业务逻辑（13 个 service）
│   │   └── utils/             # 工具函数
│   ├── cache/                 # 本地 SQLite + FAISS 索引（gitignored）
│   ├── requirements.txt
│   └── run.py
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── pages/             # 11 个分析页面
│   │   ├── components/        # 共享组件
│   │   ├── api/               # API 客户端
│   │   ├── hooks/             # React Query hooks
│   │   └── types/             # TypeScript 类型
│   └── package.json
├── dbt_prompt_analyzer/        # dbt 数据模型（可选）
├── docs/                       # 项目文档
└── README.md
```

## ⚠️ 常见问题

**Q: 启动时报错 `ModuleNotFoundError`？**
A: 先执行 `pip3 install -r requirements.txt`。如遇到 `faiss-cpu`/`bertopic` 安装失败，这些是可选的（对应的 Prompt 相似检索和 BERTopic 功能会降级，其他功能正常）。

**Q: 页面显示空白或加载失败？**
A: 确保后端 `http://localhost:5000` 正常响应。浏览器打开 `http://localhost:5000/api/data/summary` 应返回 JSON。

**Q: Athena 查询超时？**
A: 检查 AWS 凭证和 Workgroup 名称是否正确。首次同步会拉取约 5 万条数据，约 30 秒。

**Q: AI 洞察 / 意图分析 / 质量雷达图没数据？**
A: 点击「运行分析」启动 Pipeline，等待约 5-10 分钟完成。如果 Claude API 不可用，NLP 相关模块仍可正常工作。

**Q: 如何更新数据？**
A: 点击右上角「同步数据」按钮即可重新从 Athena 拉取最新数据。

## 🤝 使用建议

- **产品/运营**：从「总览」→「意图分析」→「爆款模板」查看用户需求与高效果 Prompt
- **开发/技术**：从「数据浏览」→「主题聚类」→「效果分析」查看数据质量与特征相关性
- **管理层**：直接看「总览」的 AI 洞察和 KPI 卡片
