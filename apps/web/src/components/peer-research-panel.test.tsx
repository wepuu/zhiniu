import type { PeerComparisonEnvelope } from "@zhaoniu/api-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PeerResearchPanel } from "./peer-research-panel";

describe("PeerResearchPanel", () => {
  it("summarizes a ready benchmark with no comparable peer metrics", () => {
    const envelope = {
      status: "ready",
      symbol: "600519",
      canonical_symbol: "600519.SH",
      industry: {
        taxonomy_code: "akshare_dev_industry",
        taxonomy_version: "phase6-dev-v1",
        industry_code: "dev_baijiu",
        industry_name: "白酒",
        source: "stock_master_or_phase6_dev_seed",
        source_reference: "phase6_dev_seed",
        commercial_use_status: "TBD / requires legal review",
        redistribution_status: "TBD / requires legal review",
      },
      peer_universe_fingerprint: "peer-fingerprint",
      knowledge_cutoff: "2026-08-19T00:00:00Z",
      items: [
        {
          metric_code: "roe",
          dimension: "profitability",
          status: "insufficient_peers",
        },
        {
          metric_code: "revenue",
          dimension: "growth",
          status: "missing_metric",
        },
      ],
      total: 2,
    } as PeerComparisonEnvelope;

    render(<PeerResearchPanel envelope={envelope} />);

    expect(
      screen.getByRole("heading", { name: "同行有效样本不足" }),
    ).toBeInTheDocument();
    expect(screen.getByText("样本不足 1")).toBeInTheDocument();
    expect(screen.getByText("公司指标缺失 1")).toBeInTheDocument();
    expect(screen.queryByText("roe")).not.toBeInTheDocument();
  });
});
