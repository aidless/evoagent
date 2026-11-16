# PROMPT_VARIANCE — 同设置复跑的 kind 级 L 分布

- 复跑数：5；回归率口径：`edit`；`MIN_EDITS=5`
- 判据（先验）：全一致 = `STABLE`；≥2 种 level = `UNSTABLE`（单跑不得当 kind 性质引用）

## 逐跑读数

| 账本 | 行 | overall | tool | prompt | middleware | memory | workflow | subagent |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| trust-probe-01 | 30 | BLOCK | L1 (0.750,0.100) | L2 (0.200,0.100) | L3 (0.533,1.000) | L3 (0.200,1.000) | L3 (0.667,1.000) | L3 (0.350,1.000) |
| trust-probe-01-rerun-c4badd0 | 36 | BLOCK | L1 (0.792,0.083) | L3 (0.083,0.167) | L3 (0.667,0.917) | L3 (0.167,1.000) | L3 (0.556,1.000) | L3 (0.542,1.000) |
| trust-probe-05-single-endpoint | 30 | BLOCK | L1 (0.950,0.000) | L3 (0.000,0.000) | L3 (0.733,0.800) | L3 (0.000,1.000) | L3 (0.533,1.000) | L3 (0.550,1.000) |
| trust-probe-05b-single-endpoint | 33 | BLOCK | L1 (0.909,0.091) | L3 (0.000,0.000) | L3 (0.636,1.000) | L3 (0.273,1.000) | L3 (0.833,1.000) | L3 (0.318,1.000) |
| trust-probe-05c-single-endpoint | 33 | BLOCK | L1 (0.909,0.091) | L3 (0.000,0.091) | L3 (0.545,1.000) | L3 (0.091,1.000) | L3 (0.773,1.000) | L3 (0.364,1.000) |

## 分布与判定

| kind | 分布 | 判定 |
| --- | --- | --- |
| tool | L1×5 | **STABLE** |
| prompt | L2×1, L3×4 | **UNSTABLE** |
| middleware | L3×5 | **STABLE** |
| memory | L3×5 | **STABLE** |
| workflow | L3×5 | **STABLE** |
| subagent | L3×5 | **STABLE** |

## 结论

- `UNSTABLE`：prompt —— 这些 kind 的 level 在同设置复跑间不一致，任何单跑给出的 level 都不是该 kind 的稳定性质。
- 机制 probe：不改任何阈值、不改论文数字。
