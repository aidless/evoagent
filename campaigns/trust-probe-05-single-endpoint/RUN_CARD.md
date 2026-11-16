# RUN_CARD — trust-probe-05-single-endpoint
- 模型：固定 `workbuddy/deepseek-v4.1-flash`（单端点），T=0.7
- 目的：去噪 probe-02 路由池混杂（prompt L2↔L3 波动来源分离）
- 命令：`PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
- 对照：probe-01（同模型同温度，旧账本）、probe-02（路由池 T=0.7）、probe-03（同模型 T=0.5）
- 消费：`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl`
