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
