# trust-probe-01 复现指引

先读 [PREREG.md](PREREG.md)。这是一份**机制 probe**，不是科学结论。

## 一次跑完

```bash
cd evoagent/campaigns/trust-probe-01
EVOAGENT=../../src
PYTHONPATH=$EVOAGENT /usr/bin/python3 run_campaign.py --rounds 12
```

断点续跑（读 `checkpoint.json`，跳过已完成轮次）：

```bash
PYTHONPATH=$EVOAGENT /usr/bin/python3 run_campaign.py --rounds 12 --resume
```

## 前置条件

- Magpie 网关在本机 `127.0.0.1:3425` 可用（`curl http://127.0.0.1:3425/v1/models`）。
  模型用 `workbuddy/deepseek-v4.1-flash`，可被 `MAGPIE_URL` / `MAGPIE_MODEL` 覆盖。
- 零训练、零 GPU。12 轮的耗时主要花在 12 次 LLM 调用上。

## 文件职责

| 文件 | 作用 |
| --- | --- |
| `benchmark.json` | 12 条确定性字符串规范化用例（自造，非别线冻结证据） |
| `evaluator.py` | 6 个开关按固定顺序作用到输入，与 expected 比较 |
| `seed.json` | 初始 harness：6 个开关全关 |
| `evo.json` | `min_gain: 2.0` → 12 轮永不晋升；关 statistical_gate；不配 intelligence command |
| `proposer.py` | 真 LLM 产出 predicted_fix / predicted_regression / rationale；过滤幻觉 id |
| `run_campaign.py` | 12 轮编排 + checkpoint + 拷出账本 |
| `verdicts.jsonl` | 真账本（append-only，从 `.evo/verdicts.jsonl` 拷出） |
| `checkpoint.json` | 断点状态与逐轮摘要 |
| `campaign_report.json` | 终态：墙钟、失败轮、按 kind 的编辑计数 |

## 数据真实性边界

- **真**：每笔编辑的 `predicted_fix` / `predicted_regression` / `rationale` 来自 Magpie LLM；
  per-edit 的 `hits` / `prediction_precision` / `verdict` 由 `change_manifest.reconcile()`
  对照确定性 bench 的真实翻转算出。
- **确定性分配**：`edit_id` / `kind` / `target_files` 由 proposer 按轮次分配，
  保证 6 类 kind 覆盖均衡（分类元数据不是被预测的对象）。
- **不编造**：LLM 失败、超时、JSON 解析失败 → 该轮输出空候选并记 `failed_rounds`。
- 引用了不存在任务 id 的 edit 在入账前直接丢弃（`change_manifest.py:97-101` 的
  `invalid_prediction` 分支不写 kind，会让 trust.py 归进 `unknown` 类污染账本）。

## 消费方

```bash
# P4 阈值复核（在 eval-meta 仓库）
PYTHONPATH=eval-meta /usr/bin/python3 -m eval_meta.trust \
  evoagent/campaigns/trust-probe-01/verdicts.jsonl
```
