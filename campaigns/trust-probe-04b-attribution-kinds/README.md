# trust-probe-04b-attribution-kinds（1 edit/candidate × 6 类 kind 全覆盖）

预注册见 [PREREG.md](PREREG.md)，运行卡 [RUN_CARD.md](RUN_CARD.md)。
前身 [../trust-probe-04-attribution/](../trust-probe-04-attribution/)——那份账本因 kind 轮转公式
（`(round*6+j)%6` ≡ `j%6`）只覆盖 3 类，只兑现了「归因字段落盘」，本目录补上 6 类全覆盖。

## 唯一变量
`kind_for(round_no, candidate_index) = KINDS[(round_no*3 + candidate_index) % 6]` →
12 轮 × 3 候选 = 36 笔，**6 类各 6 笔**。反证：
[`evoagent/tests/test_campaign_proposer_kind_rotation.py`](../../tests/test_campaign_proposer_kind_rotation.py)
的 `test_old_rotation_formula_would_fail_this_assertion`（旧公式算出来只有 3 类，主断言必红）。

## 不变量（与 probe-04 相同）
每候选恰 1 笔 edit；同 bench c01..c12；6 开关；seed 全关；`min_gain 2.0` 禁晋升；
statistical_gate 关；模型 `workbuddy/deepseek-v4.1-flash` T=0.7；12 轮；
幻觉 id 丢弃、失败不编造；detached + checkpoint。

## 结果
见 [campaign_report.json](campaign_report.json) 与 [verdicts.jsonl](verdicts.jsonl)（本目录内为实跑产物）。

## 复现
```bash
cd evoagent/campaigns/trust-probe-04b-attribution-kinds
PYTHONPATH=../../src nohup /usr/bin/python3 run_campaign.py --rounds 12 > campaign.stdout.txt 2> campaign.stderr.txt &
```

## 消费
```bash
cd /home/liuzewen/F:\deepseek
PYTHONPATH=eval-meta /usr/bin/python3 -m eval_meta.trust \
  evoagent/campaigns/trust-probe-04b-attribution-kinds/verdicts.jsonl --regression-basis candidate
```
机制 probe，非科学结论。
