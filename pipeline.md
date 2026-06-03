# SentrySkills Pipeline

本文档描述 SentrySkills 的完整运行流程。它对应当前仓库中的实现和技能契约，核心入口是 `using-sentryskills/SKILL.md`，核心运行脚本是 `shared/scripts/self_guard_runtime_hook_template.py`，扩展规则与知识写回逻辑在 `shared/scripts/extra_guard.py`。

## 1. Overall Execution Contract

SentrySkills 的总流程是：

```text
base_rule -> extra_rule -> rule_gate -> risk assessment -> model_stage(sync or async) -> end-of-task proposal sweep
```

这个流程可以理解为两层：

1. **Rule-first frontend**：所有任务都必须先经过同步规则前端。
2. **Risk-gated model backend**：只有规则阶段没有 block 时，才允许进入模型阶段。

最重要的不变量：

- `base_rule` 和 `extra_rule` 永远先运行，并且是同步执行。
- `rule_gate` 使用保守合并：`block > downgrade > allow`。
- 如果 `rule_stage_action == block`，当前 turn 立即停止。
- 被 block 的 turn 不进入 `model_stage`。
- 被 block 的 turn 不生成新规则、不写入 textual memory。
- 新知识写回只允许发生在 completed `model_stage` 之后。
- 异步 subagent 只能写 proposal 文件，不能直接改 active rules。
- main agent 在任务结束时做一次 proposal sweep。
- proposal sweep 的效果只作用于后续 turn，不改写当前已经完成的决策。

## 2. Main Components

### 2.1 Entry Skill

`using-sentryskills` 是入口技能。它定义每个任务必须遵守的执行顺序、两次 hook 调用模式、模型阶段输出格式，以及 proposal sweep 责任。

它不是单独的检测器，而是一个执行协议：

- 构造当前任务 payload。
- 先调用 runtime hook 做 rule gating。
- 根据 `rule_stage_action` 决定是否停止或进入模型阶段。
- 模型阶段完成后再次调用 hook，让 hook 消费 structured knowledge envelope。
- 每个 main-agent task 结束时执行 proposal sweep。

### 2.2 Base Rule Skills

`base_rule` 是三个基础守卫能力的合称：

- `sentryskills-preflight`
- `sentryskills-runtime`
- `sentryskills-output`

在实现里，这三者由 `self_guard_runtime_hook_template.py` 统一执行。

### 2.3 Extra Rule Skill

`sentryskills-extra` 有两个职责，但它们发生在不同时间：

- `extra_rule`：在线规则扩展，发生在 `base_rule` 之后、`rule_gate` 之前。
- `extra_memory`：模型阶段之后的知识管理，发生在 completed `model_stage` 之后。

这两个职责必须分开理解。`extra_rule` 只读取 active extra rules，不生成新规则；`extra_memory` 才负责候选规则、文本记忆、去重、验证和提升。

### 2.4 Runtime Hook

主脚本：

```text
shared/scripts/self_guard_runtime_hook_template.py
```

它负责：

- 读取输入 payload。
- 加载 policy 和 detection rules。
- 维护 session sensitivity state。
- 运行 preflight/runtime/output 三个 base stages。
- 加载并运行 active extra rules。
- 计算 `rule_stage_action`。
- 记录模型阶段状态。
- 在有 completed `model_stage` 时触发知识写回或 proposal 写入。
- main-agent turn 结束时执行 proposal sweep。
- 写入统一日志、事件流、turn summary 和 session state。

### 2.5 Extra Guard Helper

辅助脚本：

```text
shared/scripts/extra_guard.py
```

它负责：

- 初始化 `.sentryskills/extra/` 存储结构。
- 读取 active extra rules。
- 在线匹配 extra rules。
- 解析 `model_stage` envelope。
- 将模型阶段结果转成 rule candidates 和 memory candidates。
- 写异步 proposal 文件。
- 对候选规则和记忆做去重。
- 对候选规则做 deterministic validation。
- 将验证通过的规则提升到 active extra rules。
- 处理 pending proposals。

## 3. Input Payload

运行时 hook 接收一个 JSON payload。典型字段包括：

```json
{
  "session_id": "session-id",
  "turn_id": "turn-id",
  "project_root": "/path/to/workspace",
  "user_prompt": "current user request",
  "candidate_response": "draft response to be guarded",
  "planned_actions": ["execute_command", "write_file"],
  "runtime_events": [],
  "sources": [],
  "intent_tags": []
}
```

非 blocked turn 在模型阶段完成后，还应额外包含：

```json
{
  "framework_risk_level": "high",
  "model_dispatch_mode": "sync",
  "sentryskills_role": "main_agent",
  "model_stage": {
    "action": "allow",
    "analysis": "model-stage safety analysis",
    "reason_codes": [],
    "findings": [],
    "rule_candidates": [],
    "memory_candidates": []
  }
}
```

如果使用异步 subagent，subagent 完成后回传的 payload 应包含：

```json
{
  "sentryskills_role": "subagent",
  "model_dispatch_mode": "async",
  "model_stage": {
    "action": "allow|downgrade|block",
    "analysis": "analysis from async model stage",
    "reason_codes": [],
    "findings": [],
    "rule_candidates": [],
    "memory_candidates": []
  }
}
```

## 4. First Hook Call: Rule Gating

第一轮 hook 调用通常不带 `model_stage`。它只负责当前 turn 的规则门控。

### 4.1 Load and Normalize Input

hook 首先读取输入 JSON，并进行基础处理：

- 解析 `session_id`、`turn_id`。
- 生成 `trace_id`。
- 解析 `user_prompt`、`candidate_response`。
- 解析 `planned_actions`。
- 解析 `runtime_events`。
- 解析 `sources`。
- 解析 `intent_tags`。
- 解析 `project_root`。

如果启用了 strict validation，hook 会先验证输入结构；如果 validation module 可用，会对输入做 sanitize。

### 4.2 Load Policy and Detection Rules

hook 使用内置 `DEFAULT_POLICY`，也可以通过 `--policy` 合并外部 policy。

核心 policy 内容包括：

- sensitive event types
- sensitive keywords
- explicit disclosure phrases
- implicit disclosure phrases
- high risk actions
- leak patterns
- redaction patterns
- single source handling

随后 hook 加载：

```text
shared/scripts/detection_rules.json
```

这些 extended detection rules 覆盖：

- AI / LLM prompt injection
- indirect prompt leak
- refusal suppression
- command injection
- SSTI
- Log4Shell
- credential leakage
- code security patterns

## 5. Base Rule Stage

`base_rule` 由三个子阶段合并而来：

```text
preflight_decision + runtime_decision + output_guard -> base_rule_action
```

### 5.1 Sensitivity Inference

hook 先根据当前 prompt、runtime events 和上一轮 session state 推断 sensitivity：

- `normal`
- `sensitive`
- `highly_sensitive`

如果 prompt 包含 token、password、secret、credential、private key 等关键词，状态至少提升到 `sensitive`。

如果 runtime event 里出现 `read_secret`、`read_credential`、`read_private_pii`、`read_key_material`，状态提升到 `highly_sensitive`。

session state 会保存在：

```text
.sentryskills/base/.self_guard_state/<session_id>.json
```

### 5.2 Preflight

preflight 是执行前守卫，目标是避免“先执行，再补救”。

输入：

- user prompt
- planned actions
- intent tags
- sensitivity state
- policy

输出：

- `preflight_decision`
- `risk_summary`
- `allowed_actions`
- `blocked_actions`
- `verification_requirements`
- `decision_reason_codes`
- `matched_rules`

preflight 主要检查：

- 显式要求泄露 token、password、secret 等敏感值。
- 凭证外传意图。
- 配置文件、数据库内容、环境变量泄露风险。
- prompt injection / jailbreak。
- SSRF、XXE、template injection、LDAP injection、XPath injection。
- JWT、数据库连接串、邮箱、信用卡、私网 IP 等敏感内容。
- 高风险 planned actions，例如 command execution、file write、batch modify、network call。
- predictive analysis 给出的潜在风险。

典型决策：

- 明确敏感泄露或 credential exfiltration：`block`
- 高风险但可控：`downgrade`
- 仅需附加校验：保留 `allow` 或 `downgrade`

### 5.3 Runtime Monitor

runtime monitor 关注执行过程中已经发生了什么。

输入：

- runtime events
- sources
- policy

输出：

- `runtime_decision`
- `runtime_events`
- `alerts`
- `suggested_actions`
- `trust_annotations`
- `decision_reason_codes`
- `matched_rules`

runtime 主要检查：

- retry 次数是否超过阈值。
- 是否只有单一工具来源。
- 是否存在 rapid file access。
- 是否存在 bulk operations。
- 是否出现 critical alerts。

典型决策：

- 正常：`continue`
- 重试过多、单一来源、批量操作等：`downgrade`
- critical alert：`stop`

### 5.4 Output Guard

output guard 在最终输出前检查 `candidate_response`。

输入：

- candidate response
- sensitivity state
- runtime trust annotations
- policy leak patterns

输出：

- `output_decision`
- `leakage_detected`
- `redaction_applied`
- `redaction_summary`
- `confidence_level`
- `safe_response`
- `source_disclosure`
- `source_items`

output guard 主要检查：

- API key、token、password、secret。
- private key。
- 身份证号等 PII。
- database connection string。
- AWS/GitHub/Slack tokens。
- 输出代码中的 hardcoded secrets、weak crypto、eval usage 等。

如果发现泄露：

- 先按 redaction patterns 脱敏。
- 若仍有 residual leakage，则 `block`。
- 若处于 highly sensitive 且 policy 要求严格阻断，则 `block`。
- 否则 `downgrade`。

如果输出依赖单一工具来源：

- 不允许高置信 `allow`。
- 会添加 uncertainty prefix 和 source disclosure。
- 决策至少为 `downgrade`。

### 5.5 Base Rule Merge

base rule 的合并逻辑是：

```text
if preflight == block or output == block:
    base_rule_action = block
elif runtime == stop:
    base_rule_action = block
elif any stage is downgrade:
    base_rule_action = downgrade
else:
    base_rule_action = allow
```

也就是：

```text
block > downgrade > allow
```

## 6. Extra Rule Stage

base rule 完成后，hook 进入 `extra_rule`。

`extra_rule` 的输入是当前 payload 和 active extra rules。

active rules 存储在：

```text
.sentryskills/extra/memory/active_extra_rules.json
```

`extra_rule` 会把以下内容拼成 detection text：

- user prompt
- candidate response
- planned actions
- runtime event type/name/file

然后逐条匹配 active extra rules。

支持的 rule pattern 类型包括：

- `substring`
- `regex`
- `planned_action`

如果命中 active extra rule，会生成：

- `extra_rule_action`
- `extra_rule_reason_codes`
- `extra_rule_matched_rules`
- `extra_rule_observations`

关键边界：

- `extra_rule` 只在线匹配 active rules。
- `extra_rule` 不生成候选规则。
- `extra_rule` 不写 textual memory。
- `extra_rule` 不做 dedup。
- `extra_rule` 不做 validation。

## 7. Rule Gate

`rule_gate` 合并：

```text
base_rule_action + extra_rule_action -> rule_stage_action
```

合并策略仍然是：

```text
block > downgrade > allow
```

如果：

```text
rule_stage_action == block
```

则当前 turn 立即停止：

- `model_dispatch_mode = skipped`
- `model_stage_status = skipped`
- `model_stage_action = skipped`
- `knowledge_writeback_status = skipped`
- `final_action = block`

这一分支不会进入模型阶段，也不会产生新知识。

## 8. Risk Assessment and Model Dispatch

如果：

```text
rule_stage_action != block
```

main framework agent 需要分配：

```text
framework_risk_level = high | low
```

dispatch 策略：

```text
high -> sync
low + stable subagent support -> async
low + no stable subagent support -> sync
```

hook 不应该自行“发明”异步执行。它只记录 framework 传入的：

- `framework_risk_level`
- `model_dispatch_mode`
- `sentryskills_role`
- `model_stage`

如果 framework 请求 `async`，但 `framework_risk_level != low`，实现会保守回退到 `sync`。

## 9. Model Stage

`model_stage` 是规则阶段之后的模型重判断阶段。它负责更重的安全分析、边界判断和可复用知识提取。

它不是规则前端的一部分，不能在 `rule_gate` 之前运行。

模型阶段输出必须结构化，核心字段如下：

```json
{
  "action": "allow|downgrade|block",
  "analysis": "string",
  "reason_codes": ["..."],
  "findings": ["..."],
  "rule_candidates": [],
  "memory_candidates": []
}
```

`action` 会影响当前 turn 的最终决策，但只有在 `model_stage_status == completed` 时才会被合并。

模型阶段的复用知识分两类：

### 9.1 Rule Candidates

`rule_candidates` 用于确定性规则，适合未来 `extra_rule` 在线匹配。

典型字段：

```json
{
  "pattern": "literal substring or regex",
  "pattern_type": "substring|regex|planned_action",
  "risk_type": "prompt_injection|secret_exfiltration|unsafe_tool_use",
  "trigger_condition": "when this rule should fire",
  "suggested_action": "downgrade|block",
  "reason_code": "EXTRA_...",
  "evidence_items": ["evidence"],
  "validation_cases": {
    "positive": ["texts that should match"],
    "negative": ["safe nearby texts that must not match"]
  }
}
```

### 9.2 Memory Candidates

`memory_candidates` 用于自然语言经验，不稳定到足以变成本地确定性规则，但对后续模型阶段有帮助。

典型字段：

```json
{
  "pattern_summary": "lesson learned from this turn",
  "risk_type": "prompt_injection|secret_exfiltration|unsafe_tool_use",
  "trigger_contexts": ["where this tends to appear"],
  "why_not_rule_friendly": "why this is not a stable deterministic rule",
  "evidence_items": ["evidence"],
  "suggested_action": "downgrade|block"
}
```

重要区别：

- `rule_candidates` 经过验证后可以成为 active rules。
- active rules 会被未来 `extra_rule` 在线读取。
- `memory_candidates` 写入 textual memory。
- textual memory 不直接进入在线 `extra_rule`。
- textual memory 更适合作为后续 `model_stage` 或上下文经验使用。

## 10. Model Stage Status

hook 会记录 `model_stage_status`：

### 10.1 skipped

规则阶段 block，模型阶段不应执行。

```text
rule_stage_action == block
```

### 10.2 required_not_provided

规则阶段没有 block，理论上需要模型阶段，但 framework 没有在 payload 中提供 completed `model_stage`。

这通常发生在第一次 hook 调用之后，framework 还没有执行模型阶段。

此时：

- 当前 turn 暂时保留 rule-stage decision。
- `knowledge_writeback_status = awaiting_framework_model_stage`
- hook 期待 framework 完成 `model_stage` 后再次调用。

### 10.3 pending

framework 选择 async model stage，但当前 payload 还没有模型结果。

此时：

- `model_dispatch_mode = async`
- `model_stage_status = pending`
- 当前 turn 保留 rule-stage decision。
- 等异步 subagent 完成后再提交 proposal。

### 10.4 completed

payload 中包含 completed `model_stage`。

此时 hook 会：

- 消费模型阶段 action。
- 记录 analysis、findings、reason codes。
- 从 rule_candidates / memory_candidates 中提取可复用知识。
- 根据 sync/async 模式执行写回或写 proposal。

## 11. Final Action for Current Turn

当前 turn 的最终动作是 `final_action`。

如果没有 completed `model_stage`：

```text
final_action = rule_stage_action
```

如果有 completed `model_stage`：

```text
final_action = merge(rule_stage_action, model_stage_action)
```

仍然使用：

```text
block > downgrade > allow
```

因此：

- 规则阶段 downgrade，模型阶段 allow，最终仍是 downgrade。
- 规则阶段 allow，模型阶段 block，最终是 block。
- 规则阶段 block 时不会进入模型阶段，最终是 block。

`final_action` 是当前 turn 可执行决策。后续 proposal sweep 不能回头修改已经完成的 `final_action`。

## 12. Post-Model Knowledge Update

只有 completed `model_stage` 可以触发知识写回。

写回入口是：

```text
synthesize_knowledge_from_model_stage
```

它会从 `model_stage` 中提取：

- structured rule candidates
- structured memory candidates

如果没有结构化 candidates，但 `model_stage.findings` 或 `analysis` 中确实有可复用观察，runtime 可以生成 fallback textual memory。

不过需要注意：

- runtime 不会从 prose 中可靠生成高质量 executable rule。
- 高质量 rule 必须由 framework model 以 structured `rule_candidates` 提供。
- 高质量 validation cases 也应由 framework model 提供。

## 13. Sync Knowledge Writeback

如果：

```text
model_dispatch_mode == sync
model_stage_status == completed
```

hook 直接执行：

```text
writeback_model_knowledge
```

完整写回流程：

```text
model knowledge
  -> deduplicate rules
  -> deduplicate memories
  -> validate rule candidates
  -> promote validated rules to active rules
  -> persist textual memory
  -> write audit logs
```

### 13.1 Rule Dedup

候选规则会和已有 active rules、candidate rules 比较。

如果相似度较高：

- 合并 source turn ids。
- 合并 evidence items。
- 增加 occurrence count。
- 写入 dedup audit。

如果没有近似项：

- 作为新候选规则进入后续 validation。

### 13.2 Memory Dedup

文本记忆也会和已有 textual memory 做相似度比较。

如果相似：

- 合并 source turn ids。
- 合并 trigger contexts。
- 合并 evidence items。
- 增加 occurrence count。

如果不相似：

- 作为新 memory 写入 textual memory store。

### 13.3 Rule Validation

候选规则必须通过 deterministic validation 才能提升为 active rule。

validation corpus 优先使用 framework model 提供的：

- `validation_cases.positive`
- `validation_cases.negative`

验证原则：

- 必须命中 positive cases。
- 不得命中 negative cases。

如果没有 generated validation cases，runtime 会使用 evidence-based fallback，但这是保守路径。

验证结果写入：

```text
.sentryskills/extra/memory/validation_audit.jsonl
```

通过验证的规则会进入：

```text
.sentryskills/extra/memory/active_extra_rules.json
```

未通过验证的规则不会成为 active rules。

### 13.4 Active Rule Promotion

通过 validation 的 candidate rule 会被 materialize 成 active rule。

active rules 是未来 `extra_rule` 在线匹配的唯一规则来源。

如果 proposal type 是 rule revision，并且目标 rule 存在，则会更新目标 rule；否则作为新 active rule。

## 14. Async Model Stage and Proposals

异步路径只允许在低风险 turn 中使用。

典型流程：

```text
rule_gate allows/downgrades
  -> framework_risk_level = low
  -> model_dispatch_mode = async
  -> current hook records pending
  -> subagent performs model_stage
  -> subagent calls hook with sentryskills_role = subagent
  -> hook writes proposal file
  -> main agent later sweeps proposals
  -> proposal updates affect future turns only
```

subagent 的边界：

- 可以完成 model-heavy safety analysis。
- 可以提供 structured rule candidates。
- 可以提供 memory candidates。
- 可以写 proposal file。
- 不能直接修改 active extra rules。
- 不能直接修改 candidate store。
- 不能执行 proposal sweep。

proposal 文件写入：

```text
.sentryskills/extra/proposals/pending/
```

proposal 文件内容包括：

- proposal id
- source turn id
- source task id
- trace id
- model stage action
- analysis
- findings
- rule proposals
- memory notes

## 15. End-of-Task Proposal Sweep

每个 main-agent task 结束时，main agent 应执行一次 proposal sweep。

proposal sweep 做三件事：

1. 扫描：

```text
.sentryskills/extra/proposals/pending/
```

2. 对每个 proposal 执行同一套知识写回逻辑：

```text
proposal rule_proposals / memory_notes
  -> writeback_model_knowledge
  -> dedup
  -> validation
  -> active rule promotion
  -> memory persistence
```

3. 移动 proposal 文件：

```text
processed proposal -> .sentryskills/extra/proposals/processed/
rejected proposal  -> .sentryskills/extra/proposals/rejected/
```

proposal sweep 的结果记录在：

```text
.sentryskills/extra/memory/proposal_audit.jsonl
```

重要语义：

- proposal sweep 是 main-agent maintenance step。
- proposal sweep 的结果只影响后续 turn。
- proposal sweep 不改写当前已经完成的 `final_action`。

## 16. Runtime Outputs

hook 会在 summary、event log 和 unified log 中暴露关键字段。

核心字段：

```text
sentryskills_trace_id
base_rule_action
extra_rule_action
rule_stage_action
framework_risk_level
model_dispatch_mode
model_stage_status
model_stage_action
model_executor
model_stage_result_available
proposal_sweep_effect
knowledge_writeback_status
final_action
```

这些字段构成完整 decision chain。

### 16.1 Event Log

事件流写入：

```text
.sentryskills/base/self_guard_events.jsonl
```

主要事件类型包括：

- `hook_start`
- `preflight_result`
- `runtime_result`
- `output_guard_result`
- `extra_rule_result`
- `model_stage_result`
- `knowledge_writeback_result`
- `proposal_sweep_result`
- `final_decision`
- `hook_end`
- `hook_error`

### 16.2 Unified Logs

默认 log layout 是 unified，每个 query 一个 JSON：

```text
.sentryskills/base/logs/
```

unified log 包括：

- input summary
- preflight result
- runtime monitor result
- output guard result
- extra layer result
- model stage state
- knowledge writeback state
- proposal sweep state
- final decision
- retention snapshot

### 16.3 Session State

session sensitivity 和 conversation history 写入：

```text
.sentryskills/base/.self_guard_state/<session_id>.json
```

它让后续 turn 可以继承 sensitivity state 和有限历史。

## 17. Storage Layout

### 17.1 Base State

```text
.sentryskills/base/
  self_guard_events.jsonl
  index.jsonl
  logs/
  turns/
  .self_guard_state/
```

用途：

- 当前 turn 审计。
- 事件流。
- 统一日志。
- session sensitivity state。
- turn index。

### 17.2 Extra State

```text
.sentryskills/extra/
  memory/
    active_extra_rules.json
    candidate_extra_rules.jsonl
    textual_memory.jsonl
    validation_audit.jsonl
    dedup_audit.jsonl
    proposal_audit.jsonl
  proposals/
    pending/
    processed/
    rejected/
  tmp/
    validation/
```

用途：

- `active_extra_rules.json`：未来 `extra_rule` 在线匹配使用。
- `candidate_extra_rules.jsonl`：尚未提升的候选规则。
- `textual_memory.jsonl`：自然语言经验。
- `validation_audit.jsonl`：规则验证审计。
- `dedup_audit.jsonl`：去重审计。
- `proposal_audit.jsonl`：异步 proposal sweep 审计。
- `proposals/pending`：等待 main agent sweep 的 proposal。
- `proposals/processed`：已处理 proposal。
- `proposals/rejected`：处理失败或非法 proposal。

## 18. Framework Integration Modes

### 18.1 Claude Code

Claude Code 更适合 hook-enforced 集成。

推荐模型：

- hook 强制 rule-first frontend。
- rule stage block 时立即停止。
- framework 在 rule gate 后分配 risk。
- high risk 使用 sync model stage。
- low risk 可使用 async/subagent model stage。
- main agent 任务结束时 sweep proposal。

### 18.2 Codex / OpenClaw

Codex / OpenClaw 主要依赖：

- `SKILL.md`
- `AGENTS.md`
- framework discipline

推荐策略：

- 每个任务先运行 `/using-sentryskills`。
- 非 blocked turn 使用两次 hook 模式。
- 只有 low-risk turn 才允许 subagent 参与 `model_stage`。
- high-risk 或 subagent 不可靠时使用 sync model stage。
- task 结束时执行一次 proposal sweep。

## 19. End-to-End Turn Examples

### 19.1 Rule-Stage Block

```text
user request
  -> first hook
  -> preflight detects explicit secret disclosure
  -> base_rule_action = block
  -> extra_rule skipped or harmless
  -> rule_stage_action = block
  -> model_stage_status = skipped
  -> knowledge_writeback_status = skipped
  -> final_action = block
```

结果：

- 当前 turn 停止。
- 不调用模型阶段。
- 不写新规则。
- 不写 textual memory。

### 19.2 Non-Blocked Sync Model Stage

```text
user request
  -> first hook
  -> base_rule_action = allow or downgrade
  -> extra_rule_action = allow or downgrade
  -> rule_stage_action != block
  -> framework_risk_level = high
  -> model_dispatch_mode = sync
  -> framework completes model_stage
  -> second hook consumes model_stage
  -> writeback_model_knowledge
  -> proposal sweep
  -> final_action = merge(rule_stage_action, model_stage_action)
```

结果：

- 当前 turn 由 rule stage 和 model stage 共同决定。
- 模型阶段生成的 validated rules 可作用于后续 turn。
- textual memory 可用于后续模型阶段上下文。

### 19.3 Low-Risk Async Model Stage

```text
user request
  -> first hook
  -> rule_stage_action != block
  -> framework_risk_level = low
  -> model_dispatch_mode = async
  -> current turn records pending or keeps rule-stage decision
  -> subagent completes model_stage
  -> subagent hook writes proposal file
  -> main agent end-of-task proposal sweep
  -> validated rules promoted
  -> future turns can use new active rules
```

结果：

- subagent 不直接改 active rules。
- proposal sweep 不修改当前 turn 结果。
- 新规则只从后续 turn 开始生效。

## 20. Common Misinterpretations

### 20.1 Textual Memory Does Not Directly Feed Extra Rule

`textual_memory` 是自然语言经验，不是在线匹配规则。

真正会被 `extra_rule` 在线读取的是：

```text
active_extra_rules.json
```

### 20.2 Proposal Sweep Is Not a Knowledge Type

`Proposal Sweep` 是处理异步 proposal 的过程，不是和 `Rule Candidates`、`Textual Memory` 同级的一类知识。

更准确的关系是：

```text
Async Proposal -> Proposal Sweep -> Knowledge Writer -> Knowledge Store
```

### 20.3 Rule Hits Do Not Automatically Create New Knowledge

`base_rule` 或 `extra_rule` 命中规则，只影响当前 turn decision。

它们不会自动产生新 active rules 或 textual memory。

新知识只能来自 completed `model_stage`。

### 20.4 Async Results Do Not Rewrite Current Turn

异步模型结果通过 proposal 文件进入系统。

main agent sweep 后，即使提升了新 active rule，也只影响后续 turn。

当前已经完成的 `final_action` 不会被 retroactively changed。

### 20.5 Model Stage Is Not Allowed Before Rule Gate

模型阶段是 conditional backend，不是 rule frontend 的替代品。

必须先完成：

```text
base_rule -> extra_rule -> rule_gate
```

然后才能决定是否进入：

```text
risk assessment -> model_stage
```

## 21. Minimal Correct Mental Model

可以把 SentrySkills 理解为以下闭环：

```text
Current turn:
  task/context
    -> base rules
    -> active extra rules
    -> rule gate
    -> optional model stage
    -> final action
    -> logs/audit

Learning path:
  completed model stage
    -> rule candidates / memory candidates
    -> dedup
    -> validation
    -> active rules + textual memory
    -> reused in later turns
```

其中：

- active rules 反馈给后续 `extra_rule`。
- textual memory 反馈给后续 `model_stage/context`。
- proposal sweep 是异步结果进入 learning path 的入口。
- 所有反馈都只影响后续 turn。
