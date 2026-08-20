# LLM Provider and Safety Policy

- Production has no implicit model. Deployments must explicitly enable the gateway and configure
  an ordered model chain whose models pass structured-output preflight.
- DeepSeek or Qwen may be preferred only after provider terms, financial-data licensing and data
  handling review. OpenAI and Gemini are technically supported but are not default routes before
  data-export review.
- Each model is attempted once. LiteLLM internal retries are disabled; Zhaoniu owns timeout,
  fallback, total deadline, validation and audit behavior.
- Provider-local network, timeout, rate-limit, authentication, quota, model-availability, parse and
  output-validation failures may fall back. Internal context, repository or unknown errors may not.
- API keys are read only from provider-specific environment variables. Logs, HTTP errors and stored
  call records must contain only redacted categories and codes.
- Do not persist full prompts, raw model responses or reasoning traces. Store only structured valid
  output, public evidence mapping, route/version hashes and bounded operational metadata.
- Public UI must carry an explicit AI-generated label and continue to prohibit buy/sell language,
  target prices, return probabilities, ratings and personalized securities advice.

## Natural-language screening parser

- The parser authors a candidate allow-listed DSL document; it never executes screening or decides
  whether a company matches.
- Input is private and ephemeral: Redis TTL transport only. PostgreSQL stores an HMAC, version
  hashes, validated candidate and grounding spans, never the raw query or raw provider response.
- A deterministic policy gate rejects recommendation, target-price, return-probability and ranking
  requests before any provider call.
- Numeric values, units, time windows, metric/event/industry aliases and source spans must be
  grounded in the original text and current catalog. Validation failure falls back within the
  bounded route; it never silently repairs the candidate.
- One user may have one active parse and thirty parse runs per UTC day. Each configured model is
  attempted once, with at most two attempts and a bounded overall deadline.
- The user must explicitly confirm the rendered candidate before the deterministic Phase 9 engine
  may execute it. Manual builder edits clear parser provenance.
