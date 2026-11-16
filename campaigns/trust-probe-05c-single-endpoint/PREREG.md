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


## 复跑增补（2026-11-16）

本目录与 `trust-probe-05-single-endpoint` 设置完全相同，是同一模型的**重复观测**，
用途是把「prompt 到底稳定落在 L2 还是 L3」从单次观察变成分布：

- 判据（先验）：同一模型同一温度下，prompt 的 L 若在多次复跑间变化，
  则说明该 kind 的 level 判定在低精度区不可复现，任何单跑结论不得当作 kind 性质；
  若多次一致，则分布收敛，可作为「该 kind 在本 bench 上的稳定读数」记录。
- 不做跨模型比较（那是 probe-02 的事）；不改任何阈值。
- 仍是机制 probe：不宣称能力提升、不改论文数字。
