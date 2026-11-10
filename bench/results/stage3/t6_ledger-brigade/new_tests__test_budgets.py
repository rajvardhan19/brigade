from helpers import LedgerTestCase

from ledger.budgets import monthly_report, set_budget
from ledger.rules import set_category


class BudgetTests(LedgerTestCase):
    def test_report(self):
        a = self.add_tx("2024-03-01", "Market", -4000, account="a")
        b = self.add_tx("2024-03-20", "Market 2", -2000, account="b")
        c = self.add_tx("2024-03-05", "Movie", -1500)
        self.add_tx("2024-03-06", "Mystery", -700)
        self.add_tx("2024-03-07", "Salary", 500000)
        d = self.add_tx("2024-04-01", "Market April", -9999)
        for tx in (a, b, d):
            set_category(self.conn, tx, "Food")
        set_category(self.conn, c, "Fun")
        set_budget(self.conn, "Food", "2024-03", 5000)
        set_budget(self.conn, "Fun", "2024-03", 2000)
        set_budget(self.conn, "Rent", "2024-03", 100000)
        set_budget(self.conn, "Fun", "2024-04", 1)
        self.assertEqual(monthly_report(self.conn, "2024-03"), [
            {"category": "Food", "spent": 6000, "budget": 5000, "remaining": -1000, "over": True},
            {"category": "Fun", "spent": 1500, "budget": 2000, "remaining": 500, "over": False},
            {"category": "Rent", "spent": 0, "budget": 100000, "remaining": 100000, "over": False},
            {"category": "Uncategorized", "spent": 700, "budget": None, "remaining": None,
             "over": False},
        ])

    def test_set_budget_replaces(self):
        set_budget(self.conn, "Food", "2024-03", 5000)
        set_budget(self.conn, "Food", "2024-03", 7000)
        self.assertEqual(monthly_report(self.conn, "2024-03")[0]["budget"], 7000)

    def test_exactly_at_budget_not_over(self):
        tx = self.add_tx("2024-03-01", "X", -5000)
        set_category(self.conn, tx, "Food")
        set_budget(self.conn, "Food", "2024-03", 5000)
        row = monthly_report(self.conn, "2024-03")[0]
        self.assertEqual((row["remaining"], row["over"]), (0, False))

    def test_income_only_month_is_empty(self):
        self.add_tx("2024-03-01", "Salary", 1000)
        self.assertEqual(monthly_report(self.conn, "2024-03"), [])

    def test_bad_month(self):
        for m in ("2024-3", "2024-13", "March"):
            with self.assertRaises(ValueError):
                set_budget(self.conn, "Food", m, 1)
            with self.assertRaises(ValueError):
                monthly_report(self.conn, m)
