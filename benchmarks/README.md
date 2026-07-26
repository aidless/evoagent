# 外部智能基准

题目来自公开、独立维护的数据集，原始文件和 SHA-256 记录在 `sources.json`。

- GSM8K：数学文字题。
- BIG-Bench Hard `date_understanding`：日期推理。
- BIG-Bench Hard `logical_deduction_five_objects`：逻辑演绎。
- HumanEval：已冻结原始题库，但第一版不自动执行生成代码，避免在无沙箱环境运行不可信代码。

默认从每个可执行题库固定抽取 20 题，共 60 题；随机种子固定为 `20260724`。评分器使用 temperature=0，并保存逐题输出。候选提案器不读取这些题目。

```powershell
$env:PYTHONPATH='E:\self-evolving-agent\src'
$env:EVO_MODEL_ENDPOINT='http://127.0.0.1:1234/v1'
$env:EVO_MODEL='your-loaded-model'
python -m evoagent.intelligence --root E:\self-evolving-agent
```

模型服务不可达时返回 `verified:false` 和非零退出码，不生成虚假分数。正式晋升应要求新候选在同一冻结集上高于基线，并在另一份隐藏集上不退化。
