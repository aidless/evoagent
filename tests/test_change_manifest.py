# change_manifest 单元测试（AHE 式 per-edit 预测-对账-回滚）
# 每条断言先有"违规必须红"的对照，再有"合规必须绿"的正例（RED→GREEN）。
import unittest
from evoagent.change_manifest import (
    ChangeEdit, validate_edit, reconcile, build_rollback_plan,
)
from evoagent.protocol import Outcome, Run


def make_run(run_id: str, passed_ids, failed_ids, candidate_id="cand"):
    """构造一个 Run：passed_ids 里的任务通过，failed_ids 里的任务失败。"""
    outcomes = [Outcome(task_id=t, passed=True, score=1.0) for t in passed_ids] + \
               [Outcome(task_id=t, passed=False, score=0.0) for t in failed_ids]
    return Run(run_id=run_id, candidate_id=candidate_id,
               task_set_hash="fixed", outcomes=tuple(outcomes))


def make_edits(**overrides):
    """默认一对编辑：e1 预测修好 t2，e2 预测修好 t3 且 t4 有回归风险。"""
    e1 = ChangeEdit(edit_id="e1", kind="tool",
                    target_files=("tools/normalize.py",),
                    predicted_fix=("t2",), predicted_regression=(),
                    rationale="修归一化")
    e2 = ChangeEdit(edit_id="e2", kind="prompt",
                    target_files=("prompts/system.md",),
                    predicted_fix=("t3",), predicted_regression=("t4",),
                    rationale="收紧指令")
    if overrides:
        e1 = overrides.get("e1", e1)
        e2 = overrides.get("e2", e2)
    return (e1, e2)


class ValidateEditTests(unittest.TestCase):
    def test_valid_edit_passes(self):
        # GREEN：合规编辑零违规
        self.assertEqual(validate_edit(make_edits()[0]), [])

    def test_empty_prediction_rejected(self):
        # RED：AHE 纪律——每次 edit 必须自声明预测，两个预测都空 = 违规
        bad = ChangeEdit(edit_id="e1", kind="tool",
                         target_files=("a.py",),
                         predicted_fix=(), predicted_regression=())
        self.assertIn("empty_prediction", validate_edit(bad))

    def test_missing_target_files_rejected(self):
        # RED：没有触碰文件的编辑无法回滚
        bad = ChangeEdit(edit_id="e1", kind="tool", target_files=(),
                         predicted_fix=("t1",), predicted_regression=())
        self.assertIn("missing_target_files", validate_edit(bad))


class ReconcileTests(unittest.TestCase):
    def test_effective_fix(self):
        # GREEN：e1 预测修好 t2，t2 确实 fail→pass
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t2", "t4"), failed_ids=("t3",))
        r = reconcile(base, cand, make_edits())
        self.assertEqual(r["edits"]["e1"]["verdict"], "effective_fix")
        self.assertAlmostEqual(r["edits"]["e1"]["prediction_precision"], 1.0)

    def test_no_effect(self):
        # GREEN：预测没兑现 → no_effect（AHE：大多数 edit 的归宿）
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        r = reconcile(base, cand, make_edits())
        self.assertEqual(r["edits"]["e1"]["verdict"], "no_effect")

    def test_anticipated_regression(self):
        # GREEN：预测到的回归出现了，verdict=regression 且计入 anticipated
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t2", "t3"),
                        failed_ids=("t4",))  # t4 被 e2 预测有风险且真的挂了
        r = reconcile(base, cand, make_edits())
        self.assertEqual(r["edits"]["e2"]["verdict"], "regression")
        self.assertEqual(r["edits"]["e2"]["anticipated_regressions"], ["t4"])

    def test_unanticipated_regression_is_visible(self):
        # RED 对照 AHE 回归盲区：没预测到的回归必须被单独计数，不能静默
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t2", "t3"),
                        failed_ids=("t4",))
        edits = make_edits(e2=ChangeEdit(
            edit_id="e2", kind="prompt", target_files=("prompts/system.md",),
            predicted_fix=("t3",), predicted_regression=()))
        r = reconcile(base, cand, edits)
        self.assertEqual(r["edits"]["e2"]["verdict"], "regression")
        self.assertEqual(r["edits"]["e2"]["unanticipated_regressions"], ["t4"])

    def test_task_set_mismatch_fail_closed(self):
        # RED：任务集不一致时绝不产出 verdict（fail-closed，对齐 promotion_gate）
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t5"), failed_ids=("t2",))
        r = reconcile(base, cand, make_edits())
        self.assertFalse(r["valid"])
        self.assertIn("task_set_mismatch", r["reasons"])

    def test_unknown_predicted_case_rejected(self):
        # RED：预测引用不存在的任务 id = 幻觉预测，该 edit 判 invalid
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        edits = make_edits(e1=ChangeEdit(
            edit_id="e1", kind="tool", target_files=("a.py",),
            predicted_fix=("t999",), predicted_regression=()))
        r = reconcile(base, cand, edits)
        self.assertEqual(r["edits"]["e1"]["verdict"], "invalid_prediction")

    def test_campaign_level_metrics(self):
        # GREEN：聚合 fix 预测 precision/recall（对齐 AHE 报的 campaign 级指标）
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t2", "t4"), failed_ids=("t3",))
        r = reconcile(base, cand, make_edits())
        # e1 预测 {t2} 命中；e2 预测 {t3} 未命中 → precision=1/2
        self.assertAlmostEqual(r["campaign"]["prediction_precision"], 0.5)


class RollbackPlanTests(unittest.TestCase):
    def test_regression_edit_rolled_back_with_files(self):
        # GREEN：regression 编辑进 rollback，files 逐字带上；effective_fix 保留
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t2", "t3"), failed_ids=("t4",))
        r = reconcile(base, cand, make_edits())
        plan = build_rollback_plan(r)
        self.assertEqual([e["edit_id"] for e in plan["rollback"]], ["e2"])
        self.assertEqual(plan["rollback"][0]["files"], ("prompts/system.md",))
        self.assertIn("e1", plan["keep"])

    def test_no_effect_opt_in_rollback(self):
        # GREEN：no_effect 默认保留，include_no_effect=True 时回滚（对齐 AHE 无效即回滚）
        base = make_run("base", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        cand = make_run("cand", passed_ids=("t1", "t4"), failed_ids=("t2", "t3"))
        r = reconcile(base, cand, make_edits())
        self.assertEqual(build_rollback_plan(r)["rollback"], [])
        plan = build_rollback_plan(r, include_no_effect=True)
        self.assertEqual(len(plan["rollback"]), 2)


if __name__ == "__main__":
    unittest.main()
