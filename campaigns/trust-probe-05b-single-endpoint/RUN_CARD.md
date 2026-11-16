# RUN_CARD — 单端点复跑（固定 `workbuddy/deepseek-v4.1-flash`，T=0.7）
- 目的：与 `trust-probe-05-single-endpoint` 同一设置重复跑，量出 **kind 级 L 的复跑分布**
  （尤其 prompt 在 L2/L3 之间是否波动），把「单次观察」升级成「可数分布」。
- 模型/温度/bench/6 开关/`min_gain 2.0` 禁晋升/statistical_gate 关 全部同 05。
- 轮次：12，detached + checkpoint；失败轮不补造。
- 命令：`PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
- 产物：`verdicts.jsonl` / `checkpoint.json` / `campaign_report.json`
- 消费：`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl --regression-basis candidate`
