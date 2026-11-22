"""grade() 的解析口径护栏：显式 Answer 标记优先于位置型末位抓取。

背景（L-ops-897）：合成能力任务上 last_int 口径判 DPO GAIN +0.1333，
换成显式 Answer 口径翻成 REGRESSION −0.1667。根因是位置型解析器把
"Answer: 42 后续写 Step: 42+1=43" 判成错——输出形状一变，判决就翻。

grade() 在 evoagent/src/evoagent/intelligence.py:30 有同一假设：
  nums[-1] / options[-1]
本文件先钉住四种会红的形状，再钉住必须保持绿的回退路径，最后放
一个变异反证（把实现换回旧的末位抓取，断言必须红），保证这不是装饰。

两向定义：
  红向 = 显式标记与续写/干扰数字冲突时，旧实现会误判；
  绿向 = 无显式标记时保留旧行为，不把历史分数全部推倒重算。
"""
import re
import unittest

from evoagent.intelligence import grade


class GradeAnswerMarkerTest(unittest.TestCase):
    # ---- 红向：显式 Answer 标记必须权威，不能被后文续写翻掉 ----

    def test_gsm8k_explicit_answer_beats_trailing_step_arithmetic(self):
        # "Answer: 42" 之后续写 "42 + 1 = 43"；末位数字是 43，正确答案是 42。
        out = "Answer: 42\n\nStep: 42 + 1 = 43"
        self.assertTrue(grade("gsm8k", out, "42"))

    def test_gsm8k_explicit_answer_beats_trailing_sentence_number(self):
        out = "Work ...\nFinal total: 41.\nAnswer: 42\nNote: checked twice, 2 steps."
        self.assertTrue(grade("gsm8k", out, "42"))

    def test_mcq_explicit_answer_beats_later_option_mentions(self):
        # 显式给 (B)，后文把 (A)/(C) 当干扰项复述；末位 option 是 C。
        out = "Answer: (B). Options (A) and (C) are clearly wrong."
        self.assertTrue(grade("logic", out, "B"))

    def test_mcq_explicit_wrong_answer_is_still_wrong_even_if_later_mention_matches(self):
        # 反向：显式 (C) 是错的，后文才提到 (B)。标记权威 → 必须判错。
        out = "Answer: (C). Actually (B) was the one."
        self.assertFalse(grade("logic", out, "B"))

    # ---- 绿向：没有显式标记时保留历史末位行为 ----

    def test_gsm8k_bare_number_still_passes(self):
        self.assertTrue(grade("gsm8k", "42", "42"))

    def test_gsm8k_bare_wrong_number_still_fails(self):
        self.assertFalse(grade("gsm8k", "41", "42"))

    def test_mcq_bare_option_still_passes(self):
        self.assertTrue(grade("logic", "(B)", "B"))

    def test_mcq_bare_wrong_option_still_fails(self):
        self.assertFalse(grade("logic", "(A)", "B"))

    # ---- 变异反证：把实现换回旧末位抓取，红向断言必须红 ----

    def test_mutation_would_turn_red(self):
        NUM = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
        OPT = re.compile(r"(?:\(|\b)([A-G])\)")

        def old_grade(suite, output, expected):
            if suite == "gsm8k":
                nums = NUM.findall(output)
                return bool(nums) and nums[-1].replace(",", "") == expected
            options = OPT.findall(output.upper())
            return bool(options) and options[-1] == expected.upper()

        # 旧实现在这两个形状上必须失败，否则红向断言测的是装饰。
        self.assertFalse(old_grade("gsm8k", "Answer: 42\n\nStep: 42 + 1 = 43", "42"))
        self.assertFalse(old_grade("logic", "Answer: (B). Options (A) and (C) are clearly wrong.", "B"))
        # 而新实现必须放行同样两例（与上面红向断言同输入，逐字一致）。
        self.assertTrue(grade("gsm8k", "Answer: 42\n\nStep: 42 + 1 = 43", "42"))
        self.assertTrue(grade("logic", "Answer: (B). Options (A) and (C) are clearly wrong.", "B"))


if __name__ == "__main__":
    unittest.main()
