# 预注册：trust-probe-05-single-endpoint（固定单端点去噪复跑）

登记时间：2026-11-16（America/Los_Angeles）
对照：`campaigns/trust-probe-02-rerun-qwenflash/`（`group/difficulty-four` 路由池，prompt L2↔L3 波动）、`campaigns/trust-probe-01/`

## 目的
固定 **单一端点** `workbuddy/deepseek-v4.1-flash`（T=0.7），在同 bench/同契约下复跑 12 轮，分离“路由池混杂”与“模型/温度差异”对 kind 级 L 分布的影响（岔口②去噪）。

## 不变量
- 与 probe-01 相同：12 轮、每轮 3 候选×2 edits、`min_gain 2.0` 禁晋升、`statistical_gate` off、不配 `post_evolution_intelligence_command`、kind 轮转/过滤/失败不编造、detached+checkpoint。
- 唯一变量相对 probe-02：模型由 `group/difficulty-four` 路由池改为固定端点 `workbuddy/deepseek-v4.1-flash`。

## 执行
`cd evoagent/campaigns/trust-probe-05-single-endpoint && PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &`
