# 开源模型与 Agent 技术资料观察（2026-07-24）

## 范围

本次下载并本地保存了 12 个代表性项目的 README/技术入口，而非盲目克隆 100 个完整仓库。清单与原始 URL 见 `manifest.json`，原文见 `sources/`。这些资料足以为当前最小闭环做第一轮架构校准；若进入具体实现，再按需浅克隆相关仓库和固定 commit。

## 关键发现

1. **优化对象应当模块化，而不只是整段提示词。** DSPy 把 LM 应用视为可编程模块，并自动优化指令与示例。EvoAgent 下一步应把候选拆成 system prompt、demonstrations、tool policy、memory policy、retry policy 等独立基因。
2. **推理与非推理模式需要分开评测。** Qwen3 强调 thinking/non-thinking 与工具使用；DeepSeek-V3 描述了推理蒸馏和 reflection pattern。一个候选不应对所有任务强制使用长推理，应由路由策略按任务难度选择。
3. **Agent 能力必须以真实环境轨迹评测。** OpenHands、SWE-agent、LangGraph、AutoGen 都强调工具、状态、工作流或多 Agent 编排。仅比较最终字符串不足以测量工具选择、步骤数、恢复能力和副作用。
4. **性能目标必须多维。** vLLM、llama.cpp 和各模型说明反复涉及吞吐、显存、量化和推理效率。因此晋升不应只看正确率，还应同时约束延迟、token、费用、显存和失败率。
5. **模型后端应可替换。** Llama、Mistral、GLM、Qwen、DeepSeek 的部署协议和能力不同。进化控制器应通过统一 adapter 接 OpenAI-compatible、本地 llama.cpp/vLLM 和自定义命令，而不绑定单模型。
6. **平台期不能靠重复评测突破。** 当前十轮中基线与所有候选均为 1.0。继续用相同基准、相同 mutation 只会浪费算力。应加入候选去重、patience、动态任务课程和隐藏回归集。
7. **迁移和维护状态本身也是风险信号。** AutoGen README 已提示新用户转向 Microsoft Agent Framework；SWE-agent README 提示主要开发转向 mini-swe-agent。采用外部框架前必须检查维护状态，不能只看历史知名度。

## 对 EvoAgent 的近期设计决策

- 保留“配置进化优先、代码自改写后置”的边界。
- 引入 train/dev/hidden-test 三层任务集，只有 hidden-test 通过才能晋升。
- 采用多目标门控：质量不得退化，同时限制 p95 延迟、成本、工具错误和副作用。
- 候选保存 provenance：父版本、提案器、模型、随机种子、失败簇、评测集哈希。
- 对候选做内容哈希去重；连续 N 轮无提升自动停止并报告平台期。
- 将动态提案器设计成 adapter，优先支持本地 OpenAI-compatible endpoint。
- 真实代码进化必须在 Git worktree/容器中执行，并要求测试、静态分析和人工批准。

## 十轮实验结论

十轮均从活动分数 1.0 开始，最佳候选仍为 1.0，`min_gain=0.01` 因而拒绝全部晋升。活动 ID 始终为 `f8a196f466db`。这不是十次能力提升，而是一次有价值的收敛测试：系统没有把等价候选误报为进步；同时证明下一步必须扩大任务分布和候选空间。
