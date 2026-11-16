# PREREG — evoagent 预注册与评测规格

> 本文件是 evoagent 的**预注册规格**（registered-report 风格）：区分本仓库**能复算**的闭环行为，和只写在旧笔记里、`make check` **不会重跑**的数字。
> 能复算的证据是 `make check`（`tests/` + `evidence/toy-trace.json`）。`docs/p0-durable-runtime-and-soak-report.md` 与 registry-v2 的 360 任务标签不是这次复算的结果。

---

## 0. 一句话假设（先读这行）

> evoagent 的可复算部分是一个玩具配置控制器：4 个字符串用例上，安全门、最小增益比较、原子晋升和回滚按 `evidence/toy-trace.json` 发生。这不是智能体能力提升。L3 四阶段门（`stage_gates.py`）是另一条路径，缺真实执行证据会拒绝；默认的 `evolve()` 不走那条路径。

---

## 1. 主假设 H1（受评测约束的闭环）

- **假设**：在固定基准上，候选通过安全门且 `candidate_score >= baseline_score + min_gain` 时，统计门关闭才会原子晋升；统计门开启时还要过 `evaluate_promotion`。否则保留基线。每次晋升写入回滚快照，可一条命令回滚。
- **可证伪方向**：若候选低于门槛仍被晋升，或晋升后无回滚快照，则 H1 不成立。
- **评测方案**：`make check`（`tests/` + `evidence/toy-trace.json`）。示例种子通过 1/4。统计门关闭时，手写 mutation 会把同时打开两个 flag 的候选晋升到 4/4；`evo.json` 里统计门默认开启，同一次分数变化被拒绝（`mcnemar_not_significant`）。
- **成功标准**：默认配置下这次 1/4→4/4 不晋升；统计门关闭时晋升且回滚快照存在，`rollback` 能回到种子。以 `evidence/toy-trace.json` 为准，而不是以「总会晋升到 4/4」为准。

## 2. 假设 H2（Benchmark Registry v2 结构）

- **假设**：基准注册表为 4 阶段 × 8 领域 × 45 = **360 任务**；其中隐藏集 240（80+60+100）；完整任务与答案存放在候选工作区之外（防污染）。
- **可证伪方向**：若 `summary.json` 的 `tasks` 不为 360，或 `by_domain` 不满足 8×45，或 `hidden` 不为 240，则 H2 不成立。
- **复算**：`from evoagent.p0_registry import STAGE_COUNTS, PER_DOMAIN` 得到代码常量合计 360、`PER_DOMAIN=45`。`benchmarks/registry-v2/summary.json` 的字段也写着 `tasks=360`、`hidden=240`，但同目录的 `tasks.json` 是脱敏占位，不能逐条点数。
- **成功标准**：结构与常量一致，`sum(STAGE_COUNTS.values()) == 360`。

## 3. 假设 H3（L3 晋升严格门控 / fail-closed）

- **假设**：L3 晋升要求全部 4 阶段 `real_execution=true` 且 Candidate/Bundle/Evidence 全部 `passed=True`，绑定校验通过，成本/延迟/安全违规不超预算；任一不满足即拒绝。
- **可证伪方向**：若缺失阶段/样本量/真实执行记录仍能晋升，则 fail-closed 失效。
- **评测方案**：`evaluate_four_stage` 的 `reasons` 累积 + `l3_provisional` 的 `raise RuntimeError("four_stage_gate_rejected")`；`require_real_execution=True` 默认（见 `stage_gates.py`、`l3_provisional.py`）。
- **成功标准**：无任何 `reasons` 且 `auto_promote=True` 才晋升；`unverified_execution` 是显式阻断原因。

## 4. 假设 H4（持久运行时崩溃恢复）

- **假设**：持久运行在模拟崩溃点与真实进程 kill 下**不产生重复副作用、预算违规或孤儿任务**。
- **可证伪方向**：若任一崩溃点出现重复副作用或恢复失败，则 H4 不成立。
- **复算**：`python3 -m pytest tests/test_durable_runtime.py -q` 只覆盖仓库里的测试。`docs/p0-durable-runtime-and-soak-report.md`（2026-07-26 v1.0）记载 24h 运行 17,257 周期、466/466 崩溃恢复等数字，**不是** `make check` 的产物，不能当作本仓库可复算结果。
- **成功标准**：崩溃恢复 100%，重复副作用 0。

---

## 5. 明确边界（不证明什么）

| 维度 | 不证明 | 原因 |
|---|---|---|
| `self_verify_v2_l3` 135/135 | 不可复算 | 只存在于原 README 残留文本，仓库无对应报告/数据/commit |
| Qwen2-7B 40.0% vs 33.3% | 不可复算 | 同上，**不得作为结论引用** |
| 外部效度 / 真实用户 / 生产部署 | 未做 | 模拟器与合成任务不代表真实环境 |
| L3 全流程独立重跑 | 无法独立重跑 | 完整任务与答案不在仓库内（registry-v2 的 tasks/answer 文件是脱敏占位）。旧笔记中的工作站路径不是运行说明 |
| 本路径子进程测试 | 环境伪影非 bug | 工作区路径含字面 `:`，PYTHONPATH 冒号分割致 13 子进程失败 |

---

## 6. 结论纪律

- 闭环数字以 `make check` 和 `evidence/toy-trace.json` 为准。旧 README 里的模型分数不在该轨迹中。
- 任何只存在于残留文本、不可复算的数字（135/135、40.0%/33.3%）**不作为结论引用**。
- 本 PREREG 是规格声明，不新增实验、不改变已冻结基线（`tests/`、`benchmarks/registry-v2/summary.json` 数字不变）。
