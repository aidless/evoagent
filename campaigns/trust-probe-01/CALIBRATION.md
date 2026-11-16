# P4 阈值校准记录（trust-probe-01）

预注册见 [PREREG.md](PREREG.md)。本文件只记录**可复算**的读数与决定；
扫描脚本 [calibrate.py](calibrate.py)，原始输出 [calibration_sweep.json](calibration_sweep.json)。

## 1. 账本来源

| 项 | 值 | 证据 |
| --- | --- | --- |
| 预注册轮数 | 12 | `PREREG.md` |
| 实际完成轮 | 10 | `checkpoint.json` 的 `completed_rounds` |
| 失败轮 | 6、8（Magpie 返回空候选） | `checkpoint.json` 的 `failed_rounds`，未补造 |
| 账本行 / 编辑笔数 | 30 / 60 | `verdicts.jsonl` |
| 每类 kind 笔数 | 6 类 × 10 | `campaign_report.json` 的 `kind_counts` |
| 墙钟 | 244.62 s | `campaign_report.json` |

verdict 分布：`regression` 42、`effective_fix` 9、`no_effect` 9。
精度载体覆盖率：60/60（本账本**没有** regression-only 编辑）。
候选内 verdict 均一度：20/30 候选的所有 edit 拿到同一个 verdict。

## 2. 基线判定（阈值全取原值）

```
tool        L1   mean_precision=0.750  regression_rate=0.10
prompt      L2   mean_precision=0.200  regression_rate=0.10
middleware  L3   mean_precision=0.533  regression_rate=1.00
memory      L3   mean_precision=0.200  regression_rate=1.00
workflow    L3   mean_precision=0.667  regression_rate=1.00
subagent    L3   mean_precision=0.350  regression_rate=1.00
overall     BLOCK
```

## 3. 判别力扫描（每条阈值只问一个问题：挪动它，level 向量变不变）

| 阈值 | 原值 | 观测跨度 | 翻转点 | 结论 |
| --- | --- | --- | --- | --- |
| `MIN_EDITS` | 5 | 每类恰 10 笔 | 11 / 20 → 全部 `NOT_ASSESSED` → WARN | 有判别力，但是**机械性**的样本量门槛 |
| `REGRESSION_BLOCK_RATE` | 0.30 | 观测只有 0.10 与 1.00 | 仅 0.0 与 1.0 处翻转 | **NO_DISCRIMINATION**：区间 (0.1, 1.0) 内数据不可辨识 |
| `PRECISION_TRUST_FLOOR` | 0.50 | 0.20 ~ 0.75 | 0.2 / 0.9 才翻转，0.35~0.75 全不变 | 低判别力：4 类已被回归率压到 L3，只剩 tool 一名 L1 |
| `PRECISION_BLIND_FLOOR` | 0.20 | 观测最低恰 0.20 | 0.3 / 0.5 只改 `reasons`，`level` 不变 | 无 level 级判别力 |
| `REGRESSION_TRUST_CEIL` | 0.10 | tool 恰为 0.10 | 0.0 / 0.05 把 tool 从 L1 降到 L2，总判仍 BLOCK | 仅 kind 级贴边判别 |

扫描时踩到并修掉一个**装饰性仪器**陷阱：`score_history(rows, min_edits=MIN_EDITS)`
的默认值在 `def` 时绑定，改模块全局不影响它，第一版扫描因此对 `MIN_EDITS`
恒不翻转（假绿）。现在 `calibrate.py` 显式传 `min_edits=trust.MIN_EDITS`，
11 处才真的翻成 WARN。

## 4. 结构发现：regression_rate 实际是"候选级统计穿了 edit 级外衣"

`change_manifest.reconcile()` 对未预测到的回归做 shared blame——同一候选里
所有 edit 一起判 `regression`。实测 20/30 候选内 verdict 完全均一，
于是 regression_rate 只会落在 0.10 或 1.00 两端，中间没有观测值。

后果：`REGRESSION_BLOCK_RATE=0.30` 在这份账本上不可辨识，**但它不是错的**——
这是账本颗粒度不够，不是阈值错了。要让这条阈值真正可校准，账本得先升级：

1. `reconcile()` 在能归因时把回归记到具体 edit（谁改的文件导致的），
   不能归因时才 shared blame，并把两种情形分开打标；
2. 账本同时记 `candidate_regression_rate` 与 `edit_regression_rate`；
3. 用第二个 LLM（不同模型/温度）复跑同一 bench，看 kind 级 L 分布能否复现。

## 5. 判据修正（不是阈值调参）

发现的缺陷（读 `change_manifest.py` 的字段语义时定位，非本账本触发）：

- regression-only 编辑（`predicted_fix` 为空 → `prediction_precision=None`）
  会让 `len(precisions) < n_edits` 恒成立 → 该 kind **永远够不到 L1**。
  这是判据在惩罚诚实：编辑明说"我这次只防回归"，却被判证据不全。

修正（`eval-meta/eval_meta/trust.py` `score_kind`）：

- 覆盖率只覆盖**声称修复或有精度载体**的编辑（`fix_claims`）；
- 没有任何修复声明 → 新增 reason `no_fix_claims`，判 L2（没精度证据不能算可信）；
- regression-only 编辑**照旧计入** `n_edits` 与 `regression_rate`（不能靠不预测修复逃责任）。

证据：`eval-meta/tests/test_precision_carrier.py` 4 条，其中 2 条先 RED
（L1 被堵、`no_fix_claims` 缺失）再 GREEN；`eval-meta` 全套件 73 passed。

诚实边界：本账本 **0 笔** regression-only 编辑，所以这个缺陷不是本次数据触发的，
RED 用的是合成夹具。它属于"读 schema 发现的潜在缺陷"，不是"实测复现的缺陷"。

## 6. 决定

- **五条阈值一个都不改**（PREREG 明令禁止事后调参凑结论）。
- 本记录可引用的结论只有三条：
  1. 阈值在真实 LLM 账本上**能产出三种不同 level**（L1/L2/L3 都出现了），不是退化的；
  2. `REGRESSION_BLOCK_RATE` 与 `PRECISION_BLIND_FLOOR` 在当前账本颗粒度下**没有判别力**，
     引用它们的结论前必须先升级账本；
  3. regression-only 编辑恒堵 L1 是**已修**的判据缺陷，修法有 RED→GREEN 测试。

## 7. 局限

合成 bench（12 条字符串规范化用例）、单模型（`workbuddy/deepseek-v4.1-flash`）、
单温度（0.7）、10 轮、2 轮失败未补。**这是机制 probe，不是科学结论**，
不得被引用为"P4 阈值已经过真实数据验证"，也不得据此改动任何论文数字。

## 8. v2：按口径重扫 + 稠密网格（2026-11-16）

### 8.1 v1 仪器的两处缺陷（先修尺再读数）

| 缺陷 | v1 实际做法 | 后果 | v2 修法 |
| --- | --- | --- | --- |
| 「翻转」定义错 | `changed_vs_baseline`：与基线 `RBR=0.30` 不同就记翻转 | 把「与基线不同」和「跨过数据边界」混为一谈；稀疏网格 `[0,0.1,0.3,0.5,0.9,1.0]` 恰好跳过 0.045 边界，于是 0.1/0.3/0.5 被误判成不可分辨区间 | 按**相邻格点**是否改变 level 向量定边界，稠密网格定位真实边界位置 |
| MIN_EDITS 网格未过样本量 | 最大只扫到 20，而每类实测 32 笔 | 全格点都在样本量之下 → 机械地显示 0 判别力 | 网格扩到 1–50，跨过 32→33 的功效边界 |

这些是 v1 扫描脚本/网格的仪器缺陷，不是账本缺陷；修正后 v1 第 3 节「NO_DISCRIMINATION」结论**不再成立**。

### 8.2 数据与口径

- 账本：`trust-probe-01` + `trust-probe-02-rerun-qwenflash` + `trust-probe-03-rerun-temp05`，合计 96 行 / 192 笔有效编辑，每类 32 笔。
- `candidate_regression_rate` 覆盖：probe-01 为 30 行 **0** 覆盖（旧账本）、probe-02/03 各 33 行全覆盖；合计 66/96 行有候选级率。
- 两种回归率口径（`eval_meta.trust.score_kind(..., regression_basis=...)`）：
  - `edit`：`该类 verdict==regression 的编辑数 / 该类编辑数`（旧口径，受 shared blame 压平）。
  - `candidate`：含该类编辑的行上 `candidate_regression_rate` 的均值；缺该键的行**不计入分母**并打 `candidate_rate_missing`（兼容旧账本，不静默改口径）。

实测 per-kind 读数（合并 96 行）：

| kind | edit_rate | cand_mean（有率 22 行） | p(mean) | L(edit/cand) |
| --- | --- | --- | --- | --- |
| memory | 1.0000 | 1.0000 | 0.250 | L3/L3 |
| middleware | 0.9688 | 1.0000 | 0.604 | L3/L3 |
| prompt | 0.0625 | 0.0455 | 0.063 | L3/L3 |
| subagent | 1.0000 | 1.0000 | 0.328 | L3/L3 |
| tool | 0.0312 | 0.0455 | 0.891 | L1/L1 |
| workflow | 1.0000 | 1.0000 | 0.776 | L3/L3 |

在当前 66 行有候选级率的子集上，`candidate_regression_rate` 取值仅 {0.0, 1.0}（每行/每候选仍是二值）；`edit_regression_rate` 出现了 0.5（2 行混合 verdict），但 `trust.score_kind` 的阈值门控消费的是回归率均值而非混合度。

### 8.3 稠密网格扫描结果（脚本 `calibrate_basis.py`，产物 `calibration_basis.json`）

| 阈值 | 原值 | edit 口径：边界 / distinct | candidate 口径：边界 / distinct | 原值所处区间 |
| --- | --- | --- | --- | --- |
| `MIN_EDITS` | 5 | [33] / 2 | [33] / 2 | (None, 33) |
| `REGRESSION_BLOCK_RATE` | 0.30 | [0.045, 0.999, 1.0] / 4 | [0.05, 1.0] / 3 | (0.045, 0.999) / (0.05, 1.0) |
| `PRECISION_TRUST_FLOOR` | 0.50 | [0.9] / 2 | [0.9] / 2 | (None, 0.9) |
| `PRECISION_BLIND_FLOOR` | 0.20 | [0.1] / 2 | [0.1] / 2 | (0.1, None) |
| `REGRESSION_TRUST_CEIL` | 0.10 | [0.045] / 2 | [0.045] / 2 | (0.045, None) |

逐 campaign 的 RBR 扫描补充：probe-02 在 candidate 口径下出现 `RBR=0.1` 处的额外翻转（tool 从 L3 升 L1，distinct=3）而 edit 口径在该点无翻转（distinct=2），说明**候选级口径在单次复跑上能揭示被 shared blame 掩盖的分级变化**；合并三份账本后该差异被 1.0 类主导而收敛。

### 8.4 结论（可复算、可引用的部分）

1. **五个阈值在稠密网格上均有判别力**（distinct≥2）：v1 的「RBR/PRECISION_BLIND_FLOOR 无判别力」被证伪，成因是稀疏网格+翻转定义错，不是阈值本身退化。
2. **`REGRESSION_BLOCK_RATE=0.30` 仍可保留**：在 edit/candidate 两种口径下都落在宽稳定区间内部（到下边界余量 ≥0.25，到上边界余量 ≥0.7），并非贴边过拟合。
3. **candidate 口径是有意义的独立读数**，但在当前数据上**未翻转任何阈值的原值结论**：它改变了边界结构（尤其 probe-02 单跑），而非改变 `0.30` 这个默认值的可接受性。
4. **真正限制判别力的仍是数据形态**：66 行有候选级率的记录里 `candidate_regression_rate` 只取 0/1，`edit_regression_rate` 仅 2 行出现 0.5，且账本无 per-edit 归因字段（`regression_attribution` 全为 None）。要让 candidate 口径发挥完整判别力，需要把 `reconcile()` 的 per-edit 归因结果真正落入 ledger 行（`verdict_history` 已支持透传，但现有三份账本产于该修复之前且该 bench 的开关作用为全局态、难产生可分离归因）。

### 8.5 决定

- **五条阈值继续保持不变**（`MIN_EDITS=5, REGRESSION_BLOCK_RATE=0.30, PRECISION_TRUST_FLOOR=0.50, PRECISION_BLIND_FLOOR=0.20, REGRESSION_TRUST_CEIL=0.10`）。v2 提供的是「原值落在稳定区间内」的证据，而非「应调参」的证据。
- `eval_meta.trust` 新增 `regression_basis ∈ {edit,candidate}` 参数与 `--regression-basis` CLI，默认仍为 `edit` 以保持旧行为/旧账本兼容；candidate 口径作为可选对照读数保留。
- v1 第 3 节「NO_DISCRIMINATION」与第 4 节「不可辨识」的表述以本节为准（已被 v2 仪器修正推翻）。

## 9. 仍未关闭的缺口（诚实边界）

- 无 per-edit 归因落盘：三份真账本 `regression_attribution` 全空、`candidate_regression_rate` 仅二值 → candidate 口径的"候选内细粒度"优势尚未在数据上兑现。
- probe-01 缺候选级率（30 行）：candidate 口径在合并分析中对这 30 行退化为 edit 口径并标记 `candidate_rate_missing`。
- 单 bench（12 例字符串规范化）、kind 由脚本确定性轮转而非 LLM 真实选择、6 类均为 32 笔；`tool` 稳定 L1 而其余五类高回归率的格局可能反映 bench/开关设计而非通用 kind 性质。
- **仍是机制 probe，不是科学结论**；不得据此改动论文数字。
