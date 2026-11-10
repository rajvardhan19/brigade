from ledger.budgets import monthly_report, set_budget
from ledger.rules import set_category
from tests.helpers import TempDirTestCase


class BudgetTests(TempDirTestCase):
    def test_report(self):
        a = self.add_tx("2024-03-01", "Market", -5000)
        b = self.add_tx("2024-03-15", "Market", -2500, account="card")
        c = self.add_tx("2024-03-20", "Diner", -3000)
        self.add_tx("2024-03-21", "Mystery", -100)
        self.add_tx("2024-03-25", "Salary", 500000)
        d = self.add_tx("2024-04-01", "Market", -9999)
        r = self.add_tx("2024-03-26", "Refund", 1000)
        for t in (a, b, d, r):
            set_category(self.conn, t, "Groceries")
        set_category(self.conn, c, "Dining")
        set_budget(self.conn, "Groceries", "2024-03", 10000)
        set_budget(self.conn, "Dining", "2024-03", 2000)
        set_budget(self.conn, "Travel", "2024-03", 50000)
        set_budget(self.conn, "Travel", "2024-04", 1)

        self.assertEqual(monthly_report(self.conn, "2024-03"), [
            {"category": "Dining", "spent": 3000, "budget": 2000,
             "remaining": -1000, "over": True},
            {"category": "Groceries", "spent": 7500, "budget": 10000,
             "remaining": 2500, "over": False},
            {"category": "Travel", "spent": 0, "budget": 50000,
             "remaining": 50000, "over": False},
            {"category": "Uncategorized", "spent": 100, "budget": None,
             "remaining": None, "over": False},
        ])

    def test_set_budget_replaces(self):
        set_budget(self.conn, "Food", "2024-01", 100)
        set_budget(self.conn, "Food", "2024-01", 200)
        self.assertEqual(monthly_report(self.conn, "2024-01")[0]["budget"], 200)

    def test_exactly_at_budget_is_not_over(self):
        t = self.add_tx("2024-01-02", "X", -200)
        set_category(self.conn, t, "Food")
        set_budget(self.conn, "Food", "2024-01", 200)
        row = monthly_report(self.conn, "2024-01")[0]
        self.assertEqual((row["remaining"], row["over"]), (0, False))

    def test_empty_month(self):
        self.assertEqual(monthly_report(self.conn, "2024-01"), [])

    def test_bad_month(self):
        for bad in ("2024-1", "2024-13", "January", "2024-01-01"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    set_budget(self.conn, "Food", bad, 100)
                with self.assertRaises(ValueError):
                    monthly_report(self.conn, bad)
