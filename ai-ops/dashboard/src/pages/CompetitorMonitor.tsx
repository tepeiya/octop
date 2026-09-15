/**
 * 竞品情报监控页面
 *
 * 功能：
 * 1. 展示竞品监控列表（watchlist）
 * 2. 展示最新快照 + 价格趋势
 * 3. 展示异动检测结果
 * 4. 手动触发扫描
 * 5. 查看历史日报
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  aiOpsApi,
  type WatchlistItem,
  type CompetitorSnapshot,
  type SnapshotDiff,
} from "../../api/modules/aiOps";

interface CompetitorMonitorProps {
  agentId: string;
}

const PLATFORM_LABELS: Record<string, string> = {
  jd: "京东",
  taobao: "淘宝",
  pdd: "拼多多",
  xiaohongshu: "小红书",
  douyin: "抖音",
  weibo: "微博",
  zhihu: "知乎",
  bilibili: "B站",
};

const SEVERITY_COLORS: Record<string, string> = {
  high: "#e74c3c",
  medium: "#f39c12",
  low: "#3498db",
  info: "#95a5a6",
};

export const CompetitorMonitorPage: React.FC<CompetitorMonitorProps> = ({
  agentId,
}) => {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);
  const [latestSnapshot, setLatestSnapshot] = useState<CompetitorSnapshot | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载监控列表
  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await aiOpsApi.getWatchlist(agentId);
      setWatchlist(items || []);
      if (items && items.length > 0 && !selectedProduct) {
        setSelectedProduct(items[0].product_name);
      }
    } catch (err) {
      setError("加载监控列表失败，请确认 Agent 已配置 watchlist.json");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  // 加载最新快照
  const loadSnapshot = useCallback(
    async (productName: string) => {
      try {
        const key = productName.replace(/\s+/g, "_").toLowerCase();
        const snapshot = await aiOpsApi.getLatestSnapshot(agentId, key);
        setLatestSnapshot(snapshot);
      } catch {
        setLatestSnapshot(null);
      }
    },
    [agentId],
  );

  // 手动触发扫描
  const handleTriggerScan = async () => {
    setScanning(true);
    try {
      await aiOpsApi.triggerScan(agentId);
    } catch {
      setError("触发扫描失败，请确认 Cron 任务已配置");
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  useEffect(() => {
    if (selectedProduct) {
      loadSnapshot(selectedProduct);
    }
  }, [selectedProduct, loadSnapshot]);

  return (
    <div className="competitor-monitor">
      {/* Header */}
      <div className="monitor-header">
        <h2>竞品情报监控</h2>
        <button
          onClick={handleTriggerScan}
          disabled={scanning}
          className="btn-scan"
        >
          {scanning ? "扫描中..." : "立即扫描"}
        </button>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className="monitor-layout">
        {/* 左侧：监控列表 */}
        <div className="monitor-sidebar">
          <h3>监控目标（{watchlist.length}）</h3>
          {loading ? (
            <p>加载中...</p>
          ) : watchlist.length === 0 ? (
            <p className="empty-hint">
              暂无监控目标。
              <br />
              在对话中告诉 Agent："帮我监控
              https://item.jd.com/XXXX.html 的价格"
            </p>
          ) : (
            <ul className="watchlist">
              {watchlist.map((item, idx) => (
                <li
                  key={idx}
                  className={selectedProduct === item.product_name ? "active" : ""}
                  onClick={() => setSelectedProduct(item.product_name)}
                >
                  <span className="platform-tag">
                    {PLATFORM_LABELS[item.platform] || item.platform}
                  </span>
                  <span className="product-name">{item.product_name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 右侧：快照详情 */}
        <div className="monitor-detail">
          {latestSnapshot ? (
            <div className="snapshot-card">
              <h3>{latestSnapshot.product_name}</h3>
              <div className="snapshot-meta">
                <span className="platform-tag">
                  {PLATFORM_LABELS[latestSnapshot.platform] ||
                    latestSnapshot.platform}
                </span>
                <a
                  href={latestSnapshot.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-link"
                >
                  查看原页面 ↗
                </a>
              </div>

              <div className="snapshot-grid">
                <div className="snapshot-item">
                  <label>当前价格</label>
                  <span className="value price">
                    {latestSnapshot.price !== null
                      ? `¥${latestSnapshot.price}`
                      : "—"}
                  </span>
                </div>
                <div className="snapshot-item">
                  <label>销量</label>
                  <span className="value">{latestSnapshot.sales || "—"}</span>
                </div>
                <div className="snapshot-item">
                  <label>评分</label>
                  <span className="value">
                    {latestSnapshot.rating !== null
                      ? `⭐ ${latestSnapshot.rating}`
                      : "—"}
                  </span>
                </div>
                <div className="snapshot-item">
                  <label>评论数</label>
                  <span className="value">{latestSnapshot.comments}</span>
                </div>
              </div>

              <div className="snapshot-time">
                抓取时间：{new Date(latestSnapshot.fetched_at).toLocaleString()}
              </div>
            </div>
          ) : (
            <div className="empty-detail">
              <p>选择左侧的监控目标查看最新快照</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CompetitorMonitorPage;
