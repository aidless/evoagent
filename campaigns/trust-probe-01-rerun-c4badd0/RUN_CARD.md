# RUN_CARD — trust-probe-01-rerun-c4badd0
- 模型：`workbuddy/deepseek-v4.1-flash`（同 probe-01），T=0.7
- 目的：补齐 `candidate_regression_rate`/`edit_regression_rate` 覆盖（父账本 30 行缺失）
- 命令：`PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
- 消费：`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl --regression-basis candidate`
