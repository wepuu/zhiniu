import type { StockReadinessResponse } from "@zhaoniu/api-client";

export function canRetryStockPreparation(
  state: StockReadinessResponse,
): boolean {
  return (
    state.next_action === "retry" &&
    (state.overall_status === "failed" ||
      state.stages.some((stage) => stage.status === "failed"))
  );
}

export function readinessActionLabel(state: StockReadinessResponse): string {
  return {
    view: "可查看已完成研究",
    wait: "系统正在准备，页面会自动更新",
    retry: "准备失败，可受控重试",
    enable_preparation: "自动准备已暂停",
    unsupported: "当前公司类型部分不支持",
  }[state.next_action];
}

export function readinessReasonLabel(reason?: string | null): string | null {
  if (!reason) return null;
  return (
    {
      preparation_stalled: "任务超过等待时间，建议重新准备",
      preparation_failed: "研究准备未完成，建议稍后重试",
      provider_connection_failed: "数据源暂时不可用，已保留已有研究",
      ai_generation_failed: "AI 解读暂时不可用，不影响确定性研究",
      preparation_disabled: "自动准备开关已关闭",
      issuer_template_unsupported: "该公司类型暂不支持完整确定性研究",
      peer_research_unavailable: "同行数据暂不完整",
      extended_source_partial: "公告或同行数据仅部分覆盖",
    }[reason] ?? "部分研究数据仍在准备或覆盖有限"
  );
}

export function formatReadinessTimestamp(value?: string | null): string | null {
  if (!value) return null;
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return null;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(timestamp);
}
