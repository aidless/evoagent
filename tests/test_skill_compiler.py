# P3 技能编译器测试：失败轨迹 → lesson/trigger/evidence/scope 条目 + 预算内 Select。
# 设计来源：arXiv:2608.15071（Evo-Harness）两阶段——执行反思产出候选记忆、
# 批级进化做 Add/Merge/Revise/Skip；两层 harness（general 跨任务 / topic 任务型）。
import unittest

from evoagent.skill_compiler import (
    GuidanceEntry, compile_entries, select_entries, evolve_harness,
)

# 两条失败轨迹：同类失败（除零）重复两次，第三条是任务特有失败（格式解析）
TRAJ_DIVZERO_1 = {
    "trace_id": "t1", "task_type": "arithmetic", "passed": False,
    "failure": "ZeroDivisionError when denominator equals zero",
    "context": {"tool": "calc", "step": "division"},
}
TRAJ_DIVZERO_2 = {
    "trace_id": "t2", "task_type": "arithmetic", "passed": False,
    "failure": "ZeroDivisionError when denominator equals zero",
    "context": {"tool": "calc", "step": "division"},
}
TRAJ_FORMAT = {
    "trace_id": "t3", "task_type": "parsing", "passed": False,
    "failure": "Answer parser rejected trailing percent sign",
    "context": {"tool": "parser", "step": "extract"},
}
TRAJ_OK = {
    "trace_id": "t4", "task_type": "arithmetic", "passed": True,
    "failure": "", "context": {},
}


class CompileTests(unittest.TestCase):
    def test_only_failures_compiled(self):
        # GREEN：通过的轨迹不产条目（Evo-Harness：只反思失败）
        entries = compile_entries((TRAJ_OK, TRAJ_FORMAT))
        self.assertEqual(len(entries), 1)
        self.assertIn("percent", entries[0].lesson)

    def test_repeated_failure_merged_with_count(self):
        # GREEN：同类失败合并成一条，evidence 记次数（过滤噪声/冗余）
        entries = compile_entries((TRAJ_DIVZERO_1, TRAJ_DIVZERO_2, TRAJ_FORMAT))
        div = [e for e in entries if "ZeroDivision" in e.lesson]
        self.assertEqual(len(div), 1)
        self.assertEqual(div[0].support, 2)
        self.assertEqual(div[0].trace_ids, ("t1", "t2"))

    def test_layering_general_vs_topic(self):
        # GREEN：跨任务类型复现的失败进 general 层；单任务类型的进 topic 层
        entries = compile_entries((TRAJ_DIVZERO_1, TRAJ_DIVZERO_2, TRAJ_FORMAT))
        div = next(e for e in entries if "ZeroDivision" in e.lesson)
        fmt = next(e for e in entries if "percent" in e.lesson)
        self.assertEqual(div.layer, "general")
        self.assertEqual(fmt.layer, "topic")
        self.assertEqual(fmt.task_type, "parsing")

    def test_entry_has_all_four_fields(self):
        # GREEN：条目四要素齐全（lesson/trigger/evidence/scope）
        e = compile_entries((TRAJ_FORMAT,))[0]
        self.assertTrue(e.lesson and e.trigger and e.scope)
        self.assertEqual(e.evidence[0]["trace_id"], "t3")

    def test_empty_input(self):
        self.assertEqual(compile_entries(()), [])


class SelectTests(unittest.TestCase):
    def setUp(self):
        self.entries = compile_entries((TRAJ_DIVZERO_1, TRAJ_DIVZERO_2, TRAJ_FORMAT))

    def test_budget_respected(self):
        # GREEN：注入预算按字符数硬性截断——实测 ZeroDivision 条目 cost=122、
        # percent 条目 cost=114，故预算 130 只放得下一条，预算 60 一条都放不下
        picked = select_entries("division by zero in calc", self.entries, budget_chars=130)
        used = sum(e.cost() for e in picked)
        self.assertEqual(len(picked), 1)
        self.assertLessEqual(used, 130)
        self.assertEqual(select_entries("division by zero in calc", self.entries, 60), [])

    def test_relevance_ranking(self):
        # GREEN：任务文本命中 trigger 的条目优先
        picked = select_entries("division by zero in calc", self.entries, budget_chars=200)
        self.assertIn("ZeroDivision", picked[0].lesson)

    def test_zero_budget_returns_empty(self):
        self.assertEqual(select_entries("anything", self.entries, budget_chars=0), [])


class EvolveHarnessTests(unittest.TestCase):
    def test_add_new_entry(self):
        # GREEN：新失败 → Add
        batch = compile_entries((TRAJ_DIVZERO_1,))
        result = evolve_harness((), batch)
        self.assertEqual(result["operations"][0]["op"], "add")
        self.assertEqual(len(result["harness"]), 1)

    def test_revise_existing_on_new_evidence(self):
        # GREEN：已有同主题条目 + 新证据 → Revise（support 累加），不重复 Add
        first = evolve_harness((), compile_entries((TRAJ_DIVZERO_1,)))
        second = evolve_harness(first["harness"], compile_entries((TRAJ_DIVZERO_2,)))
        ops = [o["op"] for o in second["operations"]]
        self.assertEqual(ops, ["revise"])
        self.assertEqual(len(second["harness"]), 1)
        self.assertEqual(second["harness"][0].support, 2)

    def test_revise_promotes_to_general(self):
        # GREEN：Revise 把 support 推到 2 时，层必须同步升 general——
        # 分层口径只在 compile 里算会让同一条教训出现两套层，下游读到不一致
        first = evolve_harness((), compile_entries((TRAJ_DIVZERO_1,)))
        self.assertEqual(first["harness"][0].layer, "topic")
        second = evolve_harness(first["harness"], compile_entries((TRAJ_DIVZERO_2,)))
        self.assertEqual(second["harness"][0].support, 2)
        self.assertEqual(second["harness"][0].layer, "general")
        self.assertEqual(second["harness"][0].task_type, "")

    def test_skip_low_signal(self):
        # RED 对照：无失败批次 → Skip，harness 原样
        first = evolve_harness((), compile_entries((TRAJ_DIVZERO_1,)))
        result = evolve_harness(first["harness"], ())
        self.assertEqual(result["operations"], [{"op": "skip", "reason": "no_candidates"}])
        self.assertEqual(len(result["harness"]), 1)


if __name__ == "__main__":
    unittest.main()