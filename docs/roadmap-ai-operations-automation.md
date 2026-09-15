# AI 运营自动化中台 · 开发计划

> 基于 Octop（MIT）扩展层的商业化项目路线图。本文档面向开发团队，定义产品形态、技术架构、分阶段交付计划与验收标准。

---

## 1. 项目概述

### 1.1 产品定位

**企业级 AI 运营自动化中台**——基于 Octop 的浏览器 AI+、IM 通道桥接、多 Agent 编排与 Cron 调度能力，为运营团队提供"爬数据 → 分析 → 推送 → 执行"的一站式自动化解决方案。

### 1.2 目标客户

| 客户画像 | 核心痛点 | 付费意愿 |
|----------|----------|----------|
| 电商运营团队（5-20 人） | 竞品价格/上新靠人盯，每天机械重复 3-4 小时 | ¥299-2999/月 |
| 品牌市场部 | 舆情监控靠手动刷，负面发现滞后 2-24 小时 | ¥1999-9999/月 |
| 出海团队 | 多平台多语言竞品情报覆盖不全 | ¥999-4999/月 |
| 中大型企业（运营 20+ 人） | 内部系统无 API，自动化改价/上新/客服全靠手工 | 3w-10w 部署费 + 年服务费 |

### 1.3 核心价值主张

- **不跟 Dify/Coze 竞争**——我们卖的是 Octop 生态上的扩展层（插件、专家、Connector、定制化）
- **独占的能力组合**——市面上唯一一个开箱即用"浏览器自动化 + IM 群推送 + 多 Agent 编排"的开源方案
- **数据自主可控**——私有化部署，敏感数据不出企业内网

### 1.4 项目约束

| 约束 | 说明 |
|------|------|
| Octop 上游依赖 | 跟随 Octop mainline 同步更新，不在 `infra/` 核心目录做破坏性修改 |
| MIT 协议 | Octop 本身不可独占，商业资产锁定在自建扩展层 |
| 代码安全 | 所有 Shell 命令走 tool_guard 规则；文件操作走 BackendWorkspace |
| 跨平台 | CI 必须通过 Linux + Windows（Octop 原生支持） |

---

## 2. 技术架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    客户接入层                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ 飞书群    │  │ 企微群    │  │ 钉钉群    │  │ Dashboard│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬───┘ │
│       │             │             │               │      │
└───────┼─────────────┼─────────────┼───────────────┼──────┘
        ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────┐
│                   Octop 网关层                           │
│  harness-gateway ─── IM 协议归一化                       │
│  Cron Manager    ─── APScheduler 定时调度                │
│  Proactive Care  ─── Agent 主动推送                       │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 Octop Agent 运行时                       │
│  harness-agent (LangGraph ReAct loop)                    │
│  ├── 竞品爬虫 Agent ─── harness-browser                  │
│  ├── 舆情分析 Agent ─── 知识库 RAG + 情感分析 subagent   │
│  ├── 报告生成 Agent ─── ask_agent 多 Agent 分工          │
│  └── 推送执行 Agent ─── IM gateway                       │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                自建扩展层（商业资产）                     │
│  ├── plugins/          运营专用插件集                      │
│  ├── experts/library/  行业专家模板                      │
│  ├── connectors/       定制 Connector                     │
│  └── skills/           运营技能包                        │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              基础设施（客户自备 / 可选托管）                │
│  ├── LLM Provider      OpenAI / DeepSeek / 腾讯混元      │
│  ├── 数据库            SQLite / PostgreSQL               │
│  ├── 浏览器            Chromium (harness-browser 管理)   │
│  └── 存储              本地 / COS / S3                  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Octop 扩展点映射

我们**不修改** `src/octop/infra/` 核心代码（或仅在紧急修复时提交 upstream），所有业务逻辑放在以下扩展点：

| 扩展点 | 路径 | 放什么 | 说明 |
|--------|------|--------|------|
| **第三方插件** | `plugins/` 目录或用户上传 | 爬虫插件、情感分析、报告生成 | YAML 声明 + Python entry，Octop 自动发现加载 |
| **专家模板** | `src/octop/infra/agents/experts/library/<name>/` | SOUL.md + manifest.json + skills/ 子目录 | 一键创建的预设 Agent 配置 |
| **Subagent** | `src/octop/infra/agents/subagents/library/zh/<domain>/` | .md 单文件 | 500+ 内置模板，按需新建行业子智能体 |
| **Connector** | `src/octop/infra/connectors/gateway/adapters/` | 新平台适配器 | OAuth/MCP 网关扩展 |
| **Dashboard 定制** | `dashboard/src/` | 品牌皮肤、运营专用页面 | 改完后 `make build-frontend` |
| **知识库种子** | 专家目录下 `knowledge-base/` | 竞品历史、行业知识 | 专家创建时自动 seed |

### 2.3 插件开发规范

以"竞品爬虫插件"为例，Octop 插件的标准结构：

```
plugins/competitor-crawler/
├── plugin.yaml          # 声明元数据
├── main.py              # 工具函数 entry
└── ui/                  # 可选：Dashboard UI 扩展
    ├── index.js
    └── manifest.json
```

`plugin.yaml` 必填字段：

```yaml
id: competitor-crawler
version: 0.1.0
name: 竞品情报爬虫
description: 爬取竞品电商平台/社交媒体/新闻的价格、上新、舆情
icon: "🕷️"
kind: tool                          # tool | ui | skill
entry: main.py
requires:
  - httpx>=0.27
  - beautifulsoup4>=4.12
ui:                                 # 可选
  entry: ui/index.js
  manifest: ui/manifest.json
```

`main.py` entry 签名（harness-agent 插件协议）：

```python
from __future__ import annotations
from typing import Any
from harness_agent.plugins import PluginContext

async def crawl_competitor(ctx: PluginContext, url: str, platform: str) -> dict[str, Any]:
    """爬取单个竞品页面。ctx 提供 browser / workspace / config 访问。"""
    browser = ctx.browser  # harness-browser 会话
    page = await browser.goto(url)
    # ... 解析页面 ...
    return {"platform": platform, "url": url, "snapshot": {...}}
```

### 2.4 专家模板规范

以"竞品情报专家"为例，放在 `src/octop/infra/agents/experts/library/competitor-intel/`：

```
competitor-intel/
├── manifest.json           # 注册到专家库
├── SOUL.md                  # 核心行为准则（对应 harness-agent system prompt）
├── IDENTITY.md              # 身份设定
├── USER.md                  # 用户指南
├── HEARTBEAT.md             # 定时任务模板
├── AGENTS.md                # 子 Agent 编排配置
├── BOOTSTRAP.md             # 创建时的初始化动作
├── knowledge-base/          # 可选：知识库 seed 数据
│   └── raw/
└── skills/                  # 可选：技能脚本
    └── competitor-monitor/
```

`manifest.json` 必填字段：

```json
{
  "id": "competitor-intel",
  "label": { "zh": "竞品情报专家", "en": "Competitor Intel" },
  "description": {
    "zh": "自动爬取竞品价格/上新/舆情，定时推送异动报告到飞书/企微",
    "en": "Auto-scrape competitor pricing, launches, and sentiment — delivers change alerts to IM"
  },
  "prompt_files": ["SOUL.md", "IDENTITY.md", "HEARTBEAT.md"],
  "quick_prompts": [
    {
      "title": { "zh": "今日竞品异动", "en": "Today's competitor changes" },
      "prompt": { "zh": "爬取我关注的竞品，列出今天的价格变动、新上架商品和负面评论。", "en": "..." }
    }
  ],
  "task_examples": ["每天 08:00 推送竞品异动报告到飞书群"]
}
```

---

## 3. 分阶段交付计划

### 3.1 阶段总览

```
Phase 1 (Week 1-4)   MVP · SKU-1 竞品情报机器人
Phase 2 (Week 5-8)   SKU-2 舆情监控 + 自动响应
Phase 3 (Week 9-16)  SKU-3 企业运营中台 + 私有化部署工具链
Phase 4 (Week 17+)   Marketplace · 专家/插件生态
```

---

### 3.2 Phase 1 · MVP · SKU-1 竞品情报机器人（Week 1-4）

**目标：** 交付一个可付费的竞品情报 SaaS，¥99-299/月

**交付物：**

| # | 模块 | 类型 | Octop 扩展点 | 预估工时 | 验收标准 |
|---|------|------|-------------|---------|----------|
| 1.1 | 竞品爬虫插件 | plugin | `plugins/competitor-crawler/` | 3d | 能爬淘宝/京东/拼多多商品页（静态+动态），输出标准化 JSON |
| 1.2 | 社交媒体爬虫插件 | plugin | `plugins/social-scraper/` | 4d | 能爬小红书/抖音/B站搜索结果页（需处理 CDP 登录态） |
| 1.3 | 竞品情报专家模板 | expert | `experts/library/competitor-intel/` | 2d | 一键创建后自动配置 Cron + Proactive + 爬虫插件 |
| 1.4 | 价格异动检测 | subagent | `subagents/library/zh/marketing/` 下新建 | 2d | 对比历史数据（知识库），标记 ±10% 变动为异动 |
| 1.5 | 日报生成专家 | subagent | 同上 | 1d | 按模板输出 Markdown 日报，含异动摘要 + 来源链接 |
| 1.6 | 飞书/企微推送集成 | — | Octop 原生 `infra/gateway/` | 0.5d | 配置 channel kind="feishu"/"wecom"，Cron 触发推送 |
| 1.7 | Dashboard 任务管理页面 | frontend | `dashboard/src/pages/` | 3d | 可视化配置监控目标、Cron 时间、推送群 |
| 1.8 | 种子客户获取 + 反馈循环 | ops | — | 2d | 3 个免费种子客户 → 5 个付费客户（¥99/月试水） |

**技术要点：**

- 爬虫插件必须处理反爬：harness-browser 支持持久化 profile（`--browser-profile`），让 Agent 用真实浏览器会话绕过滑块验证
- 价格异动检测走 Octop 知识库：爬取结果写入 workspace 文件 → Agent 用 `search_knowledge` 对比历史快照
- Cron 走 Octop 原生：`POST /api/cron` 创建任务，`task_type` 设为 `"agent_turn"`，天然支持去重和重试

**验收 Checklist：**

```bash
# ☐ 插件能被 Octop 发现
curl POST /api/plugins -d '{"url": ".../competitor-crawler"}'

# ☐ 专家能一键创建 Agent
curl POST /api/experts/competitor-intel/agent -d '{"name": "我的竞品情报员"}'

# ☐ Cron 自动触发（等待 1 小时后验证）
grep -r "cron" ~/.octop/logs/octop.log | tail -20

# ☐ 飞书群收到推送
#   （手动触发：POST /api/cron/{id}/trigger）

# ☐ make all 通过
make all
cd dashboard && npx tsc --noEmit
```

---

### 3.3 Phase 2 · SKU-2 舆情监控 + 自动响应（Week 5-8）

**目标：** 扩展到舆情监控，¥1999-9999/月

**交付物：**

| # | 模块 | 类型 | Octop 扩展点 | 预估工时 | 验收标准 |
|---|------|------|-------------|---------|----------|
| 2.1 | 舆情关键词追踪插件 | plugin | `plugins/sentiment-tracker/` | 3d | 定时爬取指定关键词在小红书/知乎/微博的搜索结果 |
| 2.2 | 情感分析 subagent | subagent | `subagents/library/zh/marketing/` 新建 | 2d | 识别正面/中性/负面，负面热度 ≥ 阈值时触发告警 |
| 2.3 | 危机分级专家 | subagent | 同上 | 2d | 按热度+评论数+传播链分 3 级：观察 / 关注 / 紧急 |
| 2.4 | 内部话术库 | expert | 专家模板 `knowledge-base/` | 1d | 客户可上传 CSV/Markdown 话术库，知识库 RAG 匹配 |
| 2.5 | 自动评论回复插件 | plugin | `plugins/social-replier/` | 4d | harness-browser 登录后自动在评论区回复，话术来自知识库 |
| 2.6 | 多 Agent 编排配置 | expert | `AGENTS.md` 新建 | 2d | 爬虫 → 分析 → 告警 Agent 按 ask_agent 链路编排 |
| 2.7 | Dashboard 舆情监控页面 | frontend | `dashboard/src/pages/` | 4d | 关键词配置、热度趋势图、告警记录、自动回复开关 |
| 2.8 | 危机告警 Webhook | api router | `api/routers/proactive_care.py` 扩展 | 2d | 紧急级舆情同时推 IM + HTTP webhook（客户自定义端点） |
| 2.9 | 种子客户付费转化 | ops | — | 2d | 至少 2 个客户升级到 SKU-2（¥1999/月） |

**技术要点：**

- 自动回复必须走 HITL（Human-in-the-loop）审批：Octop 原生 `infra/gateway/hitl/` 模块已支持，在插件里标记回复为 `require_approval=true`
- 多 Agent 分工用 Octop `PeerAgentMiddleware`（`manager.py:2787`）：主 Agent 调 `ask_agent` 把分析工作委派给分析 Agent，分析 Agent 再调爬虫 Agent
- 热度计算：Agent 直接读页面数字（评论数、点赞数、转发数），按 `log(评论数) + log(点赞数) × 0.5` 加权

---

### 3.4 Phase 3 · SKU-3 企业运营中台 + 私有化部署（Week 9-16）

**目标：** 交付私有化部署方案，3w-10w 部署费

**交付物：**

| # | 模块 | 类型 | Octop 扩展点 | 预估工时 | 验收标准 |
|---|------|------|-------------|---------|----------|
| 3.1 | 电商后台 Connector | connector | `connectors/gateway/adapters/ecom_backend.py` | 5d | OAuth 对接淘宝开放平台 / 京东开放平台 / 拼多多开放平台 |
| 3.2 | CRM Connector | connector | `connectors/gateway/adapters/crm_*.py` | 4d | 企微 / Salesforce / 自研 CRM 适配 |
| 3.3 | 自动改价 / 上新插件 | plugin | `plugins/ecom-automation/` | 5d | 接收 Agent 决策 → 浏览器 AI+ 操作电商后台（API 不行时兜底走 UI） |
| 3.4 | 客服 Agent 专家 | expert | `experts/library/ecom-cs/` | 3d | 企微/Discord 群自动回复，知识库 RAG + 复杂问题转人工 |
| 3.5 | 运营日报聚合 Agent | expert | `experts/library/ops-daily/` | 2d | 每天聚合各渠道数据（电商销售/客服响应/舆情趋势），推群 |
| 3.6 | 部署脚手架 | scripts | `scripts/deploy/` 新建 | 5d | `./deploy.sh --customer XXX` → 一键 Octop + PostgreSQL + Nginx + SSL |
| 3.7 | 品牌定制 Dashboard | frontend | `dashboard/src/styles/` 主题变量 | 3d | 客户 Logo / 配色 / 登录页定制 |
| 3.8 | 运维监控面板 | api + frontend | `api/routers/observability.py` + Dashboard 页 | 3d | Agent 运行状态 / Token 用量 / 插件健康度 |
| 3.9 | 交付文档 + 培训 | docs | `docs/deploy/` 新建 | 3d | 部署指南 / 管理员手册 / 常见问题 |
| 3.10 | 第一个私有化项目 | ops | — | 持续 | 签单 → 部署 → 培训 → 运维支持 |

**技术要点：**

- 电商后台 Connector 双通道：**优先走 OAuth API**（稳定），API 不可用时**降级到浏览器 AI+ UI 操作**（兜底）。harness-agent 的 tool guard 在此场景下默认开启审批
- 部署脚手架走 Docker Compose：`docker-compose.yml` 复用 Octop 已有的 `docker/` 模板，追加 `postgres` + `nginx` + `certbot` 服务
- 品牌定制用 Octop Dashboard 已有的主题切换机制（`dashboard/src/styles/themePalettes.ts`），不改核心组件
- 运维监控读 Octop 原生 `METRICS`（`infra/metrics.py`）+ `usage` Repo，无需自建监控系统

---

### 3.5 Phase 4 · 生态 Marketplace（Week 17+）

**目标：** 把 Phase 1-3 的专家/插件沉淀为可分发资产

| # | 模块 | 说明 |
|---|------|------|
| 4.1 | 专家发布工具链 | 复用 Octop 原生 `infra/agents/experts/publish.py` + `skillhub_market.py` |
| 4.2 | 插件 SDK | 把 Phase 1-3 的插件打包成可上传格式，配合 `PluginManager` |
| 4.3 | Marketplace 前端 | 在 Dashboard 里加"专家商店"页面，付费下载（先手动记账，后续 Stripe 接入） |
| 4.4 | 贡献者分成 | 社区贡献专家/插件的开发者获得 50-70% 分成 |

---

## 4. 详细模块依赖关系

```
Phase 1:
  plugins/competitor-crawler/          ← 无依赖，harness-browser
  plugins/social-scraper/              ← 无依赖，harness-browser  
  experts/library/competitor-intel/    ← 依赖上面两个 plugin + subagent
  subagent (价格异动检测)               ← 依赖 Octop 知识库 API
  Dashboard 任务管理页面               ← 依赖 Octop REST API (/api/cron, /api/channels)

Phase 2:
  plugins/sentiment-tracker/           ← 复用 Phase 1 的 social-scraper 代码
  plugins/social-replier/              ← 依赖 harness-browser + HITL
  多 Agent 编排配置                    ← 依赖 Octop ask_agent (PeerAgentMiddleware)

Phase 3:
  Connector (ecom / CRM)               ← 依赖 Octop OAuth gateway
  plugins/ecom-automation/             ← 依赖 Connector + harness-browser (降级)
  部署脚手架                           ← 依赖 Octop Docker 镜像
```

---

## 5. 技术栈清单

### 5.1 后端（全走 Octop 现有技术栈）

| 组件 | 选型 | 版本 | 说明 |
|------|------|------|------|
| Python | 3.12+ | — | Octop 原生 |
| Web 框架 | FastAPI | — | Octop 原生 |
| Agent Runtime | harness-agent | ≥1.0.9 | Octop 依赖 |
| IM 桥接 | harness-gateway | ≥0.9.7 | Octop 依赖 |
| 浏览器 | harness-browser | ≥0.7.8 | Octop 依赖 |
| 数据库 | SQLite（默认）/ PostgreSQL | — | Octop 原生双栈 |
| 调度 | APScheduler | — | Octop 原生，Cron Manager 底层 |
| LLM | OpenAI / DeepSeek / 腾讯混元 / Ollama | 客户自选 | Octop Provider 体系 |

### 5.2 前端（全走 Octop Dashboard）

| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | React 18 + TypeScript + Vite | Octop 原生 |
| UI 库 | Ant Design | Octop 原生 |
| 图表 | Ant Design Charts（ant-design/charts） | 舆情监控热度趋势 |
| HTTP | Octop 原生 `dashboard/src/api/request.ts` | 复用，加新模块 |

### 5.3 运维工具链

| 组件 | 选型 | 说明 |
|------|------|------|
| 容器 | Docker + Docker Compose | Octop 原生支持 |
| 反向代理 | Nginx | 部署脚手架内置 |
| TLS | Let's Encrypt / Octop `infra/setup/tls/` | 一键签发 |
| 备份 | Octop 原生 `infra/backup/` | auto backup 配置 |
| 日志 | Octop 原生 logging + `infra/metrics.py` | 无需自建 ELK |

---

## 6. 代码仓库结构

```
ai-ops/                                  # 商业扩展层仓库（独立于 Octop）
├── plugins/                             # 自建插件集
│   ├── competitor-crawler/
│   │   ├── plugin.yaml
│   │   └── main.py
│   ├── social-scraper/
│   ├── sentiment-tracker/
│   ├── social-replier/
│   └── ecom-automation/
├── experts/                             # 自建专家模板（直接拷贝到 Octop 对应目录）
│   ├── competitor-intel/
│   ├── public-opinion/
│   ├── ecom-cs/
│   └── ops-daily/
├── subagents/                           # 自建子智能体（.md 文件）
│   ├── zh/marketing/price-anomaly-detector.md
│   ├── zh/marketing/crisis-classifier.md
│   └── zh/marketing/sentiment-analyzer.md
├── connectors/                          # 自建 Connector
│   ├── ecom_backend.py
│   └── crm_salesforce.py
├── scripts/
│   ├── deploy/                          # Phase 3 部署脚手架
│   │   ├── deploy.sh
│   │   ├── docker-compose.yml
│   │   └── README.md
│   └── seed/                            # 专家模板一键安装
│       └── install-experts.sh
├── docs/
│   ├── deploy/                          # 交付文档
│   │   ├── deployment-guide.md
│   │   ├── admin-manual.md
│   │   └── faq.md
│   └── plugin-development.md            # 插件开发指南
├── dashboard/
│   └── src/                             # Dashboard 定制增量（diff）
│       ├── pages/CompetitorMonitor.tsx
│       ├── pages/PublicOpinion.tsx
│       └── styles/brand-theme/
├── pyproject.toml                       # 仅声明 Octop 版本依赖
├── Makefile
│   ├── install-plugins:    # 拷贝插件到 Octop 目录
│   ├── install-experts:    # 拷贝专家到 Octop 目录
│   ├── install-subagents:  # 拷贝子智能体到 Octop 目录
│   ├── build-frontend:     # Dashboard 定制 + make build-frontend
│   └── build-deploy:       # 打包为交付物
└── README.md
```

**关键决策：** 商业扩展层**独立仓库**，通过 `make install-*` 脚本拷贝到本地 Octop 开发目录。不在 Octop 仓库里直接写业务代码，避免 upstream 合并冲突。

---

## 7. 验收标准与测试策略

### 7.1 测试分层

| 层级 | 工具 | 覆盖范围 | 频率 |
|------|------|---------|------|
| 插件单元测试 | `uv run pytest` | 爬虫解析逻辑、异动检测算法、情感分类 | 每次提交 |
| 专家模板测试 | Octop 原生 pytest（`tests/unit/agents/test_expert_catalog.py`） | manifest.json 格式、prompt 注入、task_examples 解析 | 每次提交 |
| 集成测试 | Octop 原生 integration suite | Cron → Agent → Plugin → IM Gateway 全链路 | PR 合并前 |
| 端到端测试 | 自研脚本 | 完整竞品情报日报生成流程（真实 Chromium） | 每日 CI |
| 跨平台 | Octop CI（GitHub Actions Linux + Windows） | 所有测试必须双平台通过 | 每次推送 |

### 7.2 每个 Phase 的验收 Checklist

```bash
# Phase 1 核心验证
make all                                    # Octop 完整测试通过
make install-plugins install-experts        # 安装扩展层
cd dashboard && npx tsc --noEmit            # Dashboard 类型检查
curl POST /api/agents -d '{...competitor-intel...}'   # 创建专家 Agent
curl POST /api/cron -d '{...每日08:00...}'             # 配置 Cron
# 手动验证：1 小时后检查飞书群是否收到推送

# Phase 2 新增验证
curl POST /api/cron/{id}/trigger            # 触发舆情扫描
curl GET /api/hitl/pending                  # HITL 审批队列有记录
# 手动验证：审批后评论区自动回复

# Phase 3 新增验证
docker compose up -d                        # 部署脚手架一键启动
curl GET /api/observability/health          # 运维面板数据
# 手动验证：客户管理员登录 Dashboard，自助创建 Agent + Cron
```

---

## 8. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| 爬虫被反爬封禁 | 高 | MVP 不可用 | harness-browser 持久化 profile + 模拟人类行为（随机延迟 + 滚动 + 鼠标轨迹）；优先走 OAuth API，浏览器 UI 作为降级 |
| harness-browser 新 Chromium 版本兼容性 | 中 | 运行时崩溃 | Phase 1 固定 Chromium 版本；`pyproject.toml` 锁定 harness-browser 版本号；CI 跑真实浏览器测试 |
| Octop upstream 重构导致扩展点失效 | 中 | 业务代码失效 | 独立仓库，扩展层与 Octop 通过明确的 Plugin API / Connector API 契约；每个 Octop release 验证一次兼容性 |
| LLM Provider 切换（客户换便宜的） | 低但常见 | 成本波动 | Phase 1 就走 Octop Provider 体系，所有 Prompt 走标准 LangGraph 工具调用协议，模型无关 |
| 客户私有化部署运维能力不足 | 高 | 续费率低 | Phase 3 部署脚手架 + 运维监控面板 + 年运维服务包（20-30% 年费） |
| 自动回复出错（敏感词/违规） | 中 | 品牌公关事故 | HITL 审批作为**强默认**，不审批不回复；话术库走知识库 RAG 严格匹配；审计日志完整记录每一条回复 |

---

## 9. 里程碑与交付时间线

```
Week 4  ──► Phase 1 交付：竞品情报机器人 MVP + 5 个付费种子客户
Week 8  ──► Phase 2 交付：舆情监控 + 自动回复 + ¥1999/月付费转化
Week 16 ──► Phase 3 交付：部署脚手架 + 第一个私有化项目签单
Week 24 ──► Phase 4 启动：专家 Marketplace v0.1
```

---

## 10. 团队配置建议

| 角色 | 人数 | 职责 | 何时加入 |
|------|------|------|---------|
| 后端 / Octop 扩展开发 | 1-2 | 插件、Connector、专家模板 | Week 1 起全程 |
| 前端 / Dashboard 定制 | 1 | 运营任务管理页、舆情监控页、品牌皮肤 | Week 1 起，Phase 3 可兼职 |
| 产品 / 客户对接 | 1 | 种子客户获取、需求迭代、签单 | Week 1 起全程 |
| 运维 / 部署支持 | 0.5 | 部署脚手架、私有化运维 | Week 8 起（Phase 3 前到位） |

---

## 附：关键 Octop 模块速查

| 我想做什么 | Octop 入口 |
|-----------|-----------|
| 新建插件 | `plugins/<id>/plugin.yaml` + `main.py`（`harness_agent.plugins.PluginContext`） |
| 新建专家 | `src/octop/infra/agents/experts/library/<name>/` + `manifest.json` |
| 新建子智能体 | `src/octop/infra/agents/subagents/library/<lang>/<domain>/<name>.md` |
| 新建 Connector | `src/octop/infra/connectors/gateway/adapters/<name>.py` |
| 触发 Cron | `POST /api/cron` → task_type="agent_turn" |
| 推 IM 群 | `POST /api/channels` → kind="feishu"/"wecom"；Agent 工具里调 `send_message` |
| 用浏览器 | harness-browser → `ctx.browser.goto(url)` |
| 知识库 RAG | `POST /api/knowledge_bases/{id}/search`；Agent 工具 `search_knowledge` |
| 多 Agent 分工 | Agent prompt 里写 `ask_agent`；`manager.py:2787` PeerAgentMiddleware |
| 审批危险操作 | 插件返回标记 `require_approval=true`；HITL 队列在 `GET /api/hitl/pending` |
| 热重载配置 | 改完插件/专家后 Agent 自动 reload（PluginManager 已监听） |
