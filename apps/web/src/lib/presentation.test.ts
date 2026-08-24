import { describe, expect, it } from "vitest";

import {
  financialMetricLabel,
  formatFinancialValue,
  researchTitle,
  translateEnum,
  translateReasonCode,
} from "./presentation";

describe("Chinese presentation semantics", () => {
  it("translates market, period and workflow codes", () => {
    expect(translateEnum("exchange", "SSE")).toBe("上海证券交易所");
    expect(translateEnum("board", "main")).toBe("主板");
    expect(translateEnum("stock_status", "listed")).toBe("上市");
    expect(translateEnum("basis", "ytd")).toBe("年初至报告期末累计");
    expect(translateEnum("fiscal_period", "H1")).toBe("半年报");
    expect(translateEnum("status", "succeeded_with_warnings")).toBe(
      "成功但有提醒",
    );
  });

  it("does not expose unknown consumer codes but preserves admin diagnostics", () => {
    expect(translateEnum("status", "future_state")).toBe("状态未知");
    expect(translateEnum("status", "future_state", "admin")).toBe(
      "状态未知（future_state）",
    );
    expect(translateReasonCode("future_reason")).toBe("其他原因");
    expect(translateReasonCode("future_reason", "admin")).toBe(
      "其他原因（future_reason）",
    );
  });

  it("formats company totals in 亿元 and ratios in 倍", () => {
    expect(
      formatFinancialValue({
        metricCode: "operating_cash_flow",
        value: "70690750119.06",
        unit: "CNY",
        context: "comparison",
      }),
    ).toBe("706.91 亿元");
    expect(
      formatFinancialValue({
        metricCode: "market_cap",
        value: "1591141000000",
        unit: "CNY",
        context: "summary",
      }),
    ).toBe("15,911.41 亿元");
    expect(formatFinancialValue({ value: "19.54", unit: "multiple" })).toBe(
      "19.54 倍",
    );
    expect(formatFinancialValue({ value: "5.5895", unit: "ratio" })).toBe(
      "5.59 倍",
    );
  });

  it("uses Chinese metric labels", () => {
    expect(financialMetricLabel("pe_ttm")).toBe("市盈率（滚动十二个月）");
    expect(financialMetricLabel("roe")).toBe("净资产收益率");
  });

  it("uses Chinese names for deterministic valuation titles", () => {
    expect(researchTitle("pb_percentile_3y.band", "PB处于近三年较低分位")).toBe(
      "市净率处于近三年较低分位",
    );
    expect(
      researchTitle("pe_ttm_percentile_3y.band", "PE-TTM进入近三年较高分位"),
    ).toBe("市盈率（滚动十二个月）进入近三年较高分位");
  });
});
