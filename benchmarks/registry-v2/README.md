# Benchmark Registry v2（P0）

> 说明：本文件部分中文内容曾在一次编码事故中损坏为 `?`，以下为依据可辨认事实重建的版本；原始私有数据不在本仓库内。

## 数据与产物

- 任务集：`<私有数据目录>/benchmark-registry-v2/tasks.json`
- 答案键：`<私有数据目录>/benchmark-registry-v2/answer-key.json`
- 汇总：`summary.json`

Registry v2 共 360 任务：Development 120、Hidden Confirmation 80、Trigger Safety 60、Shadow 100；模型评测使用其中 45 个。`content_sha256` 固定任务内容，`manifest_sha256` 固定任务清单。

`contamination_checked` 字段为 `false`：任务未与公开基准做过污染比对；私有数据目录（原路径 `E:\self-evolving-agent-private`）不随仓库分发。

## 运行（仓库根目录执行）

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m evoagent.p0_registry --root .
python -m evoagent.p0_evaluation --root .
python -m evoagent.p0_model_evaluation --root . --endpoint http://127.0.0.1:1234/v1
```
