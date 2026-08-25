# Phase 22 — Production Release Gate

## 状态

Phase 22 的发布证据、双阶段门禁、职责分离、管理 API、CLI 和运营台已经实现。实现完成不等于已经生产发布：当前只有在真实生产环境生成候选并逐项通过门禁后，才允许流水线推进状态。

系统不会保存部署密钥，也不会从运营台直接操作云平台。实际构建、部署、流量切换和基础设施回滚仍由受控 CI/CD 执行；知牛只记录不可变证据和流水线引用。

## 双阶段状态机

1. 流水线生成固定 commit、API/Web 镜像 digest、配置指纹、SBOM SHA-256、备份 SHA-256 和恢复演练时间，创建 `draft` 候选。
2. 与候选创建人不同的工程审批人记录 `engineering` 批准；生产配置保持 `registration_mode=closed`。
3. `closed_deployment` 检查生产安全配置、数据库和候选迁移头、连续质量/E2E/安全结果、72 小时内恢复演练、注册关闭、自动化硬关闭及工程批准。通过后为 `ready_closed`。
4. CI/CD 部署同一镜像；记录不可变部署引用前，服务端会再次实时执行关闭部署检查。成功后为 `deployed_observing`。
5. 完成观察后，将动态访问模式切换为 `invite_only`。此动态门禁状态不属于镜像 digest；每次评估会把实际值写入门禁证据。
6. `invite_activation` 要求 24 小时内的 production / production usage scope Provider 验收、真实 Resend 凭证与健康诊断、真实 delivered 邮件和已处理 webhook、法律与数据使用批准、P0/P1 为零、容量可用、自动化硬关闭，以及工程、数据合规、产品运营三个不同人的批准。
7. 记录 `released` 前服务端再次实时执行全部邀请检查。任何漂移都会拒绝状态推进。事故可记录 `failed` 或 `rolled_back`，但不会删除此前证据。

## 职责与权限

- 创建人不能批准自己创建的候选。
- 同一候选中，同一账号只能承担一个审批角色。
- `security_admin` 可承担工程或数据合规之一；`operations` 只可承担产品运营。
- 评估、批准和部署事件均需要 cookie 会话、CSRF、允许的 Origin、相应 capability 和短时 step-up。
- 移动运营台只读；高风险动作只在桌面布局显示。

## CLI

候选证据 JSON 使用 API 的 `ProductionReleaseCandidateCreate` 结构，不得包含凭证、客户数据或原始扫描报告：

```text
uv run python -m zhaoniu_api.cli create-production-release --evidence-file release.json --operator-email creator@example.com
uv run python -m zhaoniu_api.cli production-release-status CANDIDATE_ID
uv run python -m zhaoniu_api.cli run-production-release-gate CANDIDATE_ID --gate closed_deployment
uv run python -m zhaoniu_api.cli approve-production-release CANDIDATE_ID --approval-role engineering --decision approved --operator-email engineer@example.com
uv run python -m zhaoniu_api.cli record-production-deployment CANDIDATE_ID --event deployed --deployment-ref pipeline/run/123 --operator-email operator@example.com
uv run python -m zhaoniu_api.cli run-production-release-gate CANDIDATE_ID --gate invite_activation
```

`configuration_fingerprint` 标识不可变部署输入，不包含后续受审计的 `registration_mode` 动态开关；该开关的实际值和时间保存在每次 gate item 中。

## 当前边界

- Phase 22 不开放公开注册、不自动发送 Beta 邀请、不启用全市场自动化。
- 不允许用模拟邮件、开发用途数据或单独重跑成功替代真实证据。
- `ready_closed`、`deployed_observing` 和 `ready_invites` 都不是“生产就绪”宣传口径；只有流水线记录 `released` 且当前证据可追溯时，才表示内部发布状态完成。
- 生产 Resend 域名、Provider 商业用途授权和真实生产验收仍是外部前置条件；缺失时门禁保持阻断。

## 验收

- 迁移头：`20260826_0027`，`alembic check` 无 ORM 漂移。
- 新增公开面仅为受保护的 `/api/v1/admin/releases` 管理路由，不改变研究 API 合同。
- 所有失败使用稳定 reason code；证据仅含有界、非敏感摘要及 SHA-256 指纹。
- 同一失败不能通过覆盖旧记录消失：每次 gate run 和 item 都是新行。
