# EvoAgent：受评测约束的自进化闭环

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  [![CI](https://github.com/aidless/evoagent/actions/workflows/audit.yml/badge.svg)](https://github.com/aidless/evoagent/actions/workflows/audit.yml/badge.svg)

这不是“让模型随意改写自己”，而是一个可审计的改进控制器。候选策略只有在固定基准集上优于当前版本、通过安全门且达到最小增益时，才会成为活动版本；每次晋升都保留回滚快照。

## 闭环

1. **Evaluate**：在隔离临时目录中评测活动策略。
2. **Diagnose / Propose**：基于失败用例产生候选策略（内置声明式 mutation，亦可接外部 LLM proposer）。
3. **Safety gate**：限制候选大小并拦截禁止内容。
4. **Compare**：所有候选使用同一基准和超时设置。
5. **Promote**：仅当 `candidate_score >= baseline_score + min_gain` 时原子晋升。
6. **Rollback**：保存上一活动版本，支持一条命令回滚。

## 快速运行（PowerShell）

```powershell
cd E:\self-evolving-agent
$env:PYTHONPATH = "E:\self-evolving-agent\src"
python -m evoagent.cli init
python -m evoagent.cli evolve
python -m evoagent.cli status
python -m unittest discover -s tests -v
```

示例种子只能通过 1/4 用例；闭环会评测三个候选，并将同时支持大小写归一化和空白清理的候选晋升到 4/4。运行记录位于 `.evo/runs/`，历史版本位于 `.evo/history/`。

## 接入真实 Agent

- 将 `seed.json` 换成当前提示词、工具策略或参数配置。
- 将 `examples/benchmark.json` 换成冻结的代表性任务集；保留一份不参与提案的隐藏测试集更可靠。
- 将 `evaluator_command` 指向真实评测器。每个用例通过环境变量获得 `EVO_CANDIDATE`、`EVO_INPUT`、`EVO_EXPECTED`、`EVO_CASE_ID`，并向 stdout 返回 `{"passed": true}`。
- 可设置 `proposer_command` 接入任意本地或远程模型。它从 `EVO_INCUMBENT` 和 `EVO_FAILURES` 读取上下文，向 stdout 输出 JSON 候选数组。

## 安全原则

当前版本默认只进化数据配置，不允许框架自动改写自身执行代码；候选在临时目录评测、每项有超时、晋升有门槛且可回滚。生产使用时还应加入隐藏回归集、成本/延迟上限、人工审批、网络与文件权限隔离以及签名发布。


## P0 评测：Benchmark Registry v2（2026-07-25）

> **编码说明**：本节原文在历史提交中损坏（中文全部丢失为 `?`），已按**源码事实**与`docs/`报告重建。数字一律来自仓库内文件，见下方「复算」。

**Benchmark Registry v2（L3 评测）**：一个 4 阶段、按领域分层的固定基准集。`src/evoagent/p0_registry.py` 定义 `STAGE_COUNTS = {development:120, hidden_confirmation:80, trigger_safety:60, shadow:100}`（合计 **360**）、`PER_DOMAIN=45`；`benchmarks/registry-v2/summary.json` 实测 `tasks=360`、`by_domain 8×45=360`、`hidden=240`（80+60+100）、`storage_policy = "full tasks and answers are stored outside the candidate workspace"`。

- **4 阶段**：Development（120）→ Hidden Confirmation（80）→ Trigger Safety（60）→ Shadow（100）；Hidden+Trigger+Shadow = 240 个不参与提案的隐藏任务。
- **分层**：8 个领域 × 45 = 360。
- **指标**：`src/evoagent/calibration.py::selective_metrics()` 产出 Coverage / Selective Accuracy / Appropriate Abstention Rate / Unnecessary Abstention Rate。
- **L3 判定**：`l3_provisional.py::run_l3_provisional()` 跑完 4 阶段，按 `item.decision` 记录 `real_execution`，校验 Bundle 绑定；只有 `real_execution=true` 且 Candidate/Bundle/Evidence 全部 `passed=True` 才通过。
- **版本晋升**：`version_registry.py` 定义 `LEVELS=(experimental, provisional, stable, production)`；`experimental→provisional` 需要 `development_passed + rollback_available`；`provisional→stable` 需要 `statistical_passed + hidden_passed + safety_passed + rollback_available + bundle_signature_valid`。
- **数据存放**：完整任务与答案存放在工作区之外（`E:\self-evolving-agent-private`），候选工作区只含清单（防污染）。

**已知评测记录（来自原 README 保留的警告框，无法在本仓库重算）**：`self_verify_v2_l3` 135/135 passed（0 failed）；Qwen2-7B 45 任务上 Coverage 10 任务口径 40.0% vs 33.3%。这两个数字**只存在于原 README 残留，不在仓库任何文件/报告中**，无法从当前提交重算——保留为历史记录并明确标注不可复算，**不作为结论**。

**P0 命令**：

```powershell
$env:PYTHONPATH = "E:\self-evolving-agent\src"
python -m evoagent.p0_registry --root E:\self-evolving-agent
python -m evoagent.p0_evaluation --root E:\self-evolving-agent
python -m evoagent.p0_model_evaluation --root E:\self-evolving-agent --endpoint http://127.0.0.1:1234/v1
python -m evoagent.p0_rollback --root E:\self-evolving-agent            # 预演
python -m evoagent.p0_rollback --root E:\self-evolving-agent --apply    # 实际回滚
Get-Content E:\self-evolving-agent\.evo\benchmark-registry-v2\current-status.json
```

## P0 运行时：持久运行与崩溃恢复（2026-07-25）

**持久运行时**：模型外 Action Policy v2、持久化 RunState、SHA-256 追加式事件日志、Checkpoint、Lease/Heartbeat、预算与 Kill Switch、幂等副作用控制、Guarded Handler + 生产强制门、审批 Gate、Durable Scheduler。对应模块：`src/evoagent/action_policy.py`、`durable_run.py`、`event_log.py`、`checkpoint.py`、`lease.py`、`budget.py`、`idempotency.py`、`guarded_executor.py`、`scheduler.py`（全部存在）。

**Soak Test 结果（`docs/p0-durable-runtime-and-soak-report.md`，2026-07-26 v1.0）**：24 小时持久运行 `completed`；运行周期 **17,257**；约 23 小时 58 分钟；模拟崩溃点 **466**，成功恢复 **466**，恢复率 **100%**；重复副作用 **0**；预算违规 **0**；孤儿任务 **0**。早期阶段另有 100 个崩溃点模拟（100/100 完成）与真实 Worker Kill 100 次（100/100 恢复）。同报告记录当时全量测试 **238 passed**（README 残留写作 231，以报告 238 为准；当前提交实测 237 passed + 10 skipped，差异为测试演进）。

## 证明什么 / 不证明什么

**证明什么（本仓库可复算）**：
- 闭环控制器在固定基准上通过安全门与最小增益才晋升，每次晋升保留回滚快照（`src/evoagent/` 的 gate/compare/promote/rollback 路径 + `tests/`）。
- Benchmark Registry v2 的 4 阶段/8 领域/360 任务结构（`p0_registry.py` 常量 + `benchmarks/registry-v2/summary.json`，可重算）。
- 持久运行时的崩溃恢复不变量：100 个模拟崩溃点 0 重复副作用；466/466 恢复（`test_durable_runtime.py` + `docs/` 报告）。

**不证明什么（诚实性边界）**：
- `self_verify_v2_l3` 135/135 与 Qwen2-7B 40.0% vs 33.3% **只存在于原 README 残留文本**，当前仓库无对应报告/数据/commit——不可复算，**不得作为结论引用**。
- 未做外部效度、真实用户研究或生产部署验证；模拟器与合成任务不代表真实环境。
- 数据目录 `E:\self-evolving-agent-private` 在仓库外；本仓库不含完整任务与答案，无法独立重跑 L3 全流程。
- 当前工作区路径含字面 `:`（`F:\deepseek`），从该路径直接跑会因 `PYTHONPATH` 冒号分割导致 13 个子进程测试失败——**环境伪影，非仓库 bug**；从冒号无关路径跑全部通过（见下）。

## 复算

```bash
# 1) 全量测试（在冒号无关路径跑，否则子进程测试受 PYTHONPATH 冒号分割影响）
#    实测基线：237 passed + 10 skipped（2026-11-01）
cp -r <repo> /tmp/evoagent-clean && cd /tmp/evoagent-clean
python3 -m pytest tests/ -q

# 2) 基准注册表结构（不依赖外部数据）
python3 -c "from evoagent.p0_registry import STAGE_COUNTS, PER_DOMAIN; print(STAGE_COUNTS, sum(STAGE_COUNTS.values()), 'x', PER_DOMAIN)"

# 3) 持久运行时崩溃恢复
python3 -m pytest tests/test_durable_runtime.py -q
# 4) 24h soak 报告（17,257 周期 / 466/466 / 100%）
cat docs/p0-durable-runtime-and-soak-report.md
```

## 目录结构

```
evoagent/
├── src/evoagent/            # 包：闭环控制器 + P0 注册表/评测/回滚 + 持久运行时
├── benchmarks/registry-v2/  # 基准清单（summary.json: 360 任务/8 域/4 阶段；完整数据在仓库外）
├── tests/                   # pytest 套件（237 passed + 10 skipped @ 冒号无关路径）
├── examples/                # 示例种子 + benchmark.json
├── docs/                    # p0-durable-runtime-and-soak-report.md 等
├── pyproject.toml
└── README.md
```
