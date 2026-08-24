export type PresentationAudience = "consumer" | "admin";

export type PresentationDomain =
  | "exchange"
  | "board"
  | "stock_status"
  | "asset_type"
  | "basis"
  | "fiscal_period"
  | "status"
  | "freshness"
  | "source_kind"
  | "metric_role"
  | "operator_role"
  | "configuration_source"
  | "environment"
  | "credential_state"
  | "scope_type"
  | "event_type";

type PresentationDictionary = Partial<
  Record<PresentationDomain, Record<string, string>>
>;

const dictionaries: PresentationDictionary = {
  exchange: {
    SSE: "上海证券交易所",
    SH: "上海证券交易所",
    SZSE: "深圳证券交易所",
    SZ: "深圳证券交易所",
    BSE: "北京证券交易所",
    BJ: "北京证券交易所",
  },
  board: {
    main: "主板",
    star: "科创板",
    chinext: "创业板",
    beijing: "北交所",
    unknown: "板块待确认",
  },
  stock_status: {
    listed: "上市",
    delisted: "退市",
    suspended: "暂停上市",
    unknown: "状态待确认",
  },
  asset_type: {
    stock: "股票",
    equity: "股票",
    index: "指数",
    fund: "基金",
    unknown: "证券类型待确认",
  },
  basis: {
    ytd: "年初至报告期末累计",
    fy: "年度",
    standalone: "单季度",
    point_in_time: "报告期末",
    ttm: "滚动十二个月",
    market_observation: "市场观察日",
    annualized: "年化口径",
    unknown: "口径未标注",
  },
  fiscal_period: {
    Q1: "一季报",
    H1: "半年报",
    Q3: "三季报",
    FY: "年报",
  },
  status: {
    ready: "已就绪",
    current: "当前有效",
    stale: "可能陈旧",
    available: "可用",
    active: "已启用",
    inactive: "未启用",
    enabled: "已启用",
    disabled: "未启用",
    healthy: "正常",
    degraded: "服务降级",
    unavailable: "不可用",
    unknown: "状态未知",
    not_run: "尚未诊断",
    pending: "等待执行",
    running: "正在执行",
    building: "正在生成",
    succeeded: "执行成功",
    succeeded_with_warnings: "成功但有提醒",
    partial: "部分完成",
    partial_coverage: "部分覆盖",
    failed: "执行失败",
    blocked: "已阻止",
    skipped: "未执行",
    not_built: "尚未生成",
    unsupported: "暂不支持",
    unsupported_template: "模板暂不支持",
    missing_industry: "缺少行业分类",
    insufficient_peers: "同行样本不足",
    missing_metric: "缺少指标",
    incomparable_basis: "口径不可比",
    invalid_inputs: "输入未通过校验",
    not_applicable: "不适用",
    missing_input: "缺少输入",
    insufficient_history: "历史数据不足",
    invalid_input: "输入口径无效",
    empty: "暂无内容",
    no_events: "暂无事件",
    complete: "完整",
    accepted: "已受理",
    completed: "已完成",
    rejected: "已拒绝",
    new: "待处理",
    triaged: "处理中",
    resolved: "已解决",
    verified: "已验证",
    delivered: "已送达",
    review_required: "待审核",
    approved: "已批准",
    not_ready: "未就绪",
    draft: "草稿",
    published: "已发布",
    retired: "历史版本",
    draft_saved: "草稿已保存",
    draft_discarded: "草稿已废弃",
    credentials_removed: "凭据已删除",
  },
  freshness: {
    current: "当前有效",
    stale: "可能陈旧",
    unavailable: "不可用",
  },
  source_kind: {
    fundamental: "基本面研究",
    peer: "同行对比",
    corporate_event: "公司事件",
    valuation: "估值观察",
    market: "市场行情",
    disclosure: "公司公告",
    financial_report: "财务报告",
    metric: "财务指标",
    natural_language: "自然语言选股",
    deterministic: "确定性研究",
    ai_research: "AI 研究",
  },
  metric_role: {
    current: "本期值",
    previous: "上期值",
    prior: "前期值",
    benchmark: "同行基准",
    numerator: "分子",
    denominator: "分母",
    source: "来源值",
  },
  operator_role: {
    operations: "运营管理员",
    security_admin: "安全管理员",
    admin: "管理员",
    viewer: "只读人员",
  },
  configuration_source: {
    database: "数据库托管配置",
    environment: "环境变量配置",
    none: "尚未配置",
  },
  environment: {
    development: "开发环境",
    test: "测试环境",
    staging: "预发布环境",
    production: "生产环境",
  },
  credential_state: {
    missing: "缺少凭据",
    environment: "使用环境变量凭据",
    encrypted: "已加密保存",
  },
  scope_type: {
    global: "全局任务",
    pool: "股票池任务",
    stock: "单只股票",
    symbol: "单只股票",
  },
  event_type: {
    earnings: "业绩披露",
    dividend: "分红派息",
    share_change: "股本变动",
    executive_change: "管理层变动",
    regulatory: "监管事项",
    transaction: "重大交易",
    financing: "融资事项",
    litigation: "诉讼仲裁",
    other: "其他公司事件",
    share_repurchase: "股份回购",
    share_pledge: "股份质押",
    share_unlock: "限售解禁",
    regulatory_action: "监管行动",
    shareholder_change: "股东增减持",
    litigation_arbitration: "诉讼仲裁",
  },
};

const domainFallbacks: Record<PresentationDomain, string> = {
  exchange: "交易所待确认",
  board: "板块待确认",
  stock_status: "状态待确认",
  asset_type: "证券类型待确认",
  basis: "口径未标注",
  fiscal_period: "报告期未标注",
  status: "状态未知",
  freshness: "新鲜度未知",
  source_kind: "其他来源",
  metric_role: "指标值",
  operator_role: "运营人员",
  configuration_source: "配置来源未知",
  environment: "环境待确认",
  credential_state: "凭据状态未知",
  scope_type: "任务范围未知",
  event_type: "其他公司事件",
};

export function translateEnum(
  domain: PresentationDomain,
  code: string | null | undefined,
  audience: PresentationAudience = "consumer",
): string {
  if (!code) return domainFallbacks[domain];
  const translated = dictionaries[domain]?.[code];
  if (translated) return translated;
  return audience === "admin"
    ? `${domainFallbacks[domain]}（${code}）`
    : domainFallbacks[domain];
}

const reasonCodeCopy: Record<string, string> = {
  ai_disabled: "AI 股票体检当前未启用",
  ai_research_not_built: "AI 股票体检尚未生成",
  peer_research_not_built: "同行研究尚未生成",
  financial_insufficient_history: "财务历史数据不足",
  provider_unavailable: "数据服务暂时不可用",
  provider_proxy_unavailable: "数据服务网络通道不可用",
  provider_timeout: "数据服务请求超时",
  provider_connection_failed: "数据服务连接中断",
  provider_rate_limited: "数据服务触发访问频率限制",
  provider_invalid_response: "数据服务返回内容未通过校验",
  dependency_unchanged: "依赖数据没有变化",
  input_unchanged: "输入数据没有变化",
  not_due: "尚未到检查时间",
  already_current: "已有当前有效结果",
  generation_failed: "生成任务失败",
  deterministic_snapshot_missing: "缺少确定性研究快照",
  unsupported_issuer_type: "当前发行人类型暂不支持",
  llm_disabled: "AI 服务当前未启用",
  transactional_email_disabled: "事务邮件服务未启用",
  legal_review_not_approved: "法律审核尚未批准",
  data_use_not_approved: "数据使用审核尚未批准",
};

export function translateReasonCode(
  code: string | null | undefined,
  audience: PresentationAudience = "consumer",
): string {
  if (!code) return "暂无补充说明";
  const translated = reasonCodeCopy[code];
  if (translated) return translated;
  return audience === "admin" ? `其他原因（${code}）` : "其他原因";
}

export type FinancialDisplayContext =
  | "summary"
  | "comparison"
  | "detail"
  | "chart";

export type FinancialDisplaySpec = {
  metricCode?: string | null;
  value: string | number | null | undefined;
  unit?: string | null;
  context?: FinancialDisplayContext;
  digits?: number;
};

const largeMoneyMetrics = new Set([
  "revenue",
  "operating_revenue",
  "parent_net_profit",
  "net_profit",
  "operating_cash_flow",
  "operating_cash_flow_amount",
  "total_assets",
  "total_liabilities",
  "cash",
  "cash_and_equivalents",
  "equity",
  "parent_equity",
  "free_cash_flow",
  "interest_bearing_debt",
  "net_debt",
  "market_cap",
]);

const perShareMetrics = new Set([
  "price",
  "close",
  "open",
  "high",
  "low",
  "pre_close",
  "eps",
  "bps",
  "cash_flow_per_share",
]);

function finiteNumber(value: FinancialDisplaySpec["value"]): number | null {
  if (value == null || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function decimal(value: number, digits: number) {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatFinancialValue({
  metricCode,
  value,
  unit,
  context = "detail",
  digits = 2,
}: FinancialDisplaySpec): string {
  const number = finiteNumber(value);
  if (number == null) return "—";
  const normalizedUnit = unit?.toLowerCase() ?? "";
  const normalizedCode = metricCode?.toLowerCase() ?? "";

  if (
    normalizedUnit === "percent" ||
    normalizedUnit === "percentage" ||
    normalizedUnit === "%"
  ) {
    return `${decimal(number, digits)}%`;
  }
  if (normalizedUnit === "multiple" || normalizedUnit === "ratio") {
    return `${decimal(number, digits)} 倍`;
  }
  if (["cny", "cny_yuan", "yuan"].includes(normalizedUnit)) {
    const useYi =
      largeMoneyMetrics.has(normalizedCode) ||
      ((context === "summary" || context === "comparison") &&
        !perShareMetrics.has(normalizedCode));
    if (useYi) return `${decimal(number / 100_000_000, digits)} 亿元`;
    return `${decimal(number, digits)} 元`;
  }
  return decimal(number, digits);
}

const metricLabels: Record<string, { label: string; abbreviation?: string }> = {
  revenue_yoy: { label: "营业收入同比增长率" },
  parent_net_profit_yoy: { label: "归母净利润同比增长率" },
  revenue_single_quarter_yoy: { label: "单季度营业收入同比增长率" },
  parent_net_profit_single_quarter_yoy: {
    label: "单季度归母净利润同比增长率",
  },
  revenue_cagr_3y: { label: "营业收入三年复合增长率" },
  parent_net_profit_cagr_3y: { label: "归母净利润三年复合增长率" },
  revenue: { label: "营业收入" },
  operating_revenue: { label: "营业收入" },
  parent_net_profit: { label: "归属于母公司股东的净利润" },
  net_profit: { label: "净利润" },
  operating_cash_flow: { label: "经营活动现金流量净额" },
  operating_cash_flow_amount: { label: "经营活动现金流量净额" },
  total_assets: { label: "总资产" },
  total_liabilities: { label: "总负债" },
  cash: { label: "货币资金" },
  market_cap: { label: "总市值" },
  pe_ttm: { label: "市盈率（滚动十二个月）", abbreviation: "PE-TTM" },
  pb: { label: "市净率", abbreviation: "PB" },
  pcf: { label: "市现率", abbreviation: "PCF" },
  roe: { label: "净资产收益率", abbreviation: "ROE" },
  roa: { label: "总资产收益率", abbreviation: "ROA" },
  roe_avg_equity_fy: {
    label: "年度平均净资产收益率",
    abbreviation: "ROE",
  },
  roa_avg_assets_fy: {
    label: "年度平均总资产收益率",
    abbreviation: "ROA",
  },
  parent_net_margin: { label: "归母净利率" },
  operating_cash_flow_yoy: { label: "经营活动现金流同比增长率" },
  ocf_to_parent_net_profit: { label: "现金利润比" },
  accounts_receivable_yoy: { label: "应收账款同比增长率" },
  inventory_yoy: { label: "存货同比增长率" },
  free_cash_flow: { label: "自由现金流" },
  interest_bearing_debt: { label: "有息负债" },
  net_debt: { label: "净负债" },
  goodwill_to_assets: { label: "商誉占总资产比例" },
  pe_ttm_percentile_3y: { label: "市盈率近三年分位" },
  pb_percentile_3y: { label: "市净率近三年分位" },
  current_ratio: { label: "流动比率" },
  debt_to_assets: { label: "资产负债率" },
  gross_margin: { label: "毛利率" },
  net_margin: { label: "净利率" },
  revenue_growth: { label: "营业收入增长率" },
  profit_growth: { label: "净利润增长率" },
};

export function financialMetricLabel(
  metricCode: string,
  fallback?: string | null,
) {
  return metricLabels[metricCode]?.label ?? fallback ?? "财务指标";
}

export function financialMetricAbbreviation(metricCode: string) {
  return metricLabels[metricCode]?.abbreviation ?? null;
}

export function providerDisplayName(provider: string | null | undefined) {
  if (!provider) return "数据服务待确认";
  const names: Record<string, string> = {
    akshare: "AKShare",
    deepseek: "DeepSeek",
    resend: "Resend",
    openai: "OpenAI",
    gemini: "Gemini",
    qwen: "通义千问",
  };
  return names[provider.toLowerCase()] ?? provider;
}

export function researchTitle(
  signalFamily: string | null | undefined,
  title: string,
) {
  if (signalFamily?.startsWith("pb")) {
    if (title.startsWith("PB")) return `市净率${title.slice(2)}`;
  }
  if (signalFamily?.startsWith("pe_ttm")) {
    if (title.startsWith("PE-TTM")) {
      return `市盈率（滚动十二个月）${title.slice(6)}`;
    }
    if (title.startsWith("PE")) return `市盈率${title.slice(2)}`;
  }
  return title;
}
