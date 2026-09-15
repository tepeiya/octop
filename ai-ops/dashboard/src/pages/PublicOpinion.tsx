/**
 * 舆情监控页面
 *
 * 功能：
 * 1. 展示关键词监控列表
 * 2. 展示正/中/负面占比
 * 3. 展示告警列表 + 确认操作
 * 4. Webhook 配置面板
 * 5. 舆情日报列表
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  aiOpsApi,
  type AlertRecord,
  type WebhookConfig,
  type SentimentSummary,
} from "../../api/modules/aiOps";

interface PublicOpinionProps {
  agentId: string;
}

const LEVEL_LABELS: Record<string, string> = {
  urgent: "紧急",
  watch: "关注",
  observe: "观察",
};

const LEVEL_COLORS: Record<string, string> = {
  urgent: "#e74c3c",
  watch: "#f39c12",
  observe: "#3498db",
};

const LEVEL_ICONS: Record<string, string> = {
  urgent: "🔴",
  watch: "🟠",
  observe: "🟡",
};

export const PublicOpinionPage: React.FC<PublicOpinionProps> = ({ agentId }) => {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [webhookConfig, setWebhookConfig] = useState<WebhookConfig | null>(null);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEnabled, setWebhookEnabled] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载告警历史
  const loadAlerts = useCallback(async () => {
    try {
      const result = await aiOpsApi.getAlertHistory(50);
      setAlerts(result.alerts || []);
    } catch {
      setAlerts([]);
    }
  }, []);

  // 加载 Webhook 配置
  const loadWebhookConfig = useCallback(async () => {
    try {
      const cfg = await aiOpsApi.getAlertConfig();
      setWebhookConfig(cfg);
      setWebhookUrl(cfg.url || "");
      setWebhookEnabled(cfg.enabled);
    } catch {
      // 配置尚未初始化
    }
  }, []);

  // 保存 Webhook 配置
  const handleSaveWebhook = async () => {
    setLoading(true);
    setError(null);
    try {
      await aiOpsApi.updateAlertConfig({
        url: webhookUrl,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        timeout_seconds: 10,
        retry_count: 3,
        retry_delay_seconds: 5,
        enabled: webhookEnabled,
      });
      setError(null);
    } catch {
      setError("保存 Webhook 配置失败");
    } finally {
      setLoading(false);
    }
  };

  // 发送测试告警
  const handleTestAlert = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await aiOpsApi.testAlert("watch", "测试关键词");
      if (result.success) {
        setTestResult(`✅ 测试告警发送成功（HTTP ${result.status_code}）`);
        loadAlerts(); // 刷新历史
      } else {
        setTestResult(`❌ 发送失败：${result.error || "未知错误"}`);
      }
    } catch {
      setTestResult("❌ 请求失败，请检查 Webhook 配置");
    } finally {
      setTesting(false);
    }
  };

  // 确认告警
  const handleAcknowledge = async (alertId: string) => {
    try {
      await aiOpsApi.acknowledgeAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) =>
          a.alert_id === alertId ? { ...a, acknowledged: true } : a,
        ),
      );
    } catch {
      // 忽略
    }
  };

  useEffect(() => {
    loadAlerts();
    loadWebhookConfig();
  }, [loadAlerts, loadWebhookConfig]);

  // 统计
  const unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length;
  const urgentCount = alerts.filter(
    (a) => a.level === "urgent" && !a.acknowledged,
  ).length;

  return (
    <div className="public-opinion">
      {/* Header */}
      <div className="opinion-header">
        <h2>舆情监控</h2>
        <div className="opinion-stats">
          <span className="stat-item">
            待处理告警：<strong>{unacknowledgedCount}</strong>
          </span>
          {urgentCount > 0 && (
            <span className="stat-item urgent">
              🔴 紧急：{urgentCount}
            </span>
          )}
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className="opinion-layout">
        {/* 左侧：告警列表 */}
        <div className="opinion-alerts">
          <h3>告警历史（{alerts.length}）</h3>
          {alerts.length === 0 ? (
            <p className="empty-hint">暂无告警记录</p>
          ) : (
            <ul className="alert-list">
              {alerts.map((alert) => (
                <li
                  key={alert.alert_id}
                  className={`alert-item ${alert.level} ${
                    alert.acknowledged ? "acknowledged" : ""
                  }`}
                >
                  <div className="alert-header">
                    <span
                      className="alert-level"
                      style={{ color: LEVEL_COLORS[alert.level] }}
                    >
                      {LEVEL_ICONS[alert.level]} {LEVEL_LABELS[alert.level]}
                    </span>
                    <span className="alert-time">
                      {new Date(alert.timestamp).toLocaleString()}
                    </span>
                    {!alert.acknowledged && (
                      <button
                        onClick={() => handleAcknowledge(alert.alert_id)}
                        className="btn-ack"
                      >
                        确认
                      </button>
                    )}
                  </div>
                  <div className="alert-body">
                    <span className="alert-keyword">[{alert.keyword}]</span>
                    <span className="alert-platform">
                      {alert.platform}
                    </span>
                  </div>
                  <div className="alert-message">{alert.message}</div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 右侧：Webhook 配置 */}
        <div className="opinion-webhook">
          <h3>告警 Webhook 配置</h3>
          <p className="webhook-hint">
            配置后，紧急级舆情告警将自动 POST 到此 URL（支持飞书/钉钉/企微群机器人）。
          </p>

          <div className="webhook-form">
            <label>Webhook URL</label>
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://open.feishu.cn/openapi/bot/v2/hook/xxx"
              className="input-url"
            />

            <label className="checkbox">
              <input
                type="checkbox"
                checked={webhookEnabled}
                onChange={(e) => setWebhookEnabled(e.target.checked)}
              />
              启用 Webhook 推送
            </label>

            <div className="webhook-actions">
              <button
                onClick={handleSaveWebhook}
                disabled={loading || !webhookUrl}
                className="btn-save"
              >
                {loading ? "保存中..." : "保存配置"}
              </button>
              <button
                onClick={handleTestAlert}
                disabled={testing || !webhookUrl || !webhookEnabled}
                className="btn-test"
              >
                {testing ? "发送中..." : "发送测试告警"}
              </button>
            </div>

            {testResult && (
              <div className="test-result">{testResult}</div>
            )}
          </div>

          <div className="webhook-tips">
            <h4>快速接入</h4>
            <ul>
              <li>
                <strong>飞书：</strong>群设置 → 群机器人 → 添加自定义机器人
                → 复制 Webhook URL
              </li>
              <li>
                <strong>钉钉：</strong>群设置 → 智能群助手 → 添加自定义机器人
                → 复制 Webhook URL
              </li>
              <li>
                <strong>企微：</strong>群设置 → 添加群机器人 →
                新建机器人 → 复制 Webhook URL
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PublicOpinionPage;
