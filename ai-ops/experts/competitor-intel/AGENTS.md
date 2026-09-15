# AGENTS.md · 竞品情报专家 · 多 Agent 编排配置

## Agent 编排架构

```
主 Agent（competitor-intel）
  ├── ask_agent → competitor-crawler     爬取竞品页面
  ├── ask_agent → social-scraper         爬取社交媒体
  ├── ask_agent → price-anomaly-detector 价格异动深度分析
  └── ask_agent → daily-report-generator  生成日报
```

## 触发链路

### 链路 1：用户主动查询
```
用户："帮我看看京东上 XX 品牌今天的价格"
  → 主 Agent 调 crawl_competitor(url, platform="jd")
  → 主 Agent 调 snapshot_diff(current, baseline)
  → 如果有异动 → ask_agent("price-anomaly-detector", {price_change_data})
  → 主 Agent 汇总 → 直接回复用户
```

### 链路 2：Cron 定时日报
```
Cron 触发（每天 08:00）
  → 主 Agent 读取 watchlist（workspace 文件）
  → 对每个竞品调 crawl_competitor → 存快照
  → 对每个快照调 snapshot_diff(current, last_snapshot)
  → 收集所有异动 → ask_agent("daily-report-generator", {report_type: "competitor_daily", data})
  → 报告生成 → send_message 到飞书/企微群
```

### 链路 3：社交媒体舆情扫描
```
用户："帮我看看小红书上 XX 品牌的口碑"
  → 主 Agent 调 crawl_social_feed(platform="xiaohongshu", keyword="XX品牌")
  → 主 Agent 调 crawl_social_comments(platform, note_url) 获取评论区
  → ask_agent("sentiment-analyzer", {items: comments})
  → 如果有负面 → ask_agent("crisis-classifier", {negative_items})
  → 主 Agent 汇总 → 回复用户
```

## ask_agent 调用规范

### 竞品爬取委派
```json
{
  "target_agent": "competitor-crawler",
  "task": "crawl_competitor",
  "params": {
    "url": "https://item.jd.com/100012345.html",
    "platform": "jd",
    "mode": "http"
  }
}
```

### 价格异动分析委派
```json
{
  "target_agent": "price-anomaly-detector",
  "task": "analyze_price_change",
  "params": {
    "product_name": "XX品牌 YYY",
    "current_price": 89.9,
    "baseline_price": 99.9,
    "historical_prices": [99.9, 98.0, 95.0, 89.9]
  }
}
```

### 日报生成委派
```json
{
  "target_agent": "daily-report-generator",
  "task": "generate_report",
  "params": {
    "report_type": "competitor_daily",
    "date": "2026-09-15",
    "data": {"snapshots": [...]}
  }
}
```

## workspace 文件结构

```
competitor-intel/
├── watchlist.json              监控目标列表
├── snapshots/
│   ├── <product_key>/
│   │   ├── 2026-09-14.json     昨日快照
│   │   ├── 2026-09-15.json     今日快照（baseline = 昨日）
│   │   └── latest.json         最新（diff 用）
├── reports/
│   ├── 2026-09-15.md           今日日报
│   └── weekly-2026-W37.md      周报
└── alerts/
    └── dedup.json              告警去重
```
