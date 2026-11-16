# RUN_CARD — trust-probe-04-attribution
- 模型：`workbuddy/deepseek-v4.1-flash`（固定端点），T=0.7
- 变量：**每候选 1 笔 edit**（兑现 per-edit 归因；对照 probe-01 的 2 edits）
- 轮次：12，`min_gain 2.0` 禁晋升，detached+checkpoint
- 命令：`PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
- 产物：`verdicts.jsonl`/`checkpoint.json`/`campaign_report.json`
- 消费：`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl --regression-basis candidate`
- 结果摘要：36 行全覆盖，attributed 27 / none 9 / shared 0；kind 仅 tool/prompt/middleware 各 12（`KINDS[(round*6+j)%6]` 在 1-edit×3 候选下的轮转限制，已如实记录）。
