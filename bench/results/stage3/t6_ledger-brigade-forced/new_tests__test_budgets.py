import unittest

from ledger.budgets import monthly_report, set_budget
from ledger.db import connect


class BudgetsTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")

    def tx(self, date, amount, category=None, account="a"):
        self.conn.execute(
            "INSERT INTO transactions (account, date, description, amount, category) "
            "VALUES (?, ?, 'x', ?, ?)",
            (account, date, amount, category),
        )

    def test_budget_replace(self):
        set_budget(self.conn, "Food", "2024-03", 1000)
        set_budget(self.conn, "Food", "2024-03", 2000)
        rows = monthly_report(self.conn, "2024-03")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["budget"], 2000)

    def test_month_validation(self):
        for bad in ["2024-13", "2024-00", "2024-3", "24-03", "2024-03-01", "", "2024-03\n", None]:
            with self.assertRaises(ValueError):
                set_budget(self.conn, "Food", bad, 1)
            with self.assertRaises(ValueError):
                monthly_report(self.conn, bad)

    def test_amount_out_of_range(self):
        with self.assertRaises(ValueError):
            set_budget(self.conn, "Food", "2024-01", 2**63)
        set_budget(self.conn, "Food", "2024-01", 2**63 - 1)

    def test_amount_validation(self):
        for bad in [-1, 1.5, "10", True, None]:
            with self.assertRaises(ValueError):
                set_budget(self.conn, "Food", "2024-03", bad)
        set_budget(self.conn, "Food", "2024-03", 0)

    def test_ignores_income_and_other_months(self):
        self.tx("2024-03-01", -100, "Food")
        self.tx("2024-03-31", -200, "Food")
        self.tx("2024-04-01", -400, "Food")
        self.tx("2024-02-29", -800, "Food")
        self.tx("2024-03-15", 5000, "Food")
        self.tx("2024-03-15", 5000, "Salary")
        rows = monthly_report(self.conn, "2024-03")
        self.assertEqual([r["category"] for r in rows], ["Food"])
        self.assertEqual(rows[0]["spent"], 300)

    def test_sums_across_accounts(self):
        self.tx("2024-03-05", -100, "Food", "a")
        self.tx("2024-03-06", -250, "Food", "b")
        self.assertEqual(monthly_report(self.conn, "2024-03")[0]["spent"], 350)

    def test_uncategorized(self):
        self.tx("2024-03-05", -100)
        self.tx("2024-03-06", -50, "Uncategorized")
        rows = monthly_report(self.conn, "2024-03")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "Uncategorized")
        self.assertEqual(rows[0]["spent"], 150)
        set_budget(self.conn, "Uncategorized", "2024-03", 200)
        rows = monthly_report(self.conn, "2024-03")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["remaining"], 50)

    def test_budget_without_spending(self):
        set_budget(self.conn, "Fun", "2024-03", 500)
        self.assertEqual(
            monthly_report(self.conn, "2024-03"),
            [{"category": "Fun", "spent": 0, "budget": 500, "remaining": 500, "over": False}],
        )

    def test_budget_other_month_not_shown(self):
        set_budget(self.conn, "Fun", "2024-04", 500)
        self.assertEqual(monthly_report(self.conn, "2024-03"), [])

    def test_overspent(self):
        self.tx("2024-03-05", -1500, "Food")
        set_budget(self.conn, "Food", "2024-03", 1000)
        row = monthly_report(self.conn, "2024-03")[0]
        self.assertEqual(row["remaining"], -500)
        self.assertIs(row["over"], True)

    def test_equal_not_over(self):
        self.tx("2024-03-05", -1000, "Food")
        set_budget(self.conn, "Food", "2024-03", 1000)
        row = monthly_report(self.conn, "2024-03")[0]
        self.assertEqual(row["remaining"], 0)
        self.assertIs(row["over"], False)

    def test_no_budget(self):
        self.tx("2024-03-05", -1000, "Food")
        row = monthly_report(self.conn, "2024-03")[0]
        self.assertIsNone(row["budget"])
        self.assertIsNone(row["remaining"])
        self.assertIs(row["over"], False)

    def test_sort_order(self):
        self.tx("2024-03-05", -1, "Zed")
        self.tx("2024-03-05", -1, "apple")
        self.tx("2024-03-05", -1)
        set_budget(self.conn, "Mid", "2024-03", 5)
        names = [r["category"] for r in monthly_report(self.conn, "2024-03")]
        self.assertEqual(names, sorted(names))
        self.assertEqual(names, ["Mid", "Uncategorized", "Zed", "apple"])

    def test_exact_keys_and_int_types(self):
        self.tx("2024-03-05", -1, "Food")
        row = monthly_report(self.conn, "2024-03")[0]
        self.assertEqual(set(row), {"category", "spent", "budget", "remaining", "over"})
        self.assertIs(type(row["spent"]), int)


if __name__ == "__main__":
    unittest.main()
