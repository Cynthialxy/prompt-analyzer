# Prompt Analyzer 技术使用手册

> 面向开发人员的部署、配置与使用指南
> 最后更新：2026-04-12

---

## 1. 项目简介

Prompt Analyzer 是一个全栈数据分析与可视化平台，用于分析 Tripo AI 3D 模型生成的 Prompt 数据。系统从 AWS Athena 获取原始数据，通过 NLP 与 Claude LLM 进行多维度分析，并通过交互式 Dashboard 展示分析结果。

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite + Ant Design 6 + ECharts 5 |
| 状态管理 | TanStack React Query v5（全局缓存 + 预热） |
| 后端 | Python Flask 3.1 + SQLite 缓存 |
| 数据源 | AWS Athena（查询 S3 上的 Tripo 数据） |
| AI 分析 | Claude API（意图分类、质量评估、主题总结） |
| NLP | scikit-learn（TF-IDF、LDA、t-SNE）、jieba（中文分词）、langdetect（语言检测） |
| 向量检索 | FAISS + sentence-transformers（all-MiniLM-L6-v2） |

### 项目结构

```
prompt_analyzer/
├── backend/                          # Python Flask 后端
│   ├── app/
│   │   ├── __init__.py               # App factory + 蓝图注册 + StrictJSONProvider
│   │   ├── config.py                 # Pydantic Settings 配置
│   │   ├── routes/
│   │   │   ├── data.py               # 数据接口（sync/prompts/summary/export）
│   │   │   ├── analysis.py           # 原版分析接口（categories/language/topics 等）
│   │   │   ├── analysis_v1.py        # V1 升级接口（effect/user/prompt 深度分析）
│   │   │   └── pipeline.py           # Pipeline 控制（run/status）
│   │   ├── services/
│   │   │   ├── cache_service.py      # SQLite 缓存 + 本地质量代理计算
│   │   │   ├── athena_service.py     # Athena 查询
│   │   │   ├── nlp_service.py        # NLP 分析（LDA/TF-IDF/t-SNE）
│   │   │   ├── llm_service.py        # Claude API（意图/质量/主题总结）
│   │   │   ├── pipeline_service.py   # 22 步 Pipeline 编排
│   │   │   ├── user_service.py       # 用户分层 + 画像
│   │   │   ├── embedding_service.py  # FAISS 向量索引
│   │   │   ├── effect_service.py     # 效果分析（Spearman 相关性）
│   │   │   ├── retention_service.py  # 留存 Cohort
│   │   │   ├── path_service.py       # 创作路径（桑基图）
│   │   │   ├── bertopic_service.py   # BERTopic 主题模型
│   │   │   └── template_service.py   # 爆款模板挖掘
│   │   └── utils/
│   │       └── text_utils.py
│   ├── cache/                        # SQLite 数据库 + FAISS 索引文件
│   ├── requirements.txt
│   ├── run.py                        # 启动入口
│   └── .env                          # 环境变量
│
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts             # Axios 实例
│   │   │   └── endpoints.ts          # 所有 API 调用函数
│   │   ├── hooks/
│   │   │   └── useAnalysisData.ts    # React Query hooks + CORE_QUERY_KEYS + useInvalidateCoreData
│   │   ├── pages/                    # 12 个页面组件
│   │   ├── components/
│   │   │   ├── layout/AppLayout.tsx  # 侧边栏 + 顶栏 + useGlobalPrefetch
│   │   │   ├── common/KpiCard.tsx
│   │   │   └── charts/EChartsWrapper.tsx
│   │   ├── types/index.ts
│   │   └── App.tsx                   # 路由 + QueryClient 配置
│   └── package.json
│
└── docs/                             # 文档目录
```

---

## 2. 环境准备

### 前置依赖

- Python >= 3.9
- Node.js >= 18
- AWS CLI 已配置（需有 Athena 查询权限）
- Claude API Key（可选，无 key 时质量分析降级为本地计算）

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

```env
# AWS 配置
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
ATHENA_WORKGROUP=tripo-analyst
ATHENA_OUTPUT_LOCATION=s3://tripo-telescope/data-agent/athena-results/

# Claude API（可选）
CLAUDE_API_KEY=sk-ant-your-key-here
CLAUDE_BASE_URL=https://co.yes.vg/team
CLAUDE_MODEL=claude-sonnet-4-6

# 缓存路径
CACHE_DB_PATH=./cache/analysis_cache.db
```

> **注意**：`CLAUDE_API_KEY` 不可用时，平台仍可正常运行。意图分类和质量评估会跳过，质量雷达图自动使用本地代理指标（基于 prompt 长度、标签填充度等推算）。

### 高级配置

以下参数在 `backend/app/config.py` 中定义，可按需调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `athena_query_timeout_sec` | 300 | Athena 查询超时（秒） |
| `athena_poll_interval_sec` | 1.5 | Athena 状态轮询间隔（秒） |
| `claude_model` | claude-sonnet-4-6 | Claude 模型版本 |
| `llm_sample_size` | 500 | 意图分类采样数量 |
| `llm_quality_sample_size` | 100 | 质量评估采样数量 |
| `topic_num_clusters` | 15 | LDA 主题聚类数 |

---

## 4. 启动服务

### 启动后端

```bash
cd backend
python run.py
# 或后台运行：
nohup python run.py > /tmp/backend.log 2>&1 &
```

后端运行在 `http://localhost:5000`。

### 启动前端

```bash
cd frontend
npm run dev
```

前端运行在 `http://localhost:3000`，Vite 自动代理 `/api/*` 到后端 5000 端口。

### 重启后端

```bash
# 杀掉占用 5000 端口的进程并重启
lsof -ti :5000 | xargs kill -9 2>/dev/null
cd backend && nohup python run.py > /tmp/backend.log 2>&1 &
sleep 3 && tail -5 /tmp/backend.log
```

---

## 5. 分析管线（22 步）

通过 `POST /api/pipeline/run` 启动，后台线程异步执行：

| 阶段 | 步骤 | 内容 |
|------|------|------|
| 数据 | 1-2 | 从 Athena 拉取 + 加载 DataFrame |
| NLP | 3-7 | 语言检测、文本统计、TF-IDF、LDA+t-SNE、趋势分析 |
| LLM | 8-10 | 意图分类、质量评估 v1、主题总结（均需 Claude API） |
| Phase 1 | 11-14 | 用户分层、FAISS 向量索引、效果分析、质量评估 v2 |
| Phase 2 | 15-19 | 留存 Cohort、创作路径、BERTopic、爆款模板、多指标效果 |
| Phase 3 | 20-22 | pgvector 同步（可选）、Redis 预热（可选）、数据质量检查 |

Pipeline 完成后，前端 `useInvalidateCoreData()` 自动清空所有 React Query 缓存，各页面下次访问时重新拉取最新数据。

---

## 6. 缓存机制

### 前端缓存（React Query）

```typescript
// App.tsx QueryClient 配置
staleTime = 5 * 60 * 1000   // 5 分钟内切换 Tab 不重新请求
gcTime   = 10 * 60 * 1000   // 组件卸载后数据在内存保留 10 分钟
```

**全局预热**：`AppLayout` 组件挂载时调用 `useGlobalPrefetch()`，一次性触发所有 15 个核心查询，之后任何页面导航均命中缓存。

**注意**：预热调用的参数必须与页面使用的参数一致，否则 query key 不同导致缓存未命中。例如效果分析统一使用 `'like_count'` 作为默认 metric。

### 后端缓存（SQLite）

| 数据类型 | 缓存位置 | 说明 |
|----------|----------|------|
| 效果分析结果 | `analysis_results.effect_analysis_{metric}` | 首次计算后写入，后续直接读取 |
| 质量评估结果 | `analysis_results.quality` / `quality_v2` | Pipeline 写入；空时自动本地计算 |
| 其他分析结果 | `analysis_results.{result_type}` | Pipeline 写入 |
| Prompt 原始数据 | `prompts` 表 | 同步时写入，summary/categories 实时聚合 |

### JSON 安全

Flask 注册了 `_StrictJSONProvider`（`allow_nan=False`），防止 pandas 产生的 `NaN` 值通过 JSON 序列化传到前端导致解析失败。`effect_service.py` 中 heatmap 构建时额外将 `np.isnan` 替换为 `None`。

---

## 7. API 接口参考

### 数据接口（`/api/data/*`）

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/summary` | 数据概览统计 | `date_from`, `date_to` |
| GET | `/prompts` | 分页查询 | `page`, `page_size`, `search`, `category`, `style`, `language` |
| POST | `/sync` | 从 Athena 同步数据 | - |
| GET | `/daily-counts` | 每日数据量 | `date_from`, `date_to` |
| GET | `/export` | CSV 导出 | - |

### 分析接口（`/api/analysis/*`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/categories` | 类别/风格/用途/颜色分布 |
| GET | `/topics` | LDA 主题聚类 + t-SNE 散点坐标 |
| GET | `/intents` | 意图分类分布 + 示例 Prompt |
| GET | `/language` | 语言分布 + 文本统计 + 质量评分（LLM 或本地代理） |
| GET | `/trends` | 热词趋势 + 日趋势 + 词云 |
| GET | `/keywords` | TF-IDF 关键词 |
| GET | `/theme-summary` | AI 生成的数据总结 |

### V1 升级接口（`/api/v1/analysis/*`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/user/segment` | 用户分层概览 |
| GET | `/user/profile?user_id=` | 单用户画像 |
| GET | `/prompt/intent?project_id=` | 单条意图分析（SQLite→Athena fallback） |
| GET | `/prompt/quality?project_id=` | 单条质量评估（SQLite→Athena fallback） |
| GET | `/prompt/similar?project_id=` | 向量相似检索 |
| GET | `/effect?metric=like_count` | 效果分析 + 爆款（SQLite 缓存） |
| GET | `/user/retention` | 留存 Cohort |
| GET | `/user/path` | 创作路径桑基图 |
| GET | `/prompt/topics` | BERTopic 主题 |
| GET | `/prompt/hot-templates` | 爆款模板库 |

### Pipeline 接口（`/api/pipeline/*`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/run` | 启动分析管线 |
| GET | `/status` | 查询状态与进度（0.0~1.0） |

---

## 8. 数据库结构

SQLite 缓存数据库（`cache/analysis_cache.db`）包含以下表：

### prompts 表

| 字段 | 说明 |
|------|------|
| `project_id` (PK) | 项目 ID |
| `user_id` | 用户 ID |
| `prompt` | 用户输入的 Prompt 文本 |
| `caption` / `name` | 标题 / 名称 |
| `llm_keyword` / `llm_object` / `llm_category` / `llm_style` / `llm_color` / `llm_use_case` | LLM 标注的分类标签 |
| `like_count` / `collect_count` / `score` | 互动指标 |
| `from_type` / `status` / `visibility` | 来源与状态 |
| `created_at` / `pt` | 创建时间 / 分区日期（格式 YYYYMMDD） |
| `fetched_at` | 同步时间 |

### analysis_results 表

按 `result_type` 存储 JSON 分析结果，常见 key：

| result_type | 内容 |
|-------------|------|
| `language` | 语言分布 |
| `text_stats` | 文本统计（长度直方图、词汇多样性） |
| `quality` | LLM 质量评分（4 维度） |
| `quality_v2` | LLM 质量评分 v2（5 维度 + 优化建议） |
| `intents` | 意图分类分布 |
| `topics` | LDA 主题 + t-SNE 坐标 |
| `trends` | 热词趋势 + 词云 |
| `bertopic` | BERTopic 主题 |
| `retention` | 留存 Cohort 数据 |
| `user_paths` | 创作路径桑基图数据 |
| `effect_analysis_like_count` | 效果分析（like_count 指标） |

### 其他表

- `analysis_runs`：Pipeline 执行历史（status/step/progress/error）
- `sync_state`：最后同步时间
- `user_segments`：用户分层结果
- `prompt_quality_v2`：单条 Prompt 质量 v2 评分

---

## 9. 常见问题

**Q: 后端启动报 "Port 5000 is already in use"？**
A: `lsof -ti :5000 | xargs kill -9` 杀掉占用进程后重启。macOS 上 AirPlay Receiver 也会占用 5000 端口，可在系统设置中关闭。

**Q: Athena 查询超时？**
A: 调大 `athena_query_timeout_sec`，或检查 Athena Workgroup 配额和 S3 输出路径权限。

**Q: 效果分析 Tab 无数据？**
A: 检查后端日志是否有 `NaN` 相关错误。确认 `app/__init__.py` 中已注册 `_StrictJSONProvider`，`effect_service.py` 中 heatmap 值构建时已将 `np.isnan` 替换为 `None`。

**Q: 质量雷达图无数据（采样 0 条）？**
A: LLM API 不可用时 `quality.summary` 为空。`/api/analysis/language` 接口会自动调用 `cache_service.compute_quality_from_prompts()` 用本地代理指标填充，重启后端后刷新页面即可。

**Q: 切换 Tab 每次都重新加载？**
A: 检查 `AppLayout.tsx` 中 `useGlobalPrefetch()` 是否正常调用，以及 `App.tsx` 中 `staleTime` 是否为 `5 * 60 * 1000`。另外确认预热调用的参数与页面使用的参数一致（如 `useEffectAnalysis('like_count')`）。

**Q: LLM 分析成本如何控制？**
A: 通过 `llm_sample_size`（默认 500）和 `llm_quality_sample_size`（默认 100）限制采样数。Pipeline 结果会缓存到 SQLite，重复运行不会重复调用 LLM（除非手动清除缓存）。

**Q: 缓存数据如何强制刷新？**
A: 前端点击「同步数据」会清空 React Query 缓存；后端缓存可删除 `backend/cache/analysis_cache.db` 后重启，或通过 Pipeline 重新生成。

**Q: 如何增加新的分析维度？**
A: 在 `backend/app/services/` 下新增 Service，在 `pipeline_service.py` 中注册步骤，在 `analysis_v1.py` 中添加路由，前端新增对应页面和 hook 即可。新 hook 需加入 `CORE_QUERY_KEYS` 和 `useGlobalPrefetch()`。

**Q: 前端构建后如何部署？**
A: `npm run build` 生成 `dist/` 目录，部署到 Nginx/S3 等静态服务器。后端 API 地址在 `frontend/src/api/client.ts` 中配置（生产环境去掉 Vite 代理，直接指向后端地址）。
