# Prompt Analyzer 技术使用手册

> 面向开发人员的部署、配置与使用指南

---

## 1. 项目简介

Prompt Analyzer 是一个全栈数据分析与可视化平台，用于分析 Tripo AI 3D 模型生成的 Prompt 数据。系统从 AWS Athena 获取原始数据，通过 NLP 与 Claude LLM 进行多维度分析，并通过交互式 Dashboard 展示分析结果。

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite + Ant Design + ECharts |
| 后端 | Python Flask + SQLite 缓存 |
| 数据源 | AWS Athena（查询 S3 上的 Tripo 数据） |
| AI 分析 | Claude API（意图分类、质量评估、主题总结） |
| NLP | scikit-learn（TF-IDF、LDA、t-SNE）、jieba（中文分词）、langdetect（语言检测） |

### 项目结构

```
prompt_analyzer/
├── backend/                  # Python Flask 后端
│   ├── app/
│   │   ├── config.py         # 配置管理
│   │   ├── routes/           # API 路由（data / analysis / pipeline）
│   │   ├── services/         # 核心服务（Athena / Cache / NLP / LLM / Pipeline）
│   │   └── utils/            # 工具函数
│   ├── cache/                # SQLite 缓存目录
│   ├── .env.example          # 环境变量模板
│   ├── requirements.txt      # Python 依赖
│   └── run.py                # 后端启动入口
│
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── pages/            # 7 个分析页面
│   │   ├── components/       # 通用组件（布局、图表、KPI 卡片）
│   │   ├── hooks/            # 数据请求 Hooks
│   │   ├── api/              # API 客户端与接口定义
│   │   └── types/            # TypeScript 类型定义
│   ├── package.json
│   └── vite.config.ts        # Vite 配置（含 API 代理）
│
└── docs/                     # 文档目录
```

---

## 2. 环境准备

### 前置依赖

- Python >= 3.10
- Node.js >= 18
- AWS CLI 已配置（需有 Athena 查询权限）
- Claude API Key

### 后端安装

```bash
cd backend
pip install -r requirements.txt
```

### 前端安装

```bash
cd frontend
npm install
```

---

## 3. 配置说明

### 环境变量

在 `backend/` 目录下创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# AWS 配置
AWS_REGION=us-west-2
ATHENA_WORKGROUP=data-agent
ATHENA_OUTPUT_LOCATION=s3://tripo-telescope/data-agent/athena-results/

# Claude API
CLAUDE_API_KEY=sk-ant-your-key-here

# 缓存
CACHE_DB_PATH=./cache/analysis_cache.db
```

### 高级配置

以下参数在 `backend/app/config.py` 中定义，可按需调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `cache_ttl_hours` | 24 | 缓存过期时间（小时） |
| `athena_query_timeout_sec` | 300 | Athena 查询超时（秒） |
| `athena_poll_interval_sec` | 1.5 | Athena 状态轮询间隔（秒） |
| `claude_model` | claude-sonnet-4-20250514 | Claude 模型版本 |
| `llm_sample_size` | 500 | 意图分类采样数量 |
| `llm_quality_sample_size` | 100 | 质量评估采样数量 |
| `topic_num_clusters` | 15 | LDA 主题聚类数 |

---

## 4. 启动服务

### 启动后端

```bash
cd backend
python run.py
```

后端运行在 `http://localhost:5000`。

### 启动前端

```bash
cd frontend
npm run dev
```

前端运行在 `http://localhost:3000`，自动代理 `/api/*` 到后端。

### 生产构建

```bash
cd frontend
npm run build    # 输出到 dist/
npm run preview  # 预览生产构建
```

---

## 5. 分析管线

系统核心是一个 9 步分析管线，通过后台线程异步执行：

| 步骤 | 名称 | 说明 | 依赖 |
|------|------|------|------|
| 1 | Data Fetch | 从缓存加载 Prompt 数据 | - |
| 2 | Language Detection | langdetect 识别每条 Prompt 的语言 | 步骤 1 |
| 3 | Text Statistics | 字符数、词数、词汇多样性等统计 | 步骤 1 |
| 4 | Keyword Extraction | TF-IDF 关键词提取（中文用 jieba） | 步骤 1 |
| 5 | Topic Modeling | LDA 主题建模 + t-SNE 2D 降维 | 步骤 1 |
| 6 | Trend Analysis | 热词趋势、日趋势、词云数据 | 步骤 1 |
| 7 | Intent Classification | Claude 将 Prompt 分为 10 类意图 | 步骤 1 |
| 8 | Quality Assessment | Claude 从 4 个维度评分（1-5） | 步骤 1 |
| 9 | Theme Summary | Claude 生成双语数据集总结 | 步骤 1-8 |

### 意图分类（10 类）

`character_design` / `creature_animal` / `vehicle_transport` / `architecture_scene` / `prop_item` / `weapon_armor` / `furniture_decor` / `food_nature` / `abstract_logo` / `other`

### 质量评估（4 维度）

`specificity`（具体性）/ `clarity`（清晰度）/ `creativity`（创造力）/ `technical_detail`（技术细节）

---

## 6. API 接口参考

### 数据接口

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| `GET` | `/api/data/summary` | 数据概览统计 | - |
| `GET` | `/api/data/prompts` | 分页查询 | `page`, `page_size`, `search`, `category`, `style`, `language` |
| `POST` | `/api/data/sync` | 从 Athena 同步数据 | - |
| `GET` | `/api/data/daily-counts` | 每日数据量 | - |
| `GET` | `/api/data/export` | CSV 导出 | - |

### 分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/analysis/categories` | 类别/风格/用途分布 |
| `GET` | `/api/analysis/topics` | 主题聚类 + 散点坐标 |
| `GET` | `/api/analysis/intents` | 意图分类分布 + 示例 |
| `GET` | `/api/analysis/language` | 语言分布 + 文本统计 + 质量评分 |
| `GET` | `/api/analysis/trends` | 热词趋势 + 日趋势 + 词云 |
| `GET` | `/api/analysis/keywords` | TF-IDF 关键词 |
| `GET` | `/api/analysis/theme-summary` | AI 生成的数据总结 |

### 管线接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/pipeline/run` | 启动分析管线 |
| `GET` | `/api/pipeline/status` | 查询管线状态与进度 |

---

## 7. 数据库结构

SQLite 缓存数据库包含以下表：

### prompts 表

存储从 Athena 同步的 Prompt 数据。

| 字段 | 说明 |
|------|------|
| `project_id` (PK) | 项目 ID |
| `user_id` | 用户 ID |
| `prompt` | 用户输入的 Prompt 文本 |
| `caption` | 标题 |
| `llm_keyword` / `llm_object` / `llm_category` / `llm_style` / `llm_color` / `llm_use_case` | LLM 标注的分类标签 |
| `from_type` | 来源类型 |
| `created_at` / `pt` | 创建时间 / 分区日期 |

### analysis_runs 表

记录管线执行历史。

### analysis_results 表

存储各步骤的分析结果（JSON 格式）。

---

## 8. 常见问题

**Q: Athena 查询超时？**
A: 调大 `athena_query_timeout_sec`，或检查 Athena Workgroup 配额。

**Q: LLM 分析成本如何控制？**
A: 通过 `llm_sample_size` 和 `llm_quality_sample_size` 限制采样数。默认 500+100 条，约消耗少量 Token。

**Q: 缓存数据如何强制刷新？**
A: 重新点击 "Sync Data" 即可覆盖缓存；或删除 `backend/cache/analysis_cache.db` 后重启。

**Q: 前端构建后如何部署？**
A: `npm run build` 生成 `dist/` 目录，可部署到任意静态文件服务器（Nginx、S3 等），后端 API 地址需在 `api/client.ts` 中配置。

**Q: 如何增加新的分析维度？**
A: 在 `backend/app/services/` 下新增 Service，在 `pipeline_service.py` 中注册步骤，前端新增对应页面即可。
