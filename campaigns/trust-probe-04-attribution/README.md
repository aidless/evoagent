# trust-probe-04-attribution（归因友好真账本，1 edit/candidate）

预注册见 [PREREG.md](PREREG.md)，运行卡 [RUN_CARD.md](RUN_CARD.md)。

## 目的
在每候选恰 1 笔 edit 的约束下复跑 12 轮真 LLM 自声明预测，使 `reconcile` 可产出 `regression_attribution=attributed|none`（不再因多 edit 触发 shared blame），验证 per-edit 归因与双回归率在真实账本上的可观测性（岔口① 数据侧补强）。机制 probe，非科学结论。

## 与 probe-01 的差异
- **唯一变量**：每候选 1 笔 edit（probe-01 为 2 笔）；proposer prompt/校验相应收紧。
- 不变量：bench/6 开关/seed/`min_gain 2.0`/statistical_gate off/模型 `workbuddy/deepseek-v4.1-flash` T=0.7/12 轮/失败不编造/detached+checkpoint。

## 结果（本次实跑）
见 [campaign_report.json](campaign_report.json)、[verdicts.jsonl](verdicts.jsonl)。
- 12/12 completed, 0 failed, 36 行/36 edits, wall_clock 187.38s。
- kind 分布：tool/prompt/middleware 各 12（1-edit 轮转 `KINDS[(round*6+j)%6]` 在 3 候选×12 轮下只覆盖 3 类，属本变体实现限制，已如实记录）。
- 归因：`attributed` 27, `none` 9, 无 `shared`；`candidate_regression_rate`/`edit_regression_rate` 全覆盖且均为 {0,1}（单 edit 使 edit 级与候选级对齐）。
- 结论：兑现了“归因字段在真账本落盘且可为 attributed”的目标；因仅 3 类 kind + 单 edit 结构，**不用于**替代 probe-01 的阈值判别结论。

## 复现
```bash
cd evoagent/campaigns/trust-probe-04-attribution
PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &
```
消费：`cd /home/liuzewen/F:\deepseek && PYTHONPATH=eval-meta /usr/bin/python3 -m eval_meta.trust evoagent/campaigns/trust-probe-04-attribution/verdicts.jsonl --regression-basis candidate`
