import unittest

from ledger.db import connect, list_transactions
from ledger.rules import add_rule, categorize, set_category


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")

    def tx(self, description, amount=-1000, category=None, source=None):
        cur = self.conn.execute(
            "INSERT INTO transactions (account, date, description, amount, "
            "category, category_source) VALUES ('a', '2024-01-01', ?, ?, ?, ?)",
            (description, amount, category, source))
        self.conn.commit()
        return cur.lastrowid

    def cat(self, tid):
        return self.conn.execute(
            "SELECT category, category_source FROM transactions WHERE id=?",
            (tid,)).fetchone()

    def test_add_rule_validation(self):
        for kwargs in ({}, {"contains": ""}, {"pattern": ""},
                       {"contains": "", "pattern": ""}):
            with self.assertRaises(ValueError):
                add_rule(self.conn, "X", **kwargs)
        with self.assertRaises(ValueError):
            add_rule(self.conn, "X", pattern="(")
        with self.assertRaises(ValueError):
            add_rule(self.conn, "X", contains="a", min_amount=10, max_amount=5)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0], 0)

    def test_add_rule_out_of_range(self):
        big = 2**63
        for kw in ({"priority": big}, {"min_amount": big},
                   {"max_amount": big}, {"priority": -big - 1}):
            with self.assertRaises(ValueError):
                add_rule(self.conn, "X", contains="y", **kw)
        add_rule(self.conn, "X", contains="y", priority=2**63 - 1)

    def test_add_rule_returns_ids(self):
        a = add_rule(self.conn, "X", contains="a")
        b = add_rule(self.conn, "Y", pattern="b", min_amount=5, max_amount=5)
        self.assertEqual((a, b), (1, 2))

    def test_contains_case_insensitive(self):
        t = self.tx("Shell GAS station")
        add_rule(self.conn, "Fuel", contains="gas STATION")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(self.cat(t), ("Fuel", "rule"))

    def test_pattern_case_insensitive_search(self):
        t = self.tx("Payment to NETFLIX.com")
        u = self.tx("Other")
        add_rule(self.conn, "TV", pattern=r"net.?flix")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(self.cat(t)[0], "TV")
        self.assertEqual(self.cat(u), (None, None))

    def test_min_max_inclusive_abs_spending_and_income(self):
        add_rule(self.conn, "Mid", contains="x", min_amount=500,
                 max_amount=1000)
        ids = {a: self.tx("x", a) for a in
               (-499, -500, -1000, -1001, 499, 500, 1000, 1001)}
        categorize(self.conn)
        for a, t in ids.items():
            expected = "Mid" if 500 <= abs(a) <= 1000 else None
            self.assertEqual(self.cat(t)[0], expected, a)

    def test_only_min_or_only_max(self):
        add_rule(self.conn, "Big", contains="x", min_amount=500)
        add_rule(self.conn, "Small", contains="y", max_amount=500)
        big, small = self.tx("x", -500), self.tx("y", 500)
        low, high = self.tx("x", -499), self.tx("y", -501)
        categorize(self.conn)
        self.assertEqual(self.cat(big)[0], "Big")
        self.assertEqual(self.cat(small)[0], "Small")
        self.assertIsNone(self.cat(low)[0])
        self.assertIsNone(self.cat(high)[0])

    def test_all_conditions_must_hold(self):
        add_rule(self.conn, "R", contains="coffee", pattern=r"^big",
                 min_amount=100)
        ok = self.tx("big coffee", -100)
        no_contains = self.tx("big tea", -100)
        no_pattern = self.tx("small coffee", -100)
        no_amount = self.tx("big coffee", -99)
        categorize(self.conn)
        self.assertEqual(self.cat(ok)[0], "R")
        for t in (no_contains, no_pattern, no_amount):
            self.assertIsNone(self.cat(t)[0])

    def test_priority_wins(self):
        add_rule(self.conn, "Low", contains="shop", priority=1)
        add_rule(self.conn, "High", contains="shop", priority=5)
        t = self.tx("shop")
        categorize(self.conn)
        self.assertEqual(self.cat(t)[0], "High")

    def test_tie_lower_id_wins(self):
        add_rule(self.conn, "First", contains="shop")
        add_rule(self.conn, "Second", contains="shop")
        t = self.tx("shop")
        categorize(self.conn)
        self.assertEqual(self.cat(t)[0], "First")

    def test_default_skips_categorized(self):
        t = self.tx("shop")
        add_rule(self.conn, "A", contains="shop")
        categorize(self.conn)
        add_rule(self.conn, "B", contains="shop", priority=9)
        self.assertEqual(categorize(self.conn), 0)
        self.assertEqual(self.cat(t)[0], "A")

    def test_recategorize_recomputes_rule_rows(self):
        t = self.tx("shop")
        add_rule(self.conn, "A", contains="shop")
        categorize(self.conn)
        add_rule(self.conn, "B", contains="shop", priority=9)
        self.assertEqual(categorize(self.conn, recategorize=True), 1)
        self.assertEqual(self.cat(t), ("B", "rule"))

    def test_unmatched_rows_keep_category(self):
        t = self.tx("shop")
        add_rule(self.conn, "A", contains="shop")
        categorize(self.conn)
        self.conn.execute("DELETE FROM rules")
        add_rule(self.conn, "Z", contains="nomatch")
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.cat(t), ("A", "rule"))
        u = self.tx("other")
        categorize(self.conn)
        self.assertEqual(self.cat(u), (None, None))

    def test_manual_survives_recategorize(self):
        t = self.tx("shop")
        set_category(self.conn, t, "Mine")
        add_rule(self.conn, "A", contains="shop")
        self.assertEqual(categorize(self.conn), 0)
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.cat(t), ("Mine", "manual"))

    def test_preexisting_category_with_null_source_is_set(self):
        t = self.tx("shop", category="A")
        add_rule(self.conn, "A", contains="shop")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(self.cat(t), ("A", "rule"))

    def test_second_run_returns_zero(self):
        self.tx("shop")
        self.tx("shop")
        add_rule(self.conn, "A", contains="shop")
        self.assertEqual(categorize(self.conn), 2)
        self.assertEqual(categorize(self.conn), 0)
        self.assertEqual(categorize(self.conn, recategorize=True), 0)

    def test_list_transactions_shows_category(self):
        self.tx("shop")
        add_rule(self.conn, "A", contains="shop")
        categorize(self.conn)
        self.assertEqual(list_transactions(self.conn)[0]["category"], "A")

    def test_set_category_unknown_id(self):
        with self.assertRaises(ValueError):
            set_category(self.conn, 999, "X")

    def test_set_category_overrides_rule(self):
        t = self.tx("shop")
        add_rule(self.conn, "A", contains="shop")
        categorize(self.conn)
        set_category(self.conn, t, "Mine")
        self.assertEqual(self.cat(t), ("Mine", "manual"))


if __name__ == "__main__":
    unittest.main()
