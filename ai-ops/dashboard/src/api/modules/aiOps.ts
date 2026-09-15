/**
 * AI 运营自动化 · API 模块
 *
 * 竞品情报 + 舆情监控的前端 API 封装。
 * 复用 Octop Dashboard 的 request 工具，走标准 /api 前缀。
 */

import { request } from "../request";

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

export interface CompetitorSnapshot {
  url: string;
  platform: string;
  product_name: string;
  price: number | null;
  title: string;
  sales: string;
  rating: number | null;
  comments: number;
  fetched_at: string;
  snapshot_hash: string;
}

export interface SnapshotChange {
  field: string;
  direction: string;
  delta_pct: number | null;
  from: any;
  to: any;
  severity: string;
}

export interface SnapshotDiff {
  url: string;
  platform: string;
  product_name: string;
  is_anomaly: boolean;
  change_count: number;
  changes: SnapshotChange[];
  summary: string;
}

export interface WatchlistItem {
  url: string;
  platform: string;
  product_name: string;
  added_at: string;
}

export interface SentimentSummary {
  keyword: string;
  total_mentions: number;
  positive: number;
  neutral: number;
  negative: number;
  negative_ratio: number;
}

export interface AlertRecord {
  alert_id: string;
  level: "urgent" | "watch" | "observe";
  keyword: string;
  platform: string;
  message: string;
  timestamp: string;
  acknowledged?: boolean;
}

export interface WebhookConfig {
  url: string;
  method: string;
  headers: Record<string, string>;
  timeout_seconds: number;
  retry_count: number;
  retry_delay_seconds: number;
  enabled: boolean;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const aiOpsApi = {
  // ── 竞品情报 ──

  /** 获取竞品监控列表 */
  getWatchlist: (agentId: string) =>
    request<WatchlistItem[]>(
      `/agents/${encodeURIComponent(agentId)}/workspace/file?path=watchlist.json`,
    ),

  /** 获取最新快照 */
  getLatestSnapshot: (agentId: string, productKey: string) =>
    request<CompetitorSnapshot>(
      `/agents/${encodeURIComponent(agentId)}/workspace/file?path=snapshots/${productKey}/latest.json`,
    ),

  /** 获取快照历史 */
  getSnapshotHistory: (agentId: string, productKey: string, limit = 7) =>
    request<CompetitorSnapshot[]>(
      `/agents/${encodeURIComponent(agentId)}/workspace/list?path=snapshots/${productKey}`,
    ),

  /** 获取已生成的日报列表 */
  getReports: (agentId: string, limit = 7) =>
    request<string[]>(
      `/agents/${encodeURIComponent(agentId)}/workspace/list?path=reports`,
    ),

  /** 触发即时竞品扫描（通过 Cron trigger） */
  triggerScan: (agentId: string) =>
    request<{ status: string }>(
      `/cron/trigger`,
      { method: "POST", body: JSON.stringify({ agent_id: agentId }) },
    ),

  // ── 舆情监控 ──

  /** 获取关键词监控列表 */
  getOpinionWatchlist: (agentId: string) =>
    request<WatchlistItem[]>(
      `/agents/${encodeURIComponent(agentId)}/workspace/file?path=watchlist.json`,
    ),

  /** 获取舆情日报列表 */
  getOpinionReports: (agentId: string, limit = 7) =>
    request<string[]>(
      `/agents/${encodeURIComponent(agentId)}/workspace/list?path=reports`,
    ),

  // ── 告警 Webhook ──

  /** 获取 Webhook 配置 */
  getAlertConfig: () =>
    request<WebhookConfig>(`/alerts/config`),

  /** 更新 Webhook 配置 */
  updateAlertConfig: (config: WebhookConfig) =>
    request<{ status: string; config: WebhookConfig }>(
      `/alerts/config`,
      { method: "PUT", body: JSON.stringify(config) },
    ),

  /** 发送测试告警 */
  testAlert: (level: string, keyword: string) =>
    request<{ success: boolean; status_code?: number; error?: string }>(
      `/alerts/test`,
      { method: "POST", body: JSON.stringify({ level, keyword }) },
    ),

  /** 获取告警历史 */
  getAlertHistory: (limit = 50) =>
    request<{ alerts: AlertRecord[] }>(`/alerts/history?limit=${limit}`),

  /** 确认告警已处理 */
  acknowledgeAlert: (alertId: string) =>
    request<{ status: string }>(
      `/alerts/acknowledge?alert_id=${encodeURIComponent(alertId)}`,
      { method: "POST" },
    ),
};
