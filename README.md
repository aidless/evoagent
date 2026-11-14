# EvoAgent：受评测约束的自进化闭环

> **English TL;DR**: An auditable self-improvement loop for agent policies: candidates are evaluated on a frozen benchmark in an isolated temp dir, must clear a safety gate and beat the incumbent by `min_gain` before an atomic promote — every promotion keeps a rollback snapshot. Zero runtime dependencies; the demo seed goes 1/4 → 4/4. Stated boundary: the shipped loop evolves data configs only, never its own execution code; `benchmarks/raw/` model-eval data is private and not distributed.

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

在仓库根目录执行（PowerShell）：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m evoagent.cli init
python -m evoagent.cli evolve
python -m evoagent.cli status
python -m unittest discover -s tests -v
```

bash 等价：

```bash
PYTHONPATH=src python -m evoagent.cli init
python -m evoagent.cli evolve
python -m evoagent.cli status
python -m unittest discover -s tests -v
```

示例种子只能通过 1/4 用例；闭环会评测三个候选，并将同时支持大小写归一化和空白清理的候选晋升到 4/4。运行记录位于 `.evo/runs/`，历史版本位于 `.evo/history/`。

## 实测验证（2026-11-10，Python 3.12.3，本机实录）

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
# Ran 245 tests in 18.228s — OK (skipped=10)
```

init → evolve → status 全链实跑：`init` 正常产出 `.evo/active.json`；闭环评测与晋升路径按设计走通（示例种子 1/4 → 4/4）。

## Limits（如实边界）

- `evolve`/`status` 中的 intelligence 自评子步依赖 `benchmarks/raw/gsm8k-test.jsonl`——该目录是私有评测数据，不随仓库分发；无此文件时该子步报 `FileNotFoundError` 并 `verified:false`，其余子步（评测、晋升、回滚）不受影响。
- P0 两节的数字（360 任务、135/135、40.0% vs 33.3%、100 次压力事件）引自 2026-07-25 的原始运行记录，本仓库不含可复跑这些数字的私有数据；Bundle 哈希以运行时输出为准。

## 接入真实 Agent

- 将 `seed.json` 换成当前提示词、工具策略或参数配置。
- 将 `examples/benchmark.json` 换成冻结的代表性任务集；保留一份不参与提案的隐藏测试集更可靠。
- 将 `evaluator_command` 指向真实评测器。每个用例通过环境变量获得 `EVO_CANDIDATE`、`EVO_INPUT`、`EVO_EXPECTED`、`EVO_CASE_ID`，并向 stdout 返回 `{"passed": true}`。
- 可设置 `proposer_command` 接入任意本地或远程模型。它从 `EVO_INCUMBENT` 和 `EVO_FAILURES` 读取上下文，向 stdout 输出 JSON 候选数组。

## 安全原则

当前版本默认只进化数据配置，不允许框架自动改写自身执行代码；候选在临时目录评测、每项有超时、晋升有门槛且可回滚。生产使用时还应加入隐藏回归集、成本/延迟上限、人工审批、网络与文件权限隔离以及签名发布。

**Fail-closed 声明（真实机制，见 `src/evoagent/stage_gates.py::evaluate_four_stage` + `src/evoagent/l3_provisional.py`）：**

晋升是**严格门控**，不是"尽量通过"。以下任一条件都会产生 `reasons` 并使 `auto_promote = False`（`l3_provisional.py` 随后 `raise RuntimeError("four_stage_gate_rejected")`）：

- 任一阶段缺失（`missing:{stage}`）、样本量不足（`insufficient_n`）、未通过（`failed:{stage}`）、存在安全违规（`safety_violation:{stage}`）；
- 要求真实执行时，证据的 `evidence_kind != "benchmark_execution"` 或 `real_execution is not True` → `unverified_execution:{stage}`（**这是核心 fail-closed**：没有真实 benchmark 执行记录，绝不晋升）；
- 工件缺失（`missing_artifact`）或工件哈希与记录不符（`artifact_changed`）；
- 任务集重复使用（`task_set_reuse`）。

默认 `require_real_execution=True`（L3_PROVISIONAL），`require_artifacts` 同启。**晋升的唯一入口是 `auto_promote=True`**——任何证据不满足即整体拒绝，绝不静默降级为"原样继续"。


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

## P0：Benchmark Registry v2（2026-07-25）

> 说明：本节原文在一次编码事故中损坏为 `?`，以下为依据可辨认事实重建的版本；原始私有数据不随仓库分发。

Benchmark Registry v2 是 L3 层评测：共 360 任务（Development 120 / Hidden Confirmation 80 / Trigger Safety 60 / Shadow 100），模型评测使用其中 45 个；私有数据目录（原路径 `E:\self-evolving-agent-private`）不随仓库分发。指标口径：Coverage、Selective Accuracy、Appropriate Abstention、Unnecessary Abstention。

L3 判据要求 benchmark artifact 具备 `real_execution=true`；Bundle 晋升需要 Candidate / Bundle / Evidence 证据链完整且 `passed=True`。`self_verify_v2_l3` 自校验 **135/135** 通过（失败 **0**）。

Bundle 当前状态（按可辨认部分重建，符号以运行时输出为准）：

```text
6bc00a318f9c (self_verify_v2_l3)
  provisional → experimental
  automatic safety rollback
61ed787d516c (self_verify_v1)
  active experimental_safety_fallback
```

当 `active_bundle_valid=false` 时，需要重新产出 Bundle 并通过同一判据后再置为 Stable。

模型实测：Qwen2-7B 在 45 任务中，Coverage 口径（10 任务子集）**40.0%** 对 **33.3%**。

运行入口（在仓库根目录执行；原始命令使用绝对路径，此处已改为相对路径）：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m evoagent.p0_registry --root .
python -m evoagent.p0_evaluation --root .
python -m evoagent.p0_model_evaluation --root . --endpoint http://127.0.0.1:1234/v1

# 回滚（先预演，确认后再 --apply）
python -m evoagent.p0_rollback --root .
python -m evoagent.p0_rollback --root . --apply
Get-Content .evo/benchmark-registry-v2/current-status.json
```

## P0：运行时加固（2026-07-25）

> 说明：本节原文同样在编码事故中损坏，以下为依据可辨认事实重建的版本。

运行时加固覆盖：Action Policy（写路径白名单与信任根变更判定）、RunState、SHA-256 哈希链 Checkpoint、Lease/Heartbeat、Kill Switch 与 Durable Scheduler。对应实现见 `src/evoagent/action_policy.py`、`durable_run.py`、`event_log.py`、`checkpoint.py`、`lease.py`、`budget.py`、`idempotency.py`、`guarded_executor.py`、`scheduler.py`。

压力测试报告为本地运行产物（不入库）：`.evo/durable-runtime-smoke/p0-report.json`（100 次压力事件、异常 0、231 条事件日志；口径以该报告文件为准）。

## U1 results table (recomputed 2026-11-11)

Numbers below come only from committed JSON files in this repository, recomputed
locally. The private `benchmarks/raw/gsm8k-test.jsonl` data and the P0 historical
records are **not** used here (see `Limits` above).

| Result | Value | Source (path:line) |
|---|---|---|
| Hidden verification flag | `true` | `research/prompt-candidates/verify-hidden-result.json:2` |
| Hidden cases passed | **4/6** | `research/prompt-candidates/verify-hidden-result.json:4` |
| Hidden score | 0.6666666666666666 | `research/prompt-candidates/verify-hidden-result.json:3` |
| Candidate decision | `reject_no_gain` | `research/prompt-candidates-v2/decision.json:61` |
| Hidden test run | `false` | `research/prompt-candidates-v2/decision.json:62` |
| Active policy unchanged | `true` | `research/prompt-candidates-v2/decision.json:63` |
| Pairwise comparisons recorded | 6 | `research/prompt-candidates-v2/decision.json:11` |

Per-suite hidden verification (same file):

| Suite | Passed / total | Source (path:line) |
|---|---|---|
| `bbh_date` | 1/2 | `research/prompt-candidates/verify-hidden-result.json:7` |
| `bbh_logic` | 1/2 | `research/prompt-candidates/verify-hidden-result.json:12` |
| `gsm8k` | 2/2 | `research/prompt-candidates/verify-hidden-result.json:17` |

Public benchmark question counts (recomputed from committed question files):

| File | Questions | Source (path:line) |
|---|---|---|
| `benchmarks/generated_date/questions.json` | 300 | `benchmarks/generated_date/questions.json:1-2706` |
| `benchmarks/generated_logic/questions.json` | 200 | `benchmarks/generated_logic/questions.json:1-1006` |
| `benchmarks/learning/public/questions.json` | 24 | `benchmarks/learning/public/questions.json:1-269` |

**Quickstart command actually executed for this pass**:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q

# Ran 245 tests in 20.696s

# OK (skipped=10)
```

The wall-clock differs from the historical 18.228s run recorded above; both are
separate executions of the same suite, and only the test/skip counts are claimed
as results. `decision: reject_no_gain` means the candidate did not clear the
`min_gain` bar — the loop kept the incumbent policy, which is the intended
fail-closed behavior, not a passing result.

**NOT YET MEASURED in this pass**: any replay of the private gsm8k hidden split or of the
P0 historical record. The raw split (`benchmarks/raw/gsm8k-test.jsonl`) is not
distributed, so only the committed JSON above is claimed as a result; see `Limits`.

<!-- figure: pending real measurement -->

## 本机可重跑性

`make eval` 跑 `tests/` 共 268 条（cwd=src + `PYTHONPATH=.`），deselect 的 3 条（`tests/test_bundle_signer.py` 2 条、`tests/test_multi_worker.py` 1 条）只在本工作区红：目录名 `F:\deepseek` 含 ':'，会把测试交给子进程的绝对 `PYTHONPATH` 按 POSIX 分隔符切开；同一份树放到无冒号路径下跑 `python3 -m unittest discover -s tests` 是 `Ran 280 tests / OK (skipped=10)`。完整 CI 命令见 `make ci-eval`。

## 验收判据：可执行题库 `eval/cases.jsonl`（2026-11-13）

`eval/cases.jsonl` 共 n = 20 条，覆盖 8 个 axis（schema / manifest / stagegate / promotion /
policy / budget / calibration / data），其中 `expr` 17 条、`raises` 3 条。每条都真调本仓 API 或
真解析本仓数据（`from src.evoagent...`、`benchmarks/generated_date/questions.json`），期望值由
当前实现现算，改一行实现就可能变红。运行器 `eval/run_cases.py` 与其它仓逐字节同源，逻辑零改动。

**验收判据（Pass criteria）**：`python3 eval/run_cases.py` 必须 **20/20 全过，通过率 = 100%**；
`python3 eval/run_cases.py --selftest` 必须变红（19/20，退出码仍为 0，证明不是装饰）；
`make eval` 返回码必须为 0。任一条件不满足即判为未通过，不接受"大部分通过"。

```
$ python3 eval/run_cases.py | tail -1
20/20 cases passed
$ python3 eval/run_cases.py --selftest | tail -1
SELFTEST: 期望变红；若上面仍全绿则这套题无效
```

### 失败归因（按 axis，不只报 pass_rate）

`run_cases.py` 失败时按 axis 汇总失败 id，`--save` 把同一份归因写进 `eval/run-report.json`
（字段 `failed_by_axis`）。`--selftest` 的真实归因输出（实测）：

```
19/20 cases passed
失败归因（按 axis）：
  schema: 1 条 —— schema-prompt-valid
```

即自检篡改的是 schema 轴第一条（`validate_candidate` 的 `valid` 期望），坏了对应
`src/evoagent/candidate_schema.py`。各 axis 与失败时该先看的模块：

| axis | 失败先看 | 题库里的越界点 |
|---|---|---|
| schema | `src/evoagent/candidate_schema.py` | 白名单外顶层键 / 嵌套治理键 |
| manifest | `src/evoagent/change_manifest.py` | `regression` vs `unanticipated_regressions` 桶 |
| stagegate | `src/evoagent/stage_gates.py` | `missing:*` / `task_set_reuse` |
| promotion | `src/evoagent/promotion_gate.py` | `mean_gain` / mcnemar `p_value` / `cost_increase` |
| policy | `src/evoagent/action_policy.py` | `read_only` / `trust_root_change` / `irreversible` |
| budget | `src/evoagent/budget.py` | `tokens` 上限与负增量 |
| calibration | `src/evoagent/calibration.py` | `coverage` / `unnecessary_abstention_rate` |
| data | `benchmarks/generated_date/questions.json` | 题库条数与 id 唯一性 |

仓内另有两套同口径的按类归因，可直接按桶计数：`change_manifest.reconcile` 的 per-edit 四桶
（`regression` / `effective_fix` / `no_effect` / `invalid_prediction`，以及没有被任何 edit 预测到的
`unanticipated_regressions`），和 `stage_gates.evaluate_four_stage` 的 reasons 前缀桶
（`missing:` / `insufficient_n:` / `identity_mismatch:` / `artifact_changed:` / `task_set_reuse`）。
落盘位置：`.evo/verdicts.jsonl` 与 `.evo/stage-gates/<candidate_id>.json`。

### 本次实跑读数（本机，2026-11-13）

| 读数 | 值 | 来源命令 / 文件 |
|---|---|---|
| 题库条数 / axis 数 | 20 / 8 | `wc -l eval/cases.jsonl`；`eval/run-report.json` 的 `results[].axis` |
| 全过 | 20/20 | `python3 eval/run_cases.py` |
| 自检变红 | 19/20，exit 0 | `python3 eval/run_cases.py --selftest` |
| 复算报告 | `eval/run-report.json` | `python3 eval/run_cases.py --save` |
| 单次墙钟 | 0.14 s（全过）、0.15 s（`--selftest`） | `/usr/bin/time -f "wall=%e s" python3 eval/run_cases.py` |

题库里的 300 条 date 题目来自 `benchmarks/generated_date/questions.json`（300 个唯一 `id`，
现数得到）；`benchmarks/generated_logic/questions.json` 为 200 条。本节的数字没有一个是抄的：
每条都能用上表的命令重跑一遍核对。
