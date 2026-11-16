# trust-probe-05-single-endpoint（固定单端点去噪复跑）

预注册 [PREREG.md](PREREG.md)，运行卡 [RUN_CARD.md](RUN_CARD.md)。

## 目的
将模型固定为单端点 `workbuddy/deepseek-v4.1-flash`（T=0.7），在同 bench/同契约下复跑，分离 probe-02（`group/difficulty-four` 路由池）中 prompt L2↔L3 波动的“路由混杂”来源。机制 probe。

## 结果（本次实跑）
- 10/12 completed, failed [2,5]（空候选，未补造）, 30 行/60 edits, 6 类各 10, wall_clock 152.24s。
- edit 视角：overall BLOCK；tool L1 (p=0.95, reg=0.0)、prompt L3 (p=0.0, reg=0.0, blind)、middleware L3 (0.733, 0.8)、memory L3 (0.0, 1.0)、workflow L3 (0.533, 1.0)、subagent L3 (0.55, 1.0)。
- 对照：probe-02（路由池 T=0.7）同样 tool L1/prompt L3/mw/mem/wf/sub L3；probe-03（同模型族 T=0.5）亦然。prompt 在低精度区仍不稳定但本跑未出现 L2，支持“路由混杂是 probe-02 prompt L2↔L3 的可疑来源之一”的观察（单跑证据，不作因果定论）。

## 复现/消费
```bash
cd evoagent/campaigns/trust-probe-05-single-endpoint
PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &
```
`PYTHONPATH=../../../eval-meta /usr/bin/python3 -m eval_meta.trust verdicts.jsonl`

## 本目录定位（重复观测）
与 `trust-probe-05-single-endpoint` 设置完全相同（`workbuddy/deepseek-v4.1-flash`，T=0.7，
同 bench/6 开关/`min_gain 2.0` 禁晋升）。用途是把 `prompt` 等 kind 的 level 判定从
**单次观察**升级为**分布**：三份同设置账本（05/05b/05c）连同 probe-01/01-rerun 一起由
[`../trust-probe-05-single-endpoint/variance_table.py`](../trust-probe-05-single-endpoint/variance_table.py)
摊成 `PROMPT_VARIANCE.md`（判定 `STABLE/UNSTABLE`，见
[`../trust-probe-01/CALIBRATION.md`](../trust-probe-01/CALIBRATION.md) §11）。
