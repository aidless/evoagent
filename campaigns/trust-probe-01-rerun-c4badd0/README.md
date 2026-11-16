# trust-probe-01-rerun-c4badd0（补齐候选级率覆盖的同代重跑）

预注册见 [PREREG.md](PREREG.md)，运行卡 [RUN_CARD.md](RUN_CARD.md)。父账本 `../trust-probe-01/`（f17b9b7 产物）保留不动，其 30 行缺 `candidate_regression_rate`/`edit_regression_rate`。

## 目的
在当前 `reconcile`+`verdict_history`（c4badd0/4ed5e02，候选级率与归因字段落盘）下，用与 probe-01 相同 bench/模型/温度/契约重跑 12 轮，补齐 candidate-rate 行覆盖，便于同代口径对照。**非原地回填**：LLM 采样与候选内容可与父账本不同。

## 结果（本次实跑）
- 12/12 completed, 0 failed, 36 行/72 edits, 6 类各 12, wall_clock 160.16s。
- `candidate_regression_rate` 覆盖 36/36；`edit_regression_rate` 取值含 {0,0.5,1}；mixed 候选 12；归因 none 22/shared 33/attributed 17（字段在真账本落盘）。
- 结论：解决了父账本 30 行缺率问题；本跑可与 probe-02/03/05 在同代字段上做 candidate 视角分析。

## 复现/消费
```bash
cd evoagent/campaigns/trust-probe-01-rerun-c4badd0
PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &
```
`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl --regression-basis candidate`
