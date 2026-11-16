# trust-probe-02-rerun-model-alt（岔口 ② 可复现性复跑）

- 时间：2026-11-16（America/Los_Angeles）
- 目的：在同一 bench/同一 proposer 结构/同一 min_gain=2.0 冻结条件下，更换模型端点复跑 12 轮，检验 kind 级 L 分布可复现性（机制 probe，非科学结论）。
- 与 trust-probe-01 的差异（唯一实验变量）：`MAGPIE_MODEL=group/difficulty-four`（路由池，非单一固定权重 ID；快探针可用）。原单模型候选 `nvidia/deepseek-ai/deepseek-v4.1-flash` 快探针超时、`commandcode/...` 403，故选可用且不同于 baseline 的端点。
- 不变量：benchmark 12 例、6 开关、seed 全关、min_gain=2.0、statistical_gate off、每轮 3 候选×2 edits、kind 轮转/过滤/失败不编造规则同 `PREREG.md`；`MAGPIE_TEMPERATURE=0.7`。
- 执行：detached + checkpoint（`run_campaign.py --rounds 12`），stdout/stderr 落 campaign.stdout.txt/campaign.stderr.txt。
- 产物：`verdicts.jsonl`、`checkpoint.json`、`campaign_report.json`、`REPRO_COMPARE.md`（对比阶段生成）。
