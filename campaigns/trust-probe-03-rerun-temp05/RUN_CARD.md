# trust-probe-03-rerun-temp05（岔口 ② 可复现性复跑）

- 时间：2026-11-16（America/Los_Angeles）
- 目的：在同一 bench/同一模型条件下，改变采样温度复跑 12 轮，检验 kind 级 L 分布可复现性（机制 probe，非科学结论）。
- 与 trust-probe-01 的差异（唯一实验变量）：`MAGPIE_TEMPERATURE=0.5`（原 0.7），模型保持 `workbuddy/deepseek-v4.1-flash`。
- 不变量：benchmark 12 例、6 开关、seed 全关、min_gain=2.0、statistical_gate off、每轮 3 候选×2 edits、kind 轮转/过滤/失败不编造规则同 `PREREG.md`。
- 执行：detached + checkpoint（`run_campaign.py --rounds 12`），stdout/stderr 落 campaign.stdout.txt/campaign.stderr.txt。
- 产物：`verdicts.jsonl`、`checkpoint.json`、`campaign_report.json`、`calibration_sweep.json`、`CALIBRATION.md`（若补跑校准）、`REPRO_COMPARE.md`。
