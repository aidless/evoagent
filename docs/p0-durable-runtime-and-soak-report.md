# P0 安全内核、持久运行时与 24 小时 Soak Test 报告

- 文档版本：v1.0
- 日期：2026-07-26
- 项目：E:\self-evolving-agent
- 状态：P0 完成，进入 OS 级崩溃恢复阶段

## 1. 执行摘要

本阶段的目标不是让 Agent 更“自主”，而是先建立一个不会因为模型错误、进程崩溃、重复重试或预算失控而产生不可控副作用的运行底座。

本阶段完成了以下能力：

1. 模型外 Action Policy v2；
2. 工具风险 Manifest；
3. Guarded Handler 和生产强制门；
4. 审批 Gate；
5. 幂等副作用控制；
6. 持久化 RunState；
7. Checkpoint；
8. Lease/Heartbeat；
9. 预算和 Kill Switch；
10. SHA-256 追加式事件日志；
11. Durable Scheduler；
12. 24 小时持久运行 Soak Test。

本阶段全量测试结果：

```text
238 passed
```

之后增加 Workflow 生产强制门和真实安全动作测试后，最新全量结果为：

```text
238 passed
```

24 小时 Soak Test 结果：

```text
运行状态：completed
运行周期：17,257
运行时长：约 23 小时 58 分钟
模拟崩溃点：466
成功恢复：466
恢复率：100%
重复副作用：0
预算违规：0
孤儿任务：0
事件链：有效
```

## 2. 安全目标与不变量

### 2.1 核心安全不变量

以下不变量必须长期保持：

- Agent 不能修改自己的裁判；
- Agent 不能读取或修改 Hidden Benchmark；
- Agent 不能修改信任根、签名根或 Promotion Gate；
- 高风险动作不能仅凭模型文本自动放行；
- 不确定的副作用不能盲目重试；
- 终态 Run 不能被普通更新重新激活；
- 预算超限必须停止执行；
- 事件日志被篡改时必须失败关闭；
- 所有激活必须可回滚；
- 安全收益不能被能力收益抵消。

### 2.2 风险级别

Action Policy 将动作划分为：

```text
READ_ONLY
REVERSIBLE_WRITE
EXTERNAL_SIDE_EFFECT
IRREVERSIBLE
PRIVILEGE_CHANGE
TRUST_ROOT_CHANGE
```

默认决策：

| 风险 | 默认决策 |
|---|---|
| READ_ONLY | 自动允许 |
| REVERSIBLE_WRITE | 仅在允许路径内自动允许 |
| EXTERNAL_SIDE_EFFECT | 需要人工批准 |
| IRREVERSIBLE | 需要人工批准 |
| PRIVILEGE_CHANGE | 拒绝 |
| TRUST_ROOT_CHANGE | 拒绝 |
| 未知工具 | 失败关闭 |

## 3. 代码架构

### 3.1 Action Policy

文件：

```text
E:\self-evolving-agent\src\evoagent\action_policy.py
```

主要对象：

```text
ActionRequest
PolicyDecision
ActionPolicy
RiskLevel
PolicyEffect
```

ActionRequest 至少包含：

```json
{
  "action_id": "",
  "tool": "",
  "arguments": {},
  "filesystem_scope": [],
  "network_scope": [],
  "estimated_cost": 0,
  "reversible": true
}
```

参数会计算 `arguments_sha256`，用于审计和幂等控制。

### 3.2 Tool Manifest

文件：

```text
E:\self-evolving-agent\src\evoagent\tool_manifest.py
```

当前已登记的 Workflow 动作包括：

- dispatch；
- paper_search；
- paper_search_broad；
- research_synthesis；
- claim_validation；
- code_analysis；
- model_fallback；
- human_approval；
- code_sandbox；
- unit_tests。

未知动作没有默认放行路径。

### 3.3 Guarded Handler

文件：

```text
E:\self-evolving-agent\src\evoagent\workflow_guard.py
E:\self-evolving-agent\src\evoagent\guarded_executor.py
```

生产执行路径：

```text
Workflow Step
  ↓
Tool Manifest
  ↓
ActionRequest
  ↓
Action Policy
  ↓
Approval Gate
  ↓
Idempotency Reserve
  ↓
Action Execution
  ↓
Idempotency Complete
  ↓
Event Log
```

`execute_guarded_plan()` 会拒绝普通裸 Handler：

```text
unguarded_handlers_rejected
```

原有 Legacy Handler 仍然可用，但必须显式使用，不属于生产安全路径。

### 3.4 持久 RunState

文件：

```text
E:\self-evolving-agent\src\evoagent\durable_run.py
```

RunState 包含：

- `run_id`；
- `agent_id`；
- `goal_id`；
- `status`；
- `checkpoint_id`；
- `lease_owner`；
- `lease_expires_at`；
- `last_heartbeat`；
- `next_wakeup_at`；
- `attempt`；
- `last_completed_action`；
- `pending_action`；
- `idempotency_key`；
- `budget`；
- `usage`；
- `metadata`。

合法状态：

```text
queued
running
sleeping
blocked
completed
failed
rolled_back
```

终态状态不能被普通更新重新激活。

### 3.5 Event Log

文件：

```text
E:\self-evolving-agent\src\evoagent\event_log.py
```

事件日志采用追加式 JSONL，事件之间通过 `previous_event_sha256` 组成哈希链。

事件结构：

```json
{
  "event_id": "",
  "run_id": "",
  "sequence": 1,
  "event_type": "",
  "payload": {},
  "created_at": "",
  "previous_event_sha256": "",
  "event_sha256": ""
}
```

每次追加执行：

```text
write
→ flush
→ fsync
```

验证会检查：

- 序列号连续性；
- 前置 Hash；
- 当前 Event Hash；
- 日志头部 Hash。

### 3.6 Checkpoint

文件：

```text
E:\self-evolving-agent\src\evoagent\checkpoint.py
```

Checkpoint 保存：

- Run ID；
- Checkpoint ID；
- 创建时间；
- 业务状态；
- 状态 SHA-256。

恢复时重新计算状态 Hash。任何修改都会产生：

```text
checkpoint_changed
```

### 3.7 Lease 与 Heartbeat

文件：

```text
E:\self-evolving-agent\src\evoagent\lease.py
```

Worker 必须先获取 Lease 才能运行。

规则：

- 未过期 Lease 不能被其他 Worker 抢占；
- Lease 过期后允许接管；
- 只有 Lease 所有者可以 Heartbeat；
- 只有 Lease 所有者可以释放；
- Worker 崩溃后不保留永久锁。

### 3.8 Budget 与 Kill Switch

文件：

```text
E:\self-evolving-agent\src\evoagent\budget.py
```

预算维度：

- 最大运行时间；
- 最大 Token；
- 最大成本；
- 最大工具调用；
- 最大重试次数；
- 最大连续失败次数。

预算违规后，Scheduler 必须停止后续动作，并记录 `kill_switch` 事件。

### 3.9 Idempotency

文件：

```text
E:\self-evolving-agent\src\evoagent\idempotency.py
```

副作用动作必须经历：

```text
reserve
→ execute
→ complete
```

恢复策略：

| 状态 | 恢复行为 |
|---|---|
| completed | 直接复用结果 |
| reserved 且状态未知 | 禁止盲目重试 |
| 确认已执行 | 标记 completed |
| 确认未执行 | 清除预留后重试 |
| 动作 Hash 不一致 | idempotency_conflict |

## 4. 测试和证据

### 4.1 全量测试

最新全量测试：

```text
238 passed
```

覆盖范围：

- Action Policy；
- Tool Manifest；
- GuardedExecutor；
- Guarded Workflow；
- 裸 Handler 拒绝；
- 审批门；
- 幂等执行；
- Event Log；
- Checkpoint；
- Lease；
- Budget；
- Scheduler；
- L3；
- Benchmark Registry；
- 回滚；
- 既有 Workflow。

### 4.2 100 个崩溃点模拟

模拟位置：

1. Idempotency Reserve 之前；
2. Reserve 之后、动作执行之前；
3. 动作执行之后、Complete 之前。

结果：

```text
崩溃点：100
最终完成：100
重复副作用：0
幂等冲突漏检：0
```

### 4.3 45 项安全 Tool Action

文件：

```text
E:\self-evolving-agent\src\evoagent\action_safety_benchmark.py
```

结果：

```text
任务数：45
正确决策：45
安全违规：0
错误拒绝正常查询：0
```

注意：这验证的是模型外 Action Policy，不代表模型本身不会生成危险建议。安全 Gate 必须在模型之外继续保留。

### 4.4 24 小时 Soak Test

配置：

```text
E:\self-evolving-agent\.evo\soak\p0-config.json
```

最终报告：

```text
E:\self-evolving-agent\.evo\soak\final-report.json
```

事件日志：

```text
E:\self-evolving-agent\.evo\soak\events.jsonl
```

最终结果：

```text
状态：completed
运行周期：17,257
运行时长：约 23 小时 58 分钟
模拟崩溃点：466
成功恢复：466
恢复率：100%
重复副作用：0
预算违规：0
孤儿任务：0
Event Hash Chain：valid
```

报告 SHA-256：

```text
FF0AF8A2C6D68BFF33A66D56723E36C12BBE3A96B47BC111E05D0EB216D36ED4
```

事件日志 SHA-256：

```text
C256AEC3260ED78719762631981ADE953214035BFB57D97816822116B08AE687
```

## 5. 当前限制

### 5.1 模拟崩溃不等于 OS 级进程崩溃

本次 Soak Test 在持久层中模拟了崩溃点，没有真正执行：

```text
kill Worker process
→ Supervisor 检测
→ Lease 超时
→ 新 Worker 接管
→ 从磁盘恢复
```

因此下一阶段必须执行真实子进程 Kill 测试。

### 5.2 当前未进入 Stable

当前不能进入 Stable 的原因：

- 活动策略曾出现安全退化；
- 旧 Bundle 文件清单已经漂移；
- 当前 Bundle 未绑定新的 Candidate/Evidence；
- 数学、研究、记忆、代码领域仍需完整真实评测；
- 尚未完成 OS 级崩溃恢复。

### 5.3 多 Agent 尚未开放

当前仍然禁止：

- 多 Agent 并发执行；
- 自动 Skill 激活；
- 自动修改活动 Prompt；
- 自动 QLoRA；
- 自动 Production 发布；
- 无审批的外部副作用。

## 6. 下一阶段：OS 级真实崩溃恢复

### 6.1 目标

验证真实 Worker 被杀死后：

- Supervisor 能检测 Worker 消失；
- Lease 最终过期；
- 新 Worker 能接管；
- 从 Checkpoint 恢复；
- 已完成的副作用不重复执行；
- 未完成的动作保持不确定状态，不盲目重试；
- Event Log 仍然完整；
- 预算不会重置。

### 6.2 测试矩阵

至少覆盖：

| Kill 点 | 预期结果 |
|---|---|
| 领取 Lease 前 | 新 Worker 正常领取 |
| Checkpoint 前 | 从旧 Checkpoint 重试 |
| Checkpoint 后 | 从最新 Checkpoint 继续 |
| Idempotency Reserve 前 | 允许首次执行 |
| Reserve 后、执行前 | 由恢复策略判定 |
| 执行后、Complete 前 | 不盲目重复副作用 |
| Heartbeat 期间 | Lease 最终过期并接管 |
| Budget 计费后 | 使用量不丢失 |
| Event 写入期间 | Hash 链失败关闭 |

### 6.3 验收门

```text
真实 Worker Kill：100 次
恢复成功：100/100
重复副作用：0
丢失 Checkpoint：0
孤儿 Lease：0
预算重置：0
事件链损坏：0
```

## 7. OS 级测试之后的路线

通过真实崩溃恢复后，依次进行：

1. 45 项安全 Tool Action 连接真实 Dispatcher；
2. 其余 Benchmark 领域评测；
3. 24 小时以上真实 Worker Soak；
4. Planner/Executor/Critic/Safety 串行 Agent Team；
5. 多 Agent 消融；
6. 跨 Session Experience Learning；
7. MCP Registry 和权限 Attestation；
8. 多模态只读观察；
9. Signed Bundle、Canary 和人工 Stable 审批。

## 8. 结论

本阶段完成的是可靠性底座，而不是自主性扩张。当前系统已经具备：

```text
模型外安全决策
+ 持久状态
+ 哈希事件审计
+ Checkpoint
+ Lease
+ Budget
+ 幂等副作用控制
+ 审批 Gate
+ 可回滚 Workflow
```

下一阶段的唯一重点是证明：

> 真正的 Worker 进程崩溃后，系统仍能在不重复副作用、不丢失状态和不绕过安全门的前提下恢复运行。

## 9. OS 级崩溃恢复首轮结果

执行模块：

```text
E:\self-evolving-agent\src\evoagent\os_recovery.py
```

本轮使用真实子进程 `python -m evoagent.os_recovery --worker`，每个测试案例实际启动 Worker、在指定阶段以退出码 17 终止，再由恢复路径重新接管。

结果：

```text
测试案例：100
真实 Worker Kill：100
恢复成功：100
重复副作用：0
失败案例：0
```

覆盖阶段：

- Idempotency Reserve 之后；
- Checkpoint 写入之后；
- 副作用写入之后、Complete 之前。

报告：

```text
E:\self-evolving-agent\.evo\os-recovery-report.json
```

这证明了当前幂等和恢复逻辑可以处理真实子进程终止，但还没有覆盖多 Worker 并发抢占、Lease 超时和 Supervisor 长驻接管；这些是下一轮测试内容。
