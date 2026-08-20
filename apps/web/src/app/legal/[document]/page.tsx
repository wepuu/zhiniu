import { ArrowLeft, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

const documents = {
  terms: {
    title: "用户协议",
    version: "2026-08-v1",
    lead: "本协议说明受邀用户使用知牛研究工作台时的基本权利、责任与服务边界。",
    sections: [
      [
        "服务定位",
        "知牛提供证据驱动的 A 股研究工具，不提供买入、卖出、目标价、收益概率或个性化证券投资建议。",
      ],
      [
        "账户安全",
        "账户仅限本人使用。请妥善保管密码、邀请信息和激活码；发现异常登录时应立即撤销会话并联系客服。",
      ],
      [
        "数据与可用性",
        "行情、财务、公告和模型服务可能因上游数据源或网络状态暂时降级。用户应独立核对关键事实。",
      ],
      [
        "受控体验",
        "当前服务采用邀请注册。运营方可根据系统容量、数据授权和合规状态调整新用户准入。",
      ],
    ],
  },
  privacy: {
    title: "隐私政策",
    version: "2026-08-v1",
    lead: "我们只处理运行账户、自选股、研究工作区和安全保护所必需的信息。",
    sections: [
      [
        "处理的信息",
        "包括注册邮箱、密码散列、登录会话、安全审计信息，以及你主动创建的自选股、提醒和筛选方案。",
      ],
      [
        "安全措施",
        "密码和访问 Token 不以明文保存；敏感写操作使用会话、CSRF、Origin 校验和速率限制保护。",
      ],
      [
        "第三方服务",
        "事务邮件、模型和数据 Provider 仅在相应能力启用时使用，具体生产供应商需在上线前完成审查。",
      ],
      [
        "联系与申请",
        "初期可通过设置页所示客服渠道提出信息查阅、更正或删除申请；自助数据中心将在后续阶段完善。",
      ],
    ],
  },
  risk: {
    title: "研究风险揭示",
    version: "2026-08-v1",
    lead: "研究结果用于辅助核对公开事实，不替代独立判断或持牌专业服务。",
    sections: [
      [
        "数据时效",
        "财务报告、公告、行业分类和行情可能存在延迟、修订、缺失或口径差异。",
      ],
      [
        "研究边界",
        "筛选、同行位置、事件关注度和 AI 解读不表示投资质量、推荐顺序或预期收益。",
      ],
      [
        "用户责任",
        "任何决策前应核对交易所公告、公司披露和其他可靠来源，并结合自身情况独立判断。",
      ],
    ],
  },
  ai: {
    title: "AI 内容说明",
    version: "2026-08-v1",
    lead: "知牛会对 AI 生成或解析内容提供清晰标识，并将确定性计算与模型文本分开。",
    sections: [
      [
        "AI 股票体检",
        "模型只能解释已冻结研究快照并引用证据，不能计算财务指标、给出目标价或买卖建议。",
      ],
      [
        "AI 条件解析",
        "模型只生成候选筛选条件。用户确认后，实际筛选由确定性引擎执行。",
      ],
      [
        "核对要求",
        "AI 文本可能不完整或存在错误，请通过页面中的证据入口核对原始事实。",
      ],
    ],
  },
} as const;

export function generateStaticParams() {
  return Object.keys(documents).map((document) => ({ document }));
}

export default async function LegalDocumentPage({
  params,
}: {
  params: Promise<{ document: string }>;
}) {
  const { document } = await params;
  const content = documents[document as keyof typeof documents];
  if (!content) notFound();
  return (
    <main className="bg-mist min-h-screen px-4 py-8 sm:py-12">
      <article className="border-ink/10 bg-paper shadow-card mx-auto max-w-3xl rounded-2xl border p-6 sm:p-10">
        <Link
          href="/register"
          className="text-blue inline-flex items-center gap-2 text-sm font-medium"
        >
          <ArrowLeft className="size-4" /> 返回注册
        </Link>
        <div className="mt-8 flex items-start gap-4">
          <span className="bg-blue/8 text-blue grid size-11 shrink-0 place-items-center rounded-xl">
            <ShieldCheck className="size-5" />
          </span>
          <div>
            <p className="font-data text-blue text-[10px] uppercase tracking-[0.18em]">
              Version {content.version}
            </p>
            <h1 className="font-display mt-2 text-3xl font-semibold sm:text-4xl">
              {content.title}
            </h1>
            <p className="text-slate mt-3 leading-7">{content.lead}</p>
          </div>
        </div>
        <div className="mt-9 space-y-7">
          {content.sections.map(([title, body]) => (
            <section key={title} className="border-ink/8 border-t pt-6">
              <h2 className="font-display text-xl font-semibold">{title}</h2>
              <p className="text-slate mt-2 text-sm leading-7">{body}</p>
            </section>
          ))}
        </div>
        <p className="border-risk/15 bg-risk/5 text-slate mt-9 rounded-xl border px-4 py-3 text-xs leading-6">
          当前文本为受控 Beta
          工程版本，正式对外开放前仍需由产品与法律负责人确认。
        </p>
      </article>
    </main>
  );
}
