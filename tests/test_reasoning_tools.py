import unittest
from evoagent.reasoning_tools import solve_date,solve_logic
class ToolTests(unittest.TestCase):
 def test_date_month_boundary(self):
  q='''Yesterday was April 30, 2021. What is the date a month ago in MM/DD/YYYY?\nOptions:\n(A) 04/01/2094\n(B) 03/22/2021\n(C) 03/18/2021\n(D) 03/31/2021\n(E) 04/01/2021\n(F) 02/21/2021''';self.assertEqual(solve_date(q),'E')
 def test_logic_price(self):
  q='''A fruit stand sells five fruits: mangoes, cantaloupes, plums, oranges, and watermelons. The oranges are more expensive than the watermelons. The watermelons are the second-cheapest. The plums are less expensive than the cantaloupes. The plums are the second-most expensive.\nOptions:\n(A) The mangoes are the third-most expensive\n(B) The cantaloupes are the third-most expensive\n(C) The plums are the third-most expensive\n(D) The oranges are the third-most expensive\n(E) The watermelons are the third-most expensive''';self.assertEqual(solve_logic(q),'D')
if __name__=='__main__':unittest.main()
