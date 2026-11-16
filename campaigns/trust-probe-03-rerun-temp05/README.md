# trust-probe-03-rerun-temp05

岔口 ② 的温度复跑变体。唯一变量：`MAGPIE_MODEL=workbuddy/deepseek-v4.1-flash`，`MAGPIE_TEMPERATURE=0.5`。

复现：
```bash
cd evoagent/campaigns/trust-probe-03-rerun-temp05
MAGPIE_TEMPERATURE=0.5 PYTHONPATH=../../src nohup python3 run_campaign.py --rounds 12 >campaign.stdout.txt 2>campaign.stderr.txt &
```
消费：`PYTHONPATH=../../../eval-meta python3 -m eval_meta.trust verdicts.jsonl`
