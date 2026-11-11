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
| `benchmarks/generated_date/questions.json` | 3 | `benchmarks/generated_date/questions.json:1-2706` |
| `benchmarks/generated_logic/questions.json` | 3 | `benchmarks/generated_logic/questions.json:1-1006` |
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
