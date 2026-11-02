# PREREG — evoagent 预注册与评测规格

> 本文件是 evoagent 的**预注册规格**（registered-report 风格）：声明本仓库**实际执行、可从落盘证据复算**的自进化闭环假设、评测方案、成功标准与明确边界。
> 所有数字来自仓库内文件（`p0_registry.py`、`benchmarks/registry-v2/summary.json`、`docs/p0-durable-runtime-and-soak-report.md`、`tests/`），**不是虚构实验**。

---

## 0. 一句话假设（先读这行）

> evoagent 是一个**受评测约束的自进化控制器**：候选策略只有在固定基准集上优于当前版本、通过安全门且达到最小增益时才会被晋升，每次晋升保留回滚快照；晋升是**严格门控（fail-closed）**——任何一项真实执行/工件/安全证据缺失即整体拒绝。

---

## 1. 主假设 H1（受评测约束的闭环）

- **假设**：在固定基准上，候选 `candidate_score >= baseline_score + min_gain` 且通过安全门时原子晋升，否则保留基线；每次晋升写入回滚快照，可一条命令回滚。
- **可证伪方向**：若候选低于门槛仍被晋升，或晋升后无回滚快照，则 H1 不成立。
- **评测方案**：`src/evoagent/` 的 gate/compare/promote/rollback 路径 + `tests/`；示例种子只能通过 1/4 用例，闭环评测三候选后晋升一个到 4/4。
- **成功标准**：晋升仅发生在 `auto_promote=True`；回滚快照存在。

## 2. 假设 H2（Benchmark Registry v2 结构）

- **假设**：基准注册表为 4 阶段 × 8 领域 × 45 = **360 任务**；其中隐藏集 240（80+60+100）；完整任务与答案存放在候选工作区之外（防污染）。
- **可证伪方向**：若 `summary.json` 的 `tasks` 不为 360，或 `by_domain` 不满足 8×45，或 `hidden` 不为 240，则 H2 不成立。
- **复算**：`from evoagent.p0_registry import STAGE_COUNTS, PER_DOMAIN` → `STAGE_COUNTS = {development:120, hidden_confirmation:80, trigger_safety:60, shadow:100}`（合计 360）、`PER_DOMAIN=45`；`benchmarks/registry-v2/summary.json` 实测 `tasks=360`、`hidden=240`。
- **成功标准**：结构与常量一致，`sum(STAGE_COUNTS.values()) == 360`。

## 3. 假设 H3（L3 晋升严格门控 / fail-closed）

- **假设**：L3 晋升要求全部 4 阶段 `real_execution=true` 且 Candidate/Bundle/Evidence 全部 `passed=True`，绑定校验通过，成本/延迟/安全违规不超预算；任一不满足即拒绝。
- **可证伪方向**：若缺失阶段/样本量/真实执行记录仍能晋升，则 fail-closed 失效。
- **评测方案**：`evaluate_four_stage` 的 `reasons` 累积 + `l3_provisional` 的 `raise RuntimeError("four_stage_gate_rejected")`；`require_real_execution=True` 默认（见 `stage_gates.py`、`l3_provisional.py`）。
- **成功标准**：无任何 `reasons` 且 `auto_promote=True` 才晋升；`unverified_execution` 是显式阻断原因。

## 4. 假设 H4（持久运行时崩溃恢复）

- **假设**：持久运行在模拟崩溃点与真实进程 kill 下**不产生重复副作用、预算违规或孤儿任务**。
- **可证伪方向**：若任一崩溃点出现重复副作用或恢复失败，则 H4 不成立。
- **复算**：`python3 -m pytest tests/test_durable_runtime.py -q`；`docs/p0-durable-runtime-and-soak-report.md`（2026-07-26 v1.0）实测 24h 运行 17,257 周期、466/466 崩溃恢复、重复副作用 0、预算违规 0、孤儿 0；早期 100 崩溃点 100/100、真实 Worker Kill 100 次 100/100。
- **成功标准**：崩溃恢复 100%，重复副作用 0。

---

## 5. 明确边界（不证明什么）

| 维度 | 不证明 | 原因 |
|---|---|---|
| `self_verify_v2_l3` 135/135 | 不可复算 | 只存在于原 README 残留文本，仓库无对应报告/数据/commit |
| Qwen2-7B 40.0% vs 33.3% | 不可复算 | 同上，**不得作为结论引用** |
| 外部效度 / 真实用户 / 生产部署 | 未做 | 模拟器与合成任务不代表真实环境 |
| L3 全流程独立重跑 | 无法独立重跑 | 完整任务与答案在仓库外 `E:\self-evolving-agent-private` |
| 本路径子进程测试 | 环境伪影非 bug | 工作区路径含字面 `:`，PYTHONPATH 冒号分割致 13 子进程失败 |

---

## 6. 结论纪律

- 所有数字从本仓重算（见 README「复算」节）。
- 任何只存在于残留文本、不可复算的数字（135/135、40.0%/33.3%）**不作为结论引用**。
- 本 PREREG 是规格声明，不新增实验、不改变已冻结基线（`tests/`、`benchmarks/registry-v2/summary.json` 数字不变）。
