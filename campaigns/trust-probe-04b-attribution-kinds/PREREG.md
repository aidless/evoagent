# 预注册：trust-probe-04b-attribution-kinds（1 edit/candidate × 6 类全覆盖）

登记时间：2026-11-16（America/Los_Angeles）
前身：`trust-probe-04-attribution`（同变体，但 kind 轮转有缺陷，见下）。

## 为什么重跑

`trust-probe-04-attribution` 的 1-edit 变体把 kind 写成
`KINDS[(round_no * 6 + j) % len(KINDS)]`。`round_no * 6` 恒被 6 整除 → 退化为
`KINDS[j % 6]`，而 j 只取 0/1/2，36 笔只落到 tool/prompt/middleware 三类
（该目录 `verdicts.jsonl` 实测 kind 计数 `{tool:12, prompt:12, middleware:12}`）。
那份账本因此只兑现了「归因字段能落盘」，**没有**给出 memory/workflow/subagent
三类在 1-edit 结构下的证据。

本 campaign 的唯一改动：`kind_for(round_no, candidate_index) = KINDS[(round_no*3 + candidate_index) % 6]`，
12 轮 × 3 候选 = 36 笔，6 类各 6 笔。反证见
`evoagent/tests/test_campaign_proposer_kind_rotation.py::test_old_rotation_formula_would_fail_this_assertion`。

## 不变量（与 probe-04 完全一致，只差 kind 轮转）

- 每候选 **恰 1 笔 edit**（保证 `reconcile` 的 unanticipated regression 能唯一归因到该 edit，
  不再 shared blame）。
- 自造确定性字符串规范化 bench 12 例（c01..c12）、6 个正交开关、`seed.json` 全关。
- `min_gain: 2.0` 禁晋升 → 12 轮 baseline/failures 固定，账本测「预测质量」不测「演化效果」。
- `statistical_gate` 关、不配 `post_evolution_intelligence_command`。
- 模型 `workbuddy/deepseek-v4.1-flash`（固定单端点），T=0.7，12 轮。
- 预测 id 必须来自 12 个真实 id，幻觉 id 的 edit 入账前丢弃；LLM 失败 → 空候选 + `failed_rounds`，不编造。
- checkpoint/resume；每轮 copy `.evo/verdicts.jsonl` → `verdicts.jsonl`。

## 判据（先验，不随观测改）

1. 账本 36 行/36 edits，**6 类各 6 笔**（由 `kind_for` 保证，可复算）。
2. `regression_attribution` 必须出现 `attributed` 与 `none`，且 `shared` 应为 0
   （单 valid edit 时 reconcile 走 attributed/none 分支）。
3. 若出现 `candidate_regression_rate` 中间值（0<c<1），说明单 edit 结构下仍可读出
   「候选内有涨有跌」；若全为 {0,1}，如实记为「1-edit 结构下候选级率退化为二值」。
4. 本 campaign 是机制 probe：不宣称 AHE 精度可复现、不改论文任何数字。

## 环境口径

Magpie 网关本机 `127.0.0.1:3425` 无法上云；AGENTS.md 第 17 条下 detached + checkpoint。
零训练、零 GPU 占用。
