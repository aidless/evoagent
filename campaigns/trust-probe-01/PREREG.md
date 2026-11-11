# 预注册：trust-probe-01（真 LLM 自声明预测账本）

登记时间：2026-11-11（America/Los_Angeles）
关联件：P1 `change_manifest` + P4 `eval_meta.trust` 阈值判别力复核。

## 目的

`eval_meta/trust.py` 的四个阈值（`MIN_EDITS=5`、
`REGRESSION_BLOCK_RATE=0.30`、`PRECISION_TRUST_FLOOR=0.50`、
`PRECISION_BLIND_FLOOR=0.20`、`REGRESSION_TRUST_CEIL=0.10`）目前只被合成夹具
的 selftest 验过。本 campaign 用**真实 LLM 调用**产生的 per-edit 账本复核四阈值
在真数据上有没有判别力，并暴露 `score_kind` 的结构缺陷。

## 底物（固定，不演化）

- 自造确定性字符串规范化 bench，12 例（`benchmark.json` + `evaluator.py`）。
  与 `wse-bench-public` 的冻结预注册无任何关系，不触碰别的研究线。
- 6 个正交开关：`trim_whitespace` / `collapse_spaces` / `strip_punct` /
  `normalize_case` / `dedupe_words` / `reverse_words`（最后一个是故意有害变换）。
- `seed.json` 全关，`evo.json` 设 `min_gain: 2.0`（不可能达到）→ **禁止晋升**，
  12 轮的 baseline 与 failures 完全相同。变的是 LLM 的自声明预测，不是被测系统。
  这让账本测的是「预测质量」，而不是「演化效果」。
- 关闭 `statistical_gate`、不配 `post_evolution_intelligence_command`
  （`core.py:256` 默认 1800s 会拖死 campaign）。

## 执行契约

- 12 轮，每轮 1 次 Magpie 网关调用（`workbuddy/deepseek-v4.1-flash`），产出 3 个候选。
- 每个候选带 `change_manifest.edits`，每笔编辑自声明
  `predicted_fix` / `predicted_regression` / `kind` / `target_files`。
- `kind` 从 6 类取：tool / prompt / middleware / memory / workflow / subagent。
- 预测里的任务 id 必须来自 bench 的 12 个 id；引用不存在的 id 的候选直接丢弃。
  （理由：`change_manifest.py:97-101` 的 `invalid_prediction` 分支不写 `kind`，
  会让 `trust.py` 把它归进 `unknown` 类，污染真账本。）
- LLM 调用失败或 JSON 解析失败 → 该轮输出空候选、记 `failed_rounds`，**不编造数据**。
- checkpoint 写 `checkpoint.json`（轮号 + run_id + 成败），支持 `--resume` 断点续跑。
- 每轮结束把 `.evo/verdicts.jsonl` 拷成 `verdicts.jsonl`（`.evo/` 被 gitignore）。

## 判据（先验，不随观测改）

1. 账本里至少 4 种 kind 各有 ≥`MIN_EDITS=5` 笔编辑；否则结论标 `INSUFFICIENT`。
2. 四个阈值各自做「原值 vs 跨过观测值」两跑，判决必须能翻转；不能翻转 = 该阈值
   在这份账本上无判别力，如实记为 `NO_DISCRIMINATION`，**不事后调阈值去凑绿**。
3. 本 campaign 是机制 probe，不是科学结论：不宣称 AHE 的 33.7% 精度可复现，
   不把自造 bench 上的精度当外部泛化证据，不拿来改论文里的任何数字。

## 环境口径

- Magpie 网关是本机 `127.0.0.1:3425`，无法上云；AGENTS.md 第 17 条下以
  detached + checkpoint 执行，实测墙钟写入 `campaign_report.json`。
- 本机零训练、零 GPU 占用；只跑编排与亚分钟级 subprocess 评测。
