# REPRO_COMPARE — probe-05 (fixed single endpoint) vs probe-01/02/03

> 目的：分离 probe-02（`group/difficulty-four` 路由池）prompt L2↔L3 波动来源（岔口②去噪）。机制 probe，非科学结论。

## 运行条件

| 账本 | 模型/端点 | T | 轮次完成/失败 | 行/编辑 | kind 各 |
| --- | --- | --- | --- | --- | --- |
| trust-probe-01 (f17b9b7, 旧字段) | `workbuddy/deepseek-v4.1-flash` 单端点 | 0.7 | 10/2 | 30/60 | 10 |
| trust-probe-01-rerun-c4badd0 (同代字段) | `workbuddy/deepseek-v4.1-flash` 单端点 | 0.7 | 12/0 | 36/72 | 12 |
| trust-probe-02-rerun-qwenflash | `group/difficulty-four` **路由池** | 0.7 | 11/1 | 33/66 | 11 |
| trust-probe-03-rerun-temp05 | `workbuddy/deepseek-v4.1-flash` 单端点 | 0.5 | 11/1 | 33/66 | 11 |
| **trust-probe-05-single-endpoint (本跑)** | `workbuddy/deepseek-v4.1-flash` **固定单端点** | 0.7 | 10/2 | 30/60 | 10 |

## kind 级 L 分布（edit 视角，`eval_meta.trust` 默认）

| kind | probe-01 | rerun-c4badd0 | probe-02(路由池,0.7) | probe-03(0.5) | **probe-05(单端点,0.7)** |
| --- | --- | --- | --- | --- | --- |
| tool | L1 (0.75,0.10) | L1/L2 见 JSON* | L1 (0.955,0.00) | L1 (0.955,0.00) | **L1 (0.95,0.00)** |
| prompt | L2 (0.20,0.10) | L3* | L3 (0.00,0.091,blind) | L3 (0.00,0.00,blind) | **L3 (0.00,0.00,blind)** |
| middleware | L3 (0.533,1.00) | L3* | L3 (0.682,1.00) | L3 (0.591,0.909) | **L3 (0.733,0.80)** |
| memory | L3 (0.20,1.00) | L3* | L3 (0.227,1.00) | L3 (0.318,1.00) | **L3 (0.00,1.00)** |
| workflow | L3 (0.667,1.00) | L3* | L3 (0.788,1.00) | L3 (0.864,1.00) | **L3 (0.533,1.00)** |
| subagent | L3 (0.35,1.00) | L3* | L3 (0.455,1.00) | L3 (0.182,1.00) | **L3 (0.55,1.00)** |

\* rerun-c4badd0 的逐 kind 精确数见 `PYTHONPATH=../../../eval-meta python3 -m eval_meta.trust verdicts.jsonl` 输出（本跑为新采样，非父账本复刻）；上表 rerun 列仅示意其 overall BLOCK 与分布方向，精确消费以账本为准。

## 观察
- **tool** 在四条含同代/可比跑中稳定 L1（probe-02/03/05 及 rerun 方向一致），最稳健。
- **prompt** 处于低精度盲区：probe-01 为 L2，但 probe-02(路由池)/03(降温)/05(固定单端点同模型同温) 均落 L3 且 precision≈0、blind。probe-05 与 probe-02 同为 L3，**不支持**“probe-02 的 L3 单独由路由混杂造成”的强结论；更像 prompt 在此 bench+预测任务下本就易落盲预测区，L2↔L3 波动受采样/失败轮影响。
- **middleware/memory/workflow/subagent** 在 probe-02/03/05 均为 L3，回归率高位主导，与先前结论一致。

## 边界
单跑、每类 10 笔、存在失败轮（2 轮空候选），且 LLM 预测随机性高；本对比仅提供“路由混杂不是 prompt 波动的唯一解释”的证据，不改变阈值，不构成科学结论。
