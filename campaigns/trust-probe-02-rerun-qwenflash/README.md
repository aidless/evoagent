# trust-probe-02-rerun-model-alt

岔口 ② 的模型端点复跑变体。唯一变量：`MAGPIE_MODEL=group/difficulty-four`（快探针 OK；同名模型直连候选在探针阶段超时/403），`MAGPIE_TEMPERATURE=0.7`。

复现：
```bash
cd evoagent/campaigns/trust-probe-02-rerun-qwenflash
MAGPIE_MODEL=group/difficulty-four PYTHONPATH=../../src nohup python3 run_campaign.py --rounds 12 >campaign.stdout.txt 2>campaign.stderr.txt &
```
消费：`PYTHONPATH=../../../eval-meta python3 -m eval_meta.trust verdicts.jsonl`
