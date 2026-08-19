import type { EventRadarEnvelope } from "@zhaoniu/api-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventRadarPanel } from "./event-radar-panel";

const ready = {
  status: "ready",
  freshness: "current",
  source_health: "healthy",
  coverage_status: "partial",
  symbol: "600519",
  canonical_symbol: "600519.SH",
  snapshot_id: "00000000-0000-4000-8000-000000000010",
  knowledge_cutoff: "2026-08-19T00:00:00Z",
  generated_at: "2026-08-19T01:00:00Z",
  upcoming_items: [],
  recent_items: [
    {
      section: "recent",
      attention_level: "info",
      attention_rule_id: "routine-disclosure",
      attention_rule_version: "event-attention-v1",
      attention_reason: "记录已披露的公司行动及其进展",
      event: {
        id: "00000000-0000-4000-8000-000000000011",
        symbol: "600519",
        canonical_symbol: "600519.SH",
        event_family: "share_repurchase",
        event_type: "repurchase_completed",
        title: "关于股份回购实施完成的公告",
        event_thread_key: "thread",
        identity_basis: "source_document+family+effective_date",
        source_published_at: "2026-08-18T00:00:00Z",
        known_at: "2026-08-19T00:00:00Z",
        extraction_status: "partial",
        typed_payload: { kind: "share_repurchase" },
        field_lineage: {},
        sources: [
          {
            document_id: "00000000-0000-4000-8000-000000000012",
            source_owner: "cninfo",
            source_document_id: "notice-1",
            title: "关于股份回购实施完成的公告",
            source_url: "https://example.invalid/notice-1",
            source_published_at: "2026-08-18T00:00:00Z",
            source_published_precision: "date",
          },
        ],
      },
    },
  ],
} as EventRadarEnvelope;

describe("EventRadarPanel", () => {
  it("renders ready data and opens evidence on desktop/mobile composition", () => {
    render(
      <EventRadarPanel
        envelope={ready}
        pending={false}
        error={false}
        onRetry={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "事件雷达" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("关于股份回购实施完成的公告"));
    expect(
      screen.getByRole("dialog", { name: "事件证据" }),
    ).toBeInTheDocument();
    expect(screen.getByText("原始披露")).toBeInTheDocument();
  });

  it("keeps transport errors local and retryable", () => {
    const retry = vi.fn();
    render(<EventRadarPanel pending={false} error onRetry={retry} />);
    expect(screen.getByText("事件雷达暂时不可用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("renders no-events as an honest completed state", () => {
    render(
      <EventRadarPanel
        envelope={{ ...ready, status: "no_events", recent_items: [] }}
        pending={false}
        error={false}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText("暂未识别到支持的事件")).toBeInTheDocument();
  });
});
