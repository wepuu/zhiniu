import type { CompanyTimelineEnvelope } from "@zhaoniu/api-client";

export function assertCompanyTimeline(value: unknown): CompanyTimelineEnvelope {
  if (!value || typeof value !== "object") {
    throw new Error("公司研究时间线返回格式无效");
  }
  const payload = value as Partial<CompanyTimelineEnvelope>;
  if (
    !payload.status ||
    !payload.query_cutoff ||
    !Array.isArray(payload.items) ||
    !payload.coverage
  ) {
    throw new Error("公司研究时间线缺少必要字段");
  }
  return payload as CompanyTimelineEnvelope;
}
