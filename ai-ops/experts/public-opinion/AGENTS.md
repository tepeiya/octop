# AGENTS.md · 舆情监控专家 · 多 Agent 编排配置

## Agent 编排架构

```
主 Agent（public-opinion）
  ├── ask_agent → social-scraper          爬取社交平台
  ├── ask_agent → sentiment-tracker       情感分类
  ├── ask_agent → crisis-classifier       危机分级
  ├── ask_agent → social-replier          起草回复（需 HITL 审批）
  └── ask_agent → daily-report-generator   生成日报/周报
```

## 触发链路

### 链路 1：定时舆情扫描（每 2 小时）
```
Cron 触发
  → 主 Agent 读 watchlist.json（关键词列表）
  → 对每个关键词、每个平台：
      ask_agent("social-scraper", {platform, keyword, limit: 50})
  → 收集结果 → ask_agent("sentiment-tracker", {text: items})
  → 如果负面数 ≥ 10：
      ask_agent("crisis-classifier", {negative_items, scan_history})
  → 如果分级 = 紧急：
      立即推送 IM 群 + @负责人
  → 写入 opinion/<keyword>/scans/<timestamp>.json
```

### 链路 2：每日舆情日报（09:00）
```
Cron 触发
  → 主 Agent 读 opinion/<keyword>/scans/ 聚合昨日数据
  → ask_agent("daily-report-generator", {report_type: "sentiment_daily", data})
  → 推送到飞书/企微群
```

### 链路 3：自动回复（HITL 强制）
```
负面评论触发回复需求
  → 主 Agent 从知识库匹配话术（RAG search）
  → ask_agent("social-replier", {platform, comment_url, reply_text})
  → social-replier 返回 {require_approval: true, draft: "..."}
  → 主 Agent 写入 HITL 队列：POST /api/hitl
  → 人工审批通过后 → social-replier 执行发送（浏览器 AI+）
```

## ask_agent 调用规范

### 社交爬取委派
```json
{
  "target_agent": "social-scraper",
  "task": "crawl_social_feed",
  "params": {
    "platform": "xiaohongshu",
    "keyword": "XX品牌",
    "limit": 50
  }
}
```

### 情感分析委派
```json
{
  "target_agent": "sentiment-tracker",
  "task": "analyze_sentiment",
  "params": {
    "text": ["评论1", "评论2", ...]
  }
}
```

### 危机分级委派
```json
{
  "target_agent": "crisis-classifier",
  "task": "classify_crisis",
  "params": {
    "negative_items": [...],
    "scan_history": [...]
  }
}
```

### 回复草拟委派
```json
{
  "target_agent": "social-replier",
  "task": "draft_reply",
  "params": {
    "platform": "xiaohongshu",
    "comment_url": "https://...",
    "reply_text": "感谢反馈，我们已..."
  }
}
```

## workspace 文件结构

```
public-opinion/
├── watchlist.json              关键词监控列表
├── opinion/
│   ├── <keyword_key>/
│   │   ├── scans/
│   │   │   ├── 2026-09-15-08.json
│   │   │   ├── 2026-09-15-10.json
│   │   │   └── latest.json
│   │   └── daily/
│   │       └── 2026-09-15.json
├── reports/
│   ├── 2026-09-15.md
│   └── weekly-2026-W37.md
├── alerts/
│   └── dedup.json
└── reply_templates/            话术库（知识库 RAG 源）
    ├── apology.md              道歉话术
    ├── product_issue.md        产品问题话术
    └── service_complaint.md    客服投诉话术
```
