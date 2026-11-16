# REPRO_COMPARE — 岔口 ② kind 级 L 分布可复现性（机制 probe）

生成时间：2026-11-16（America/Los_Angeles）。对比对象：probe-01 基线 vs 两个单变量复跑。

## 运行条件

| 运行 | 模型 | 温度 | 完成轮/总轮 | 失败轮 | verdicts 行 | 每类 edits | wall_clock_s |
|---|---|---:|---:|---|---:|---:|---:|
| probe-01 | `workbuddy/deepseek-v4.1-flash` | 0.7 | 10/12 | [6, 8] | 30 | 10 | 244.62 |
| probe-02-model-alt | `group/difficulty-four（路由池；直连单模型候选探针超时/403）` | 0.7 | 11/12 | [9] | 33 | 11 | 242.54 |
| probe-03-temp05 | `workbuddy/deepseek-v4.1-flash` | 0.5 | 11/12 | [8] | 33 | 11 | 267.51 |

## kind 级判定对比（trust.score_history）

| kind | probe-01 | probe-02-model-alt | probe-03-temp05 | L 一致? |
|---|---|---|---|---|
| tool | L1 (p=0.750, reg=0.100) | L1 (p=0.955, reg=0.000) | L1 (p=0.955, reg=0.000) | yes |
| prompt | L2 (p=0.200, reg=0.100) | L3 (p=0.000, reg=0.091) | L3 (p=0.000, reg=0.000) | no |
| middleware | L3 (p=0.533, reg=1.000) | L3 (p=0.682, reg=1.000) | L3 (p=0.591, reg=0.909) | yes |
| memory | L3 (p=0.200, reg=1.000) | L3 (p=0.227, reg=1.000) | L3 (p=0.318, reg=1.000) | yes |
| workflow | L3 (p=0.667, reg=1.000) | L3 (p=0.788, reg=1.000) | L3 (p=0.864, reg=1.000) | yes |
| subagent | L3 (p=0.350, reg=1.000) | L3 (p=0.455, reg=1.000) | L3 (p=0.182, reg=1.000) | yes |

**总体 verdict：** probe-01=BLOCK, probe-02=BLOCK, probe-03=BLOCK。**6 类 kind 的 L 级全一致：False。**

## 观察（事实）

- 三次运行均 BLOCK；`tool` 稳定 L1，`middleware/memory/workflow/subagent` 稳定 L3，`prompt` 在 probe-01 为 L2、两次复跑为 L3（均处低预测精度区间：probe-01 p=0.200 reg=0.100；probe-02 p=0.000 reg=0.091 且 blind；probe-03 p=0.000 reg=0.000 且 blind）。
- 复跑均出现 1 轮空候选失败（probe-02 round 9，probe-03 round 8），未编造数据；有效样本量 11 edits/kind，仍满足 `MIN_EDITS=5`。
- probe-02 端点 `group/difficulty-four` 为路由池（探针可用），**不是**与 baseline 同分布的固定权重模型；该复跑同时混入模型与路由不确定性，需与 probe-03（同模型、改温度）合读，不能单独等同于“同模型可复现”。
- 本比较反映 **本 bench+proposer 机制下 trust 分级跨运行形态**；不构成外部任务/模型泛化结论，不改变论文数字，不代表阈值已对外部分布校准。
