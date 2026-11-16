# RUN_CARD — trust-probe-04b-attribution-kinds
- 模型：`workbuddy/deepseek-v4.1-flash`（固定单端点），T=0.7
- 变量：每候选 **1 笔 edit** + kind 轮转步长 **3**（12 轮 × 3 候选 → 6 类各 6 笔）
- 轮次：12，`min_gain 2.0` 禁晋升，detached + checkpoint
- 命令：`PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
- 产物：`verdicts.jsonl` / `checkpoint.json` / `campaign_report.json`
- 消费：`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl --regression-basis candidate`
