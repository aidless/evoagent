# 预注册：trust-probe-01-rerun-c4badd0（补齐候选级率覆盖）

登记时间：2026-11-16（America/Los_Angeles）
父账本：`campaigns/trust-probe-01/`（f17b9b7 时代产物，30 行无 `candidate_regression_rate`/`edit_regression_rate`）

## 目的
用与 probe-01 相同的 bench/seed/模型/温度/轮次，在当前 `reconcile`+`verdict_history`（含候选级率与归因字段落盘，c4badd0/4ed5e02 以来）下重跑 12 轮，补齐候选级回归率行覆盖，使 P4 `regression_basis=candidate` 分析可用同代代码/同口径对 probe-01 行为做对照。

## 不变量
- 与 `campaigns/trust-probe-01/PREREG.md` 相同：12 轮、每轮 3 候选×2 edits、`min_gain 2.0` 禁晋升、`statistical_gate` off、不配 `post_evolution_intelligence_command`、`workbuddy/deepseek-v4.1-flash`、T=0.7、kind 轮转/过滤/失败不编造、detached+checkpoint。
- bench/evaluator/seed/evo/config 不改。

## 注意（非原地回填）
这是**新账本**，不是对原 30 行的字段回填：LLM 采样、失败轮与候选内容可能与父账本不同；原 `trust-probe-01/verdicts.jsonl` 保留不动。

## 执行
`cd evoagent/campaigns/trust-probe-01-rerun-c4badd0 && PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
