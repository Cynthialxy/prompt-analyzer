# Tripo Prompt 分析平台 —— 技术设计文档

> 最后更新：2026-04-12
> 版本：v3.1（缓存优化 + 质量指标本地化）

---

## 1. 项目简介

### 1.1 背景
Tripo Prompt 分析平台是一个全栈数据分析与可视化系统，用于深度分析 Tripo AI 3D 模型生成服务中用户提交的 Prompt 数据。平台从 AWS Athena 实时拉取数据，通过 NLP、LLM、向量嵌入等技术进行多维度分析，为产品、运营、管理层提供数据驱动的洞察。

### 1.2 核心能力（截至 v3.1）
- **基础分析**：类别/风格分布、语言检测、文本统计、TF-IDF 关键词
- **主题建模**：LDA + t-SNE 散点图，可升级为 BERTopic
- **LLM 智能分析**：意图分类（10 类 + 子类）、质量评估（5 维度）、优化建议生成
- **本地质量代理指标**：不依赖 LLM API，从本地 SQLite 数据实时计算质量评分
- **用户分析**：分层（power_user/regular/casual/churned）、画像、留存 Cohort
- **Prompt 深度分析**：向量相似检索（FAISS）、单条 Prompt 浏览
- **效果分析**：爆款挖掘、特征-效果相关性、爆款模板合成
- **创作路径**：桑基图 + 序列挖掘 + 类别迁移
- **业务洞察总结**：总览页动态生成 4 模块业务结论（现状→洞察→问题→建议）
- **性能优化**：前后端双层缓存、全局预热、Effect 分析 SQLite 缓存、异步 Pipeline

---

## 2. 技术架构

### 2.1 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                         Browser (React 19)                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  11 个分析页面 + Prompt 详情页                               │  │
│  │  React Router v7 · Ant Design 6 · ECharts 5                 │  │
│  │  React Query（staleTime 5min · gcTime 10min · 全局预热）     │  │
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
│  ├────────────────────────────────────────────────────────────┤  │
│  │  严格 JSON Provider（拒绝 NaN）+ 22 步 Pipeline              │  │
│  └──────────┬───────────┬──────────┬──────────┬────────────────┘  │
└─────────────┼───────────┼──────────┼──────────┼────────────────────┘
              │           │          │          │
       AWS Athena    SQLite      FAISS       Claude API
   (silver.*)    (本地缓存)  (向量索引)  (via API Router)
```

### 2.2 目录结构

```
prompt_analyzer/
├── backend/                          # Flask 后端
│   ├── app/
│   │   ├── __init__.py               # App factory + 蓝图注册 + StrictJSONProvider
│   │   ├── config.py                 # Pydantic Settings
│   │   ├── routes/
│   │   │   ├── data.py               # 数据接口
│   │   │   ├── analysis.py           # 原版分析接口
│   │   │   ├── analysis_v1.py        # V1 升级接口（含 Athena fallback）
│   │   │   └── pipeline.py           # Pipeline 控制
│   │   ├── services/
│   │   │   ├── cache_service.py      # SQLite 缓存 + 本地质量计算
│   │   │   ├── athena_service.py     # Athena 查询
│   │   │   ├── nlp_service.py        # NLP 分析（LDA/TF-IDF）
│   │   │   ├── llm_service.py        # Claude API
│   │   │   ├── pipeline_service.py   # 22 步 Pipeline 编排
│   │   │   ├── user_service.py       # 用户分层 + 画像
│   │   │   ├── embedding_service.py  # FAISS 向量索引
│   │   │   ├── effect_service.py     # 效果分析（NaN→null 修复）
│   │   │   ├── retention_service.py  # 留存 Cohort
│   │   │   ├── path_service.py       # 创作路径
│   │   │   ├── bertopic_service.py   # BERTopic 主题
│   │   │   └── template_service.py   # 爆款模板
│   │   └── utils/
│   │       └── text_utils.py
│   ├── cache/                        # SQLite + FAISS 索引
│   ├── requirements.txt
│   ├── run.py
│   └── .env                          # 环境变量（AWS/Claude）
│
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts             # Axios
│   │   │   └── endpoints.ts          # 所有 API 函数
│   │   ├── hooks/
│   │   │   └── useAnalysisData.ts    # React Query hooks + CORE_QUERY_KEYS + useInvalidateCoreData
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx     # 总览（含动态业务洞察卡片）
│   │   │   ├── CategoryPage.tsx      # 分类标签
│   │   │   ├── TopicPage.tsx         # 主题聚类（LDA）
│   │   │   ├── TrendPage.tsx         # 趋势分析
│   │   │   ├── LanguagePage.tsx      # 语言与质量（本地代理质量指标）
│   │   │   ├── IntentPage.tsx        # 意图分析
│   │   │   ├── ExplorerPage.tsx      # 数据浏览
│   │   │   ├── PromptDetailPage.tsx  # Prompt 详情（只展示内容，无 AI 分析）
│   │   │   ├── UserPathPage.tsx      # 创作路径
│   │   │   ├── EffectAnalysisPage.tsx # 效果分析
│   │   │   ├── TopicAnalysisPage.tsx # 主题分析（BERTopic）
│   │   │   └── TemplateMarketPage.tsx # 爆款模板
│   │   ├── components/
│   │   │   ├── layout/AppLayout.tsx  # 侧边栏 + 顶栏 + useGlobalPrefetch
│   │   │   ├── common/KpiCard.tsx
│   │   │   └── charts/EChartsWrapper.tsx
│   │   ├── types/index.ts            # 所有 TypeScript 接口
│   │   └── App.tsx                   # 路由 + QueryClient 配置
│   └── package.json
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
| 状态/请求 | TanStack Query | 5 | 数据请求 + 全局缓存 |
| HTTP | Axios | 1.14 | API 客户端 |
| 构建 | Vite | 8 | 开发/打包 |
| 后端框架 | Flask | 3.1 | Web 服务 |
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
| 统计 | scipy | 1.11 | 相关性分析（Spearman） |
| 主题模型 | BERTopic | 0.16 | 高级主题（Phase 2+） |

---

## 3. 核心模块设计

### 3.1 数据同步
- **入口**：`POST /api/data/sync` → `athena_service.fetch_and_cache_prompts()`
- **策略**：默认同步最近 7 天、最多 5 万条，避免全表扫描（原始表 1750 万+ 条）
- **字段**：project_id, user_id, prompt, caption, name, llm_*, from_type, status, visibility, display_image, like_count, collect_count, score, created_at, pt
- **落地**：SQLite `prompts` 表（主键 project_id），同步后清除所有 React Query 缓存

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
| **Phase 3** | 20 | 92% | pgvector 同步（可选） |
| **Phase 3** | 21 | 95% | Redis 缓存预热（可选） |
| **Phase 3** | 22 | 97% | 数据质量检查 |

### 3.3 LLM 分析
- **模型**：`claude-sonnet-4-6` via API Router（`CLAUDE_BASE_URL=https://co.yes.vg/team`）
- **意图分类**：10 大类 × 子类，批量 20 条/请求
- **质量 v2**：5 维度（具体性/清晰度/创造力/技术细节/可执行性），每条 1-5 分，合成 0-100 分
- **降级策略**：LLM API 不可用时，质量指标自动降级到本地代理计算（见 3.4）

### 3.4 本地质量代理指标
当 LLM API 不可用或历史 quality 数据为空时，`cache_service.compute_quality_from_prompts()` 从本地 SQLite 数据计算代理质量分：

| 维度 | 计算逻辑 | 范围 |
|------|----------|------|
| specificity（具体性） | prompt 长度分段：≤50→1，≤100→2，≤200→3，≤400→4，>400→5 | 1-5 |
| clarity（清晰度） | 有 llm_category 标签→4，无→2 | 1-5 |
| creativity（创造力） | 有非通用 llm_style→4，通用风格→3，无→2 | 1-5 |
| technical_detail（技术细节） | llm_color/keyword/object/style 填充数量 +1 | 1-5 |

`/api/analysis/language` 接口：优先返回 LLM quality 数据；若 summary 为空，自动调用本地计算填充。

### 3.5 向量检索
- **模型**：`all-MiniLM-L6-v2`（384 维，多语言基础支持）
- **索引**：FAISS `IndexFlatIP`（余弦相似度，归一化向量）
- **持久化**：`cache/faiss_index.bin` + `cache/faiss_id_map.json`

### 3.6 Prompt 详情页
- 点击效果分析爆款 Prompt 表格行 → 跳转 `/prompt/:projectId`
- 详情页直接从 React Query 缓存的 `effect-analysis` 数据中查找对应 `hit_prompts` 记录，展示 prompt 原文
- 不调用 LLM，无额外 API 请求
- 若缓存中找不到（少见），显示 Empty 提示

### 3.7 单条 Prompt 后端查找（`/api/v1/analysis/prompt/intent`）
当需要对单条 Prompt 进行意图/质量分析时，后端采用两阶段查找：
1. 先查本地 SQLite `prompts` 表
2. 找不到时 fallback 到 Athena `silver.clean_tripo_project` 查询
3. 两者均无则返回 404

### 3.8 缓存策略

#### 前端（React Query）
```
QueryClient 全局配置（App.tsx）：
  staleTime = 5 min   # 5 分钟内切换 Tab 直接读缓存，不发请求
  gcTime   = 10 min   # 组件卸载后数据在内存保留 10 分钟

全局预热（AppLayout → useGlobalPrefetch）：
  App 启动时一次性触发所有核心查询（15 个 hook），
  之后任何页面导航均命中缓存，零请求延迟。

全局失效（useInvalidateCoreData）：
  Pipeline 完成后批量 invalidate CORE_QUERY_KEYS 中的所有 key，
  下次访问自动重新拉取最新数据。

注意：预热调用与页面使用必须使用相同参数，避免 query key 不匹配。
  例：AppLayout 中 useEffectAnalysis('like_count')
      EffectAnalysisPage 默认 metric='like_count'  ← 保持一致
```

#### 后端（SQLite）
| 接口 | 缓存策略 |
|------|----------|
| `/api/analysis/language` 的 quality | 优先读 `analysis_results.quality`；空时实时计算 |
| `/api/v1/analysis/effect` | 读 `analysis_results.effect_analysis_{metric}`；无缓存时计算并写入 |
| 其他分析接口 | 读 `analysis_results` 对应 result_type；无数据时提示跑 Pipeline |
| summary/categories/daily-counts | 每次从 `prompts` 表实时聚合，无独立缓存 |

#### JSON 安全
`app/__init__.py` 注册 `_StrictJSONProvider`，全局设置 `allow_nan=False`，防止 pandas Spearman 相关性产生的 `NaN` 通过 Flask JSON 序列化导致前端解析失败。`effect_service.py` 中 heatmap 值构建时额外将 `np.isnan` 值替换为 `None`。

### 3.9 总览页业务洞察
`DashboardPage.tsx` 的 `buildInsight()` 函数基于已加载的 summary、categories、langData 动态生成 4 模块业务洞察卡片：
1. **核心业务现状** — 规模、人均创作量、需求集中度、风格、国际化
2. **关键数据洞察** — 5 条带数据+业务解读的分析（活跃度、需求集中、风格、质量、国际化）
3. **问题诊断与风险提示** — 按阈值动态判断显示（需求集中 >50%、风格单一 >45%、留存偏低等）
4. **可落地优化建议** — 每条对应具体问题，类别/风格关键词可点击跳转

---

## 4. API 接口清单

### 4.1 数据接口（`/api/data/*`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/summary` | 总览统计（实时聚合 prompts 表） |
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
| GET | `/language` | 语言 + 文本统计 + 质量（LLM 或本地代理） |
| GET | `/trends` | 趋势 + 热词 + 词云 |
| GET | `/keywords` | TF-IDF 关键词 |
| GET | `/theme-summary` | AI 生成的中英双语总结 |

### 4.3 V1 升级接口（`/api/v1/analysis/*`）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/user/segment` | 用户分层概览 |
| GET | `/user/profile` | 单用户画像 |
| GET | `/prompt/intent` | 意图分析（单条 SQLite→Athena fallback / 批量） |
| GET | `/prompt/quality` | 质量评估（单条 SQLite→Athena fallback / 批量） |
| GET | `/prompt/similar` | 向量相似检索 |
| GET | `/effect` | 效果分析 + 爆款（SQLite 缓存） |
| GET | `/user/retention` | 留存 Cohort |
| GET | `/user/path` | 创作路径桑基图 |
| GET | `/prompt/topics` | BERTopic 主题 |
| GET | `/prompt/hot-templates` | 爆款模板库 |

### 4.4 Pipeline 接口（`/api/pipeline/*`）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/run` | 启动 22 步 Pipeline |
| GET | `/status` | 查询执行状态与进度 |

---

## 5. 数据库 Schema

### 5.1 SQLite（本地缓存）
- `prompts`：同步自 Athena 的 Prompt 数据（主键 project_id，含 like_count/collect_count/score 等指标字段）
- `analysis_runs`：Pipeline 执行记录
- `analysis_results`：按 result_type 存 JSON 分析结果（language/intents/topics/quality/effect_analysis_like_count 等）
- `sync_state`：同步状态
- `user_segments`：用户分层（Phase 1）
- `prompt_quality_v2`：质量 v2 评分（Phase 1）

### 5.2 前端路由
| 路径 | 页面 |
|------|------|
| `/` | DashboardPage（总览） |
| `/categories` | CategoryPage（分类标签） |
| `/topics` | TopicPage（主题聚类） |
| `/trends` | TrendPage（趋势分析） |
| `/language` | LanguagePage（语言与质量） |
| `/intents` | IntentPage（意图分析） |
| `/explorer` | ExplorerPage（数据浏览） |
| `/paths` | UserPathPage（创作路径） |
| `/effects` | EffectAnalysisPage（效果分析） |
| `/topic-analysis` | TopicAnalysisPage（主题分析） |
| `/templates` | TemplateMarketPage（爆款模板） |
| `/prompt/:projectId` | PromptDetailPage（Prompt 详情） |

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

### 6.2 环境变量
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

# 缓存路径
CACHE_DB_PATH=./cache/analysis_cache.db
```

---

## 7. 变更历史

### v3.1（2026-04-12）—— 缓存优化 + 质量指标本地化

**新增**：
- `cache_service.compute_quality_from_prompts()`：不依赖 LLM API 的本地代理质量计算，直接从 SQLite prompts 表推算 4 个维度评分
- 效果分析 SQLite 缓存：`/api/v1/analysis/effect` 首次计算后写入 `analysis_results`，后续直接读缓存
- 总览页 4 模块动态业务洞察卡片（`buildInsight()`）：现状→洞察→问题→建议，类别/风格关键词可点击跳转对应页面
- 热力图分析描述：效果分析页共线性热力图下方附业务语言说明

**修复**：
- 效果分析 Tab 无数据：pandas Spearman 相关性产生 `NaN` → Flask 序列化为无效 JSON，前端解析失败。修复方案：① `effect_service.py` 中将 `np.isnan` 值替换为 `None`；② `app/__init__.py` 注册 `_StrictJSONProvider`（`allow_nan=False`）
- 前端 React Query query key 不匹配：`AppLayout` 预热 `useEffectAnalysis()` 与页面 `useEffectAnalysis('like_count')` key 不同导致缓存未命中，统一为 `'like_count'`
- 语言与质量页质量雷达图无数据：LLM API 不可用时 quality.summary 为空，前端判断 `{}` 为 truthy 但内部无数据，改为 `hasQualityData` 检查后自动使用本地计算数据
- Prompt 详情页显示"未找到 Prompt 数据"：效果分析的爆款 Prompt 来自 Athena 而非本地 SQLite，后端 `/prompt/intent` 加 Athena fallback；前端详情页改为直接读 effect-analysis 缓存中的 hit_prompts，无需额外请求

**调整**：
- `PromptDetailPage` 移除 LLM 分析功能（API 不稳定），只展示 prompt 原文和 Project ID
- 总览页移除 AI 主题总结（theme-summary）区块，改为本地数据驱动的业务洞察卡片
- 全局预热统一使用 `staleTime: 5min, gcTime: 10min`（原设计中分级 LIVE/ANALYSIS/STATIC 未实际实现）
- 效果分析共线性热力图分析描述改为蓝色 Alert 样式（对齐主题分析风格）

### v3.0（2026-04-09）—— Phase 3 基建
**新增**：
- Phase 3 可选组件：pg_service、redis_cache、celery_config（均非默认启用）
- dbt mart 层：5 个宽表
- Pipeline 扩展至 22 步

**优化**：
- 全局 gcTime 设置，切换 Tab 不重复请求
- 同步数据后自动清除所有缓存

**UI 调整**：
- 「用户分析」「用户留存」Tab 从侧边栏隐藏（组件和 API 保留）
- 每日 Prompt 量改为带渐变填充的折线图

### v2.5（2026-04-09）—— Phase 2 深度分析
**新增服务**：retention / path / bertopic / template

**新增前端页面**：
- `UserPathPage`（桑基图 + 迁移表）
- `TopicAnalysisPage`（主题树图 + 效果散点图 + 平均点赞排行）
- `TemplateMarketPage`（模板卡片网格 + 详情 + 一键复制）

### v2.0（2026-04-09）—— Phase 1 基础能力
**新增**：user / embedding / effect 三个 Service；6 个 V1 端点；EffectAnalysisPage

### v1.2（2026-04-09）—— UI 与数据修复
Claude 模型名修正；Dashboard 数据一致性；意图/质量维度全面中文化；Dashboard 时间范围筛选器

### v1.0（2026-04-08）—— 初始 MVP
Flask 骨架 + 9 步 Pipeline + 7 个前端页面

---

## 8. 验证清单

```bash
# 后端健康检查
curl http://localhost:5000/api/data/summary

# 效果分析（含缓存）
curl http://localhost:5000/api/v1/analysis/effect?metric=like_count

# 语言质量（本地计算）
curl http://localhost:5000/api/analysis/language | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('quality sample_size:', d['quality'].get('sample_size'))
print('specificity mean:', d['quality']['summary'].get('specificity',{}).get('mean'))
"

# Pipeline
curl -X POST http://localhost:5000/api/pipeline/run
curl http://localhost:5000/api/pipeline/status
```

### 前端验证
1. 访问 http://localhost:3000
2. 侧边栏显示 11 个菜单项
3. 切换 Tab：首次加载后再切换应即时响应（无 loading）
4. 总览页 KPI 卡片下方应显示业务洞察蓝色卡片（4 个模块）
5. 效果分析 → 点击爆款 Prompt 行 → 跳转详情页显示 prompt 原文
6. 语言与质量页 → 质量雷达图应有数据（非空白）

---

## 9. 已知限制与后续规划

### 当前限制
- SQLite 并发读写能力有限（适合单机）
- FAISS 索引全量重建（未做增量）
- Pipeline 单线程执行
- BERTopic 需要额外依赖（未启用时自动降级到 LDA）
- 质量指标在 LLM API 不可用时为代理估算，非真实 LLM 评分

### 后续规划（Phase 4+）
- Pipeline 增量更新（只分析新增 Prompt）
- 接入 Airflow/Prefect 做工作流编排
- LLM API 恢复后自动触发质量重评
- A/B 实验分析模块
- 用户画像推送（邮件/钉钉报告）
- 多租户支持（不同 Workspace 隔离）
