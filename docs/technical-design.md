# Tripo Prompt 分析平台 —— 技术设计文档

> 最后更新：2026-04-09
> 版本：v3.0（Phase 3 完整上线）

---

## 1. 项目简介

### 1.1 背景
Tripo Prompt 分析平台是一个全栈数据分析与可视化系统，用于深度分析 Tripo AI 3D 模型生成服务中用户提交的 Prompt 数据。平台从 AWS Athena 实时拉取数据，通过 NLP、LLM、向量嵌入等技术进行多维度分析，为产品、运营、管理层提供数据驱动的洞察。

### 1.2 核心能力（截至 v3.0）
- **基础分析**：类别/风格分布
、语言检测、文本统计、TF-IDF 关键词
- **主题建模**：LDA + t-SNE 散点图，可升级为 BERTopic
- **LLM 智能分析**：意图分类（10 类 + 子类）、质量评估（5 维度）、优化建议生成
- **用户分析**：分层（power_user/regular/casual/churned）、画像、留存 Cohort
- **Prompt 深度分析**：向量相似检索（FAISS/pgvector）、单条 Prompt 诊断
- **效果分析**：爆款挖掘、特征-效果相关性、爆款模板合成
- **创作路径**：桑基图 + 序列挖掘 + 类别迁移
- **性能优化**：前后端双层缓存、异步 Pipeline、Redis 热缓存、Celery 异步任务

---

## 2. 技术架构

### 2.1 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                         Browser (React 19)                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  11 个分析页面 + Prompt 详情页                               │  │
│  │  React Router v7 · Ant Design 6 · ECharts 5                 │  │
│  │  React Query（staleTime 10~60min 分级缓存）                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP (/api/* 代理)
┌──────────────────────────────▼───────────────────────────────────┐
│                     Flask Backend (Python)                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Routes: /api/data · /api/analysis · /api/v1/analysis       │  │
│  │          /api/pipeline                                      │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  Services（13 个）：                                          │  │
│  │   基础：cache / athena / nlp / llm / pipeline                │  │
│  │   Phase 1：user / embedding / effect / query_cache           │  │
│  │   Phase 2：retention / path / bertopic / template            │  │
│  │   Phase 3：pg / redis_cache / celery_config                  │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │  Query Cache（内存，10min TTL）+ 22 步 Pipeline               │  │
│  └──────────┬───────────┬──────────┬──────────┬────────────────┘  │
└─────────────┼───────────┼──────────┼──────────┼────────────────────┘
              │           │          │          │
       AWS Athena    SQLite      FAISS/      Claude API
   (silver.*)    (本地缓存)  pgvector  (via API Router)
                              (向量)
              │
         Redis (可选：热缓存 + Celery 队列)
```

### 2.2 目录结构

```
prompt_analyzer/
├── backend/                          # Flask 后端
│   ├── app/
│   │   ├── __init__.py               # App factory + 蓝图注册
│   │   ├── config.py                 # Pydantic Settings
│   │   ├── celery_config.py          # Celery 任务定义（Phase 3）
│   │   ├── routes/
│   │   │   ├── data.py               # 数据接口
│   │   │   ├── analysis.py           # 原版分析接口
│   │   │   ├── analysis_v1.py        # V1 升级接口（10 个端点）
│   │   │   └── pipeline.py           # Pipeline 控制
│   │   ├── services/
│   │   │   ├── cache_service.py      # SQLite 缓存
│   │   │   ├── athena_service.py     # Athena 查询
│   │   │   ├── query_cache.py        # 内存查询缓存
│   │   │   ├── nlp_service.py        # NLP 分析（LDA/TF-IDF）
│   │   │   ├── llm_service.py        # Claude API
│   │   │   ├── pipeline_service.py   # 22 步 Pipeline 编排
│   │   │   ├── user_service.py       # 用户分层 + 画像
│   │   │   ├── embedding_service.py  # FAISS 向量索引
│   │   │   ├── effect_service.py     # 效果分析
│   │   │   ├── retention_service.py  # 留存 Cohort
│   │   │   ├── path_service.py       # 创作路径
│   │   │   ├── bertopic_service.py   # BERTopic 主题
│   │   │   ├── template_service.py   # 爆款模板
│   │   │   ├── pg_service.py         # PostgreSQL + pgvector
│   │   │   └── redis_cache.py        # Redis 缓存
│   │   └── utils/
│   │       └── text_utils.py
│   ├── cache/                        # SQLite + FAISS 索引
│   ├── pgvector_init.sql             # PG 初始化脚本
│   ├── requirements.txt
│   ├── run.py
│   └── .env                          # 环境变量（AWS/Claude/PG/Redis）
│
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts             # Axios
│   │   │   └── endpoints.ts          # 所有 API 函数
│   │   ├── hooks/
│   │   │   └── useAnalysisData.ts    # React Query hooks + 缓存策略
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx     # 总览
│   │   │   ├── CategoryPage.tsx      # 分类标签
│   │   │   ├── TopicPage.tsx         # 主题聚类（LDA）
│   │   │   ├── TrendPage.tsx         # 趋势分析
│   │   │   ├── LanguagePage.tsx      # 语言与质量
│   │   │   ├── IntentPage.tsx        # 意图分析
│   │   │   ├── ExplorerPage.tsx      # 数据浏览
│   │   │   ├── PromptDetailPage.tsx  # Prompt 详情
│   │   │   ├── UserProfilePage.tsx   # 用户画像（已隐藏）
│   │   │   ├── UserRetentionPage.tsx # 用户留存（已隐藏）
│   │   │   ├── UserPathPage.tsx      # 创作路径
│   │   │   ├── EffectAnalysisPage.tsx # 效果分析
│   │   │   ├── TopicAnalysisPage.tsx # 主题分析（BERTopic）
│   │   │   └── TemplateMarketPage.tsx # 爆款模板
│   │   ├── components/
│   │   │   ├── layout/AppLayout.tsx  # 侧边栏 + 顶栏
│   │   │   ├── common/KpiCard.tsx
│   │   │   └── charts/EChartsWrapper.tsx
│   │   ├── types/index.ts            # 所有 TypeScript 接口
│   │   └── App.tsx                   # 路由
│   └── package.json
│
├── dbt_prompt_analyzer/              # dbt 数据模型
│   ├── dbt_project.yml
│   ├── profiles.yml                  # Athena 连接
│   └── models/
│       ├── staging/
│       │   ├── stg_prompts.sql
│       │   └── schema.yml
│       ├── intermediate/
│       │   └── int_user_activity.sql
│       └── marts/
│           ├── user_mart.sql
│           ├── prompt_mart.sql
│           ├── topic_mart.sql
│           ├── template_mart.sql
│           └── effect_mart.sql
│
└── docs/
    ├── technical-guide.md            # 技术手册（给开发）
    ├── technical-design.md           # 本文件（设计 + 变更历史）
    └── user-guide.md                 # 使用手册（给领导/运营）
```

### 2.3 技术栈

| 层 | 技术 | 版本 | 用途 |
|----|------|------|------|
| 前端框架 | React | 19 | UI |
| 路由 | react-router-dom | 7 | SPA 路由 |
| 组件库 | Ant Design | 6 | UI 组件 |
| 图表 | ECharts | 5.6 | 可视化 |
| 状态/请求 | TanStack Query | 5 | 数据请求 + 缓存 |
| HTTP | Axios | 1.14 | API 客户端 |
| 构建 | Vite | 8 | 开发/打包 |
| 后端框架 | Flask | 3.0 | Web 服务 |
| 配置 | pydantic-settings | 2.1 | 环境变量 |
| 数据湖 | AWS Athena | - | S3 上 Tripo 数据 |
| AWS SDK | boto3 | 1.34 | Athena 查询 |
| 本地缓存 | SQLite | 3 | 离线分析缓存 |
| LLM | Claude Sonnet 4.6 | via API Router | 意图分类、质量评估 |
| LLM SDK | anthropic | 0.40 | Claude SDK |
| NLP | scikit-learn | 1.4 | TF-IDF / LDA / t-SNE |
| 中文分词 | jieba | 0.42 | - |
| 语言检测 | langdetect | 1.0.9 | - |
| 向量搜索 | FAISS | 1.7 | 本地向量索引 |
| 嵌入模型 | sentence-transformers | 2.2 | all-MiniLM-L6-v2 (384 维) |
| 统计 | scipy | 1.11 | 相关性分析 |
| 主题模型 | BERTopic | 0.16 | 高级主题（Phase 2+） |
| 降维 | umap-learn | 0.5 | - |
| 聚类 | hdbscan | 0.8 | - |
| 向量数据库 | pgvector | 0.2 | 生产级向量（Phase 3） |
| 缓存 | Redis | 5.0 | 热数据缓存（Phase 3） |
| 任务队列 | Celery | 5.3 | 异步任务（Phase 3） |
| 数据建模 | dbt | 1.7+ | 分层数据模型 |

---

## 3. 核心模块设计

### 3.1 数据同步
- **入口**：`POST /api/data/sync` → `athena_service.fetch_and_cache_prompts()`
- **策略**：默认同步最近 7 天、最多 5 万条，避免全表扫描（原始表 1750 万+ 条）
- **字段**：project_id, user_id, prompt, caption, name, llm_*, from_type, status, visibility, display_image, like_count, collect_count, score, created_at, pt
- **落地**：SQLite `prompts` 表（主键 project_id），同步后清除所有内存缓存

### 3.2 Pipeline（22 步）
所有分析任务由 `pipeline_service.start_pipeline()` 启动的后台线程顺序执行：

| 阶段 | 步骤 | 进度 | 内容 |
|------|------|------|------|
| 数据 | 1 | 5% | 从 Athena 拉取 |
| 数据 | 2 | 10% | 加载 DataFrame |
| NLP | 3 | 15% | 语言检测（langdetect） |
| NLP | 4 | 25% | 文本统计（长度、词数、多样性） |
| NLP | 5 | 35% | TF-IDF 关键词提取 |
| NLP | 6 | 45% | LDA + t-SNE 主题模型 |
| NLP | 7 | 55% | 趋势分析（热词、类别趋势、词云） |
| LLM | 8 | 65% | 意图分类（Claude 10 类） |
| LLM | 9 | 70% | 质量评估 v1（4 维度） |
| LLM | 10 | 78% | 主题总结（Claude 双语） |
| **Phase 1** | 11 | 82% | 用户分层 |
| **Phase 1** | 12 | 85% | FAISS 向量索引构建 |
| **Phase 1** | 13 | 88% | 效果分析（like_count） |
| **Phase 1** | 14 | 92% | 质量评估 v2（5 维度 + 优化建议） |
| **Phase 2** | 15 | 68% | 留存 Cohort |
| **Phase 2** | 16 | 73% | 用户创作路径 |
| **Phase 2** | 17 | 78% | BERTopic 主题模型 |
| **Phase 2** | 18 | 85% | 爆款模板挖掘 |
| **Phase 2** | 19 | 88% | 多指标效果分析 |
| **Phase 3** | 20 | 92% | pgvector 同步 |
| **Phase 3** | 21 | 95% | Redis 缓存预热 |
| **Phase 3** | 22 | 97% | 数据质量检查 |

### 3.3 LLM 分析
- **模型**：`claude-sonnet-4-6` via API Router（`CLAUDE_BASE_URL=https://co.yes.vg/team`）
- **意图分类**：10 大类 × 5 子类 = 50 个意图，批量 20 条/请求
- **质量 v2**：5 维度（具体性/清晰度/创造力/技术细节/可执行性），每条 1-5 分，合成 0-100 分
- **单条分析**：`classify_intent_v2()` 一次调用返回意图 + 子意图 + 质量 + 优化建议 + 优化版 Prompt

### 3.4 向量检索
- **模型**：`all-MiniLM-L6-v2`（384 维，多语言基础支持）
- **索引**：FAISS `IndexFlatIP`（余弦相似度，归一化向量）
- **持久化**：`cache/faiss_index.bin` + `cache/faiss_id_map.json`
- **Phase 3 升级**：pgvector（支持类别过滤、并发访问、SQL Join）

### 3.5 缓存策略

#### 前端（React Query）
```
staleTime:
  LIVE     = 10 min  # 实时查询（Athena）：summary, daily-counts, categories
  ANALYSIS = 30 min  # Pipeline 结果：topics, intents, trends, ...
  STATIC   = 60 min  # 单条数据：prompt-detail, similar
gcTime = 60 min      # 组件卸载后缓存保留时间
```
切换 Tab 在缓存期内不会重新请求，只在 staleTime 过期后才查询。

#### 后端（内存）
`query_cache.cached_query(key_prefix, ttl=600)` 装饰器，为下列函数加缓存：
- `athena_service.fetch_summary` (TTL 10 min)
- `athena_service.fetch_daily_counts_live` (TTL 10 min)
- `athena_service.fetch_category_distributions` (TTL 10 min)

效果：首次查询 ~9 秒 → 二次查询 ~15 ms（**提速 ~600 倍**）

同步后自动调用 `invalidate()` 清除所有缓存。

#### Redis（可选，Phase 3）
`redis_cache.cached(key_prefix, ttl)` 装饰器，用于跨进程共享缓存。未启用时自动降级到内存缓存。

### 3.6 异步任务（Celery，Phase 3）
`celery_config.py` 定义 8 个 task：
- `pipeline.run_full`
- `analysis.bertopic`
- `analysis.user_segments`
- `analysis.retention`
- `analysis.embeddings`
- `analysis.effect`
- `analysis.templates`
- `analysis.user_paths`

启动 Worker：
```bash
celery -A app.celery_config worker --loglevel=info
```

### 3.7 dbt 数据模型
```
staging (view)       intermediate (view)     marts (table)
─────────────        ──────────────────      ─────────────
stg_prompts    →     int_user_activity  →   user_mart
                                              prompt_mart
                                              topic_mart
                                              template_mart
                                              effect_mart
```

---

## 4. API 接口清单

### 4.1 数据接口（`/api/data/*`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/summary` | 总览统计（Athena 实时） |
| GET | `/prompts` | 分页查询（支持 search/category/style/language） |
| POST | `/sync` | 从 Athena 同步 |
| GET | `/daily-counts` | 每日数据量 |
| GET | `/export` | CSV 导出 |

### 4.2 原版分析接口（`/api/analysis/*`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/categories` | 类别/风格/用途/颜色分布 |
| GET | `/topics` | LDA 主题聚类 |
| GET | `/intents` | 意图分类 |
| GET | `/language` | 语言 + 文本统计 + 质量 |
| GET | `/trends` | 趋势 + 热词 + 词云 |
| GET | `/keywords` | TF-IDF 关键词 |
| GET | `/theme-summary` | AI 生成的中英双语总结 |

### 4.3 V1 升级接口（`/api/v1/analysis/*`）
| 方法 | 路径 | 说明 | 引入版本 |
|------|------|------|---------|
| GET | `/user/segment` | 用户分层概览 | v2.0 |
| GET | `/user/profile` | 单用户画像 | v2.0 |
| GET | `/prompt/intent` | 意图分析（单条/批量） | v2.0 |
| GET | `/prompt/quality` | 质量评估 | v2.0 |
| GET | `/prompt/similar` | 向量相似检索 | v2.0 |
| GET | `/effect` | 效果分析 + 爆款 | v2.0 |
| GET | `/user/retention` | 留存 Cohort | v2.5 |
| GET | `/user/path` | 创作路径桑基图 | v2.5 |
| GET | `/prompt/topics` | BERTopic 主题 | v2.5 |
| GET | `/prompt/hot-templates` | 爆款模板库 | v2.5 |

### 4.4 Pipeline 接口（`/api/pipeline/*`）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/run` | 启动 22 步 Pipeline |
| GET | `/status` | 查询执行状态与进度 |

---

## 5. 数据库 Schema

### 5.1 SQLite（本地缓存）
- `prompts`：同步自 Athena 的 Prompt 数据（主键 project_id）
- `analysis_runs`：Pipeline 执行记录
- `analysis_results`：按 result_type 存 JSON 分析结果
- `sync_state`：同步状态
- `user_segments`：用户分层（Phase 1）
- `prompt_quality_v2`：质量 v2 评分（Phase 1）

### 5.2 PostgreSQL（pgvector，Phase 3）
- `prompt_embedding`：384 维向量 + 元数据 + 余弦相似度 IVFFlat 索引
- `llm_cache`：LLM 响应缓存（避免重复分析相同 prompt）
- `async_tasks`：Celery 任务跟踪

---

## 6. 部署

### 6.1 开发环境
```bash
# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env  # 填入 AWS/Claude 配置
python run.py         # http://localhost:5000

# 前端
cd frontend
npm install
npm run dev           # http://localhost:3000
```

### 6.2 生产部署（Phase 3）
```bash
# 数据库
psql -U postgres -f backend/pgvector_init.sql

# Redis
redis-server

# Celery Worker
cd backend
celery -A app.celery_config worker --loglevel=info

# 后端（使用 gunicorn）
gunicorn -w 4 -b 0.0.0.0:5000 run:app

# 前端（构建后部署到 Nginx/S3）
cd frontend
npm run build
```

### 6.3 环境变量
```env
# AWS
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
ATHENA_WORKGROUP=tripo-analyst
ATHENA_OUTPUT_LOCATION=s3://tripo-telescope/data-agent/athena-results/

# Claude
CLAUDE_API_KEY=xxx
CLAUDE_BASE_URL=https://co.yes.vg/team
CLAUDE_MODEL=claude-sonnet-4-6

# PostgreSQL (Phase 3, 可选)
PG_ENABLED=true
PG_CONNECTION_STRING=postgresql://user:pass@host:5432/db

# Redis (Phase 3, 可选)
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# Celery (Phase 3, 可选)
CELERY_ENABLED=true
CELERY_BROKER_URL=redis://localhost:6379/1
```

---

## 7. 变更历史

### v3.0（2026-04-09）—— Phase 3 完整上线
**新增**：
- Phase 3 基建：`pg_service.py`、`redis_cache.py`、`celery_config.py`
- pgvector 表结构 + 初始化脚本
- dbt mart 层：5 个宽表（user_mart、prompt_mart、topic_mart、template_mart、effect_mart）
- dbt intermediate 层：`int_user_activity`
- Pipeline 扩展至 22 步（新增 pgvector 同步、Redis 预热、数据质量检查）

**优化**：
- 前端 React Query 缓存策略分级（LIVE/ANALYSIS/STATIC，10~60 min）
- 全局 gcTime 60 min，切换 Tab 不重复请求
- 后端 `query_cache.py`：Athena 查询内存缓存（装饰器模式，TTL 10 min）
- 首次查询 ~9s → 二次查询 ~15ms（**600x 提速**）
- 同步数据后自动清除所有缓存

**UI 调整**：
- 「用户分析」「用户留存」Tab 从侧边栏隐藏（组件和 API 保留）
- 每日 Prompt 量从柱状图改为带渐变填充的折线图（Dashboard + 趋势页）

### v2.5（2026-04-09）—— Phase 2 深度分析
**新增服务**：
- `retention_service.py`：Cohort 留存分析（D1/D3/D7/D14/D30 + 复生成率 + 活跃间隔）
- `path_service.py`：用户创作路径（桑基图 + 序列挖掘 + 类别迁移）
- `bertopic_service.py`：BERTopic 主题模型（带 LDA fallback）
- `template_service.py`：爆款模板聚类 + LLM 模板合成

**新增 API**（4 个）：
- `GET /api/v1/analysis/user/retention`
- `GET /api/v1/analysis/user/path`
- `GET /api/v1/analysis/prompt/topics`
- `GET /api/v1/analysis/prompt/hot-templates`

**新增前端页面**（4 个）：
- `UserRetentionPage`（Cohort 热力图 + 留存曲线）
- `UserPathPage`（桑基图 + 迁移表）
- `TopicAnalysisPage`（主题树图 + 效果散点图）
- `TemplateMarketPage`（模板卡片网格 + 详情 + 一键复制）

**Pipeline**：从 13 步扩展至 22 步

### v2.0（2026-04-09）—— Phase 1 基础能力补全
**新增服务**：
- `user_service.py`：用户分层（power_user/regular/casual/churned）+ 个人画像
- `embedding_service.py`：FAISS 向量索引 + 相似检索
- `effect_service.py`：特征-效果相关性 + 爆款挖掘
- `query_cache.py`：内存查询缓存（v3.0 完善）

**LLM 升级**：
- `classify_intent_v2`：单 Prompt 返回意图 + 子意图 + 质量 + 优化建议 + 优化版 Prompt
- `assess_quality_v2`：5 维度批量评分 + 建议
- 50 个子意图分类体系

**新增 API**（6 个 V1 端点）：
- `GET /api/v1/analysis/user/segment`
- `GET /api/v1/analysis/user/profile`
- `GET /api/v1/analysis/prompt/intent`
- `GET /api/v1/analysis/prompt/quality`
- `GET /api/v1/analysis/prompt/similar`
- `GET /api/v1/analysis/effect`

**数据层扩展**：
- `prompts` 表新增 7 列：name, status, visibility, display_image, like_count, collect_count, score
- 新建表：`user_segments`, `prompt_quality_v2`
- 同步查询新增对应字段

**新增前端页面**（3 个）：
- `PromptDetailPage`（质量雷达图 + 优化建议 + 相似 Prompt）
- `UserProfilePage`（分层概览 + 个人画像）
- `EffectAnalysisPage`（相关性 + 爆款表）

**Explorer 升级**：表格行点击跳转到 Prompt 详情

**dbt 骨架**：`dbt_prompt_analyzer/` 项目结构 + `stg_prompts.sql`

### v1.2（2026-04-09）—— UI 与数据修复
**数据一致性修复**：
- 修复 Dashboard 数据不一致：KPI 用 Athena 实时查询，但图表仍读本地缓存（5 万条采样），导致热门类别与类别分布图冲突
- `categories` 接口也改为从 Athena 实时查询（fallback 到 cache）
- Athena 查询统一加入 `prompt != ''` 过滤

**Claude API 修复**：
- 模型名从 `claude-sonnet-4-20250514` → `claude-sonnet-4-6`（API Router 要求）
- 所有 LLM 调用（意图分类、质量评估、主题总结）从失败状态恢复

**UI 优化**：
- 全量中文化：侧边栏、按钮、图表标题、表格列头、Toast 消息
- 意图标签中英对照映射（character_design → 角色设计）
- 质量维度中文化（具体性/清晰度/创造力/技术细节）
- Dashboard 新增时间范围选择器（RangePicker），KPI 和每日量支持日期筛选
- 修复 TrendPage 日期 undefined（字段名 `pt` 而非 `date`）
- 修复 LanguagePage x 轴截断（grid bottom 30→60）
- 类别分布标签不截断（width 100→140, break 模式）
- 主题聚类标签含关键词（"Topic 6" → "主题 6：hair, character, anime"）
- 主题聚类 tooltip max-width + 换行，解决长文本溢出
- `prompt_preview` 从 80 字符扩展到 200 字符

### v1.1（2026-04-08）—— 工程化修复
**兼容性**：
- Python 3.9 兼容性修复：`dict | None` → `from __future__ import annotations`
- Pydantic Settings 添加 `extra: ignore` 支持 AWS 凭证环境变量
- Claude 客户端支持自定义 `base_url`（API Router）
- Flask 禁用 reloader（避免无关目录文件监听导致同步请求中断）

**数据同步优化**：
- 同步查询增加 `LIMIT 50000` 和 `days=7` 过滤，避免全表扫描（原表 1750 万条）
- 修复 Workgroup 名称：`data-agent` → `tripo-analyst`

### v1.0（2026-04-08）—— 初始 MVP
**后端**：
- Flask 应用骨架 + 3 个蓝图（data/analysis/pipeline）
- 5 个 Service：cache、athena、nlp、llm、pipeline
- 9 步 Pipeline
- SQLite 缓存 + Athena 查询
- Claude API 集成（意图分类、质量评估、主题总结）

**前端**：
- 7 个分析页面：Dashboard、Categories、Topics、Trends、Language、Intents、Explorer
- React Query + Axios + Ant Design + ECharts
- 侧边栏导航 + 顶栏（同步按钮 + 运行分析按钮 + 进度条）

**文档**：
- 初版技术手册 `technical-guide.md`
- 初版用户使用手册 `user-guide.md`

---

## 8. 验证清单

### 功能验证
```bash
# 1. 后端健康检查
curl http://localhost:5000/api/data/summary

# 2. V1 API（Phase 1）
curl http://localhost:5000/api/v1/analysis/user/segment
curl http://localhost:5000/api/v1/analysis/effect?metric=like_count
curl "http://localhost:5000/api/v1/analysis/prompt/similar?query=cute+cat"

# 3. V1 API（Phase 2）
curl http://localhost:5000/api/v1/analysis/user/retention
curl http://localhost:5000/api/v1/analysis/user/path
curl http://localhost:5000/api/v1/analysis/prompt/topics
curl http://localhost:5000/api/v1/analysis/prompt/hot-templates

# 4. Pipeline
curl -X POST http://localhost:5000/api/pipeline/run
curl http://localhost:5000/api/pipeline/status

# 5. 缓存效果对比
time curl http://localhost:5000/api/data/summary  # 首次 ~9s
time curl http://localhost:5000/api/data/summary  # 二次 ~0.01s
```

### 前端验证
1. 访问 http://localhost:3000
2. 侧边栏应显示 11 个菜单项
3. 依次点击每个 Tab：切换应即时响应（无重新请求）
4. 点击 Explorer 表格行 → 跳转到 Prompt 详情页
5. 点击「同步数据」→ 缓存清空，下次切 Tab 会重新查询

### 性能指标
| 场景 | v1.0 | v3.0 |
|------|------|------|
| 冷启动首页加载 | ~10s | ~10s |
| 切换 Tab（无缓存） | ~3~9s | ~50ms |
| 切换 Tab（有缓存） | N/A | ~0ms |
| Athena 重复查询 | ~9s | ~15ms |

---

## 9. 已知限制与后续规划

### 当前限制
- SQLite 并发读写能力有限（适合单机）
- FAISS 索引全量重建（未做增量）
- Pipeline 单线程执行（Celery Worker 未默认启用）
- BERTopic 需要额外依赖（未启用时自动降级到 LDA）
- pgvector 需要外部 PostgreSQL 实例（未启用时使用 FAISS）

### 后续规划（Phase 4+）
- Pipeline 增量更新（只分析新增 Prompt）
- 接入 Airflow/Prefect 做工作流编排
- 支持更多数据源（S3 直读、BigQuery）
- A/B 实验分析模块
- 用户画像推送（邮件/钉钉报告）
- 多租户支持（不同 Workspace 隔离）
