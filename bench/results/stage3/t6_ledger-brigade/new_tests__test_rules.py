from helpers import LedgerTestCase

from ledger import db
from ledger.rules import add_rule, categorize, set_category


class RuleTests(LedgerTestCase):
    def cats(self):
        return {t["description"]: t["category"] for t in db.list_transactions(self.conn)}

    def test_add_rule_requires_condition(self):
        with self.assertRaises(ValueError):
            add_rule(self.conn, "Food")
        with self.assertRaises(ValueError):
            add_rule(self.conn, "Food", min_amount=1)

    def test_add_rule_bad_regex(self):
        with self.assertRaises(ValueError):
            add_rule(self.conn, "Food", pattern="(")

    def test_add_rule_returns_ids(self):
        a = add_rule(self.conn, "Food", contains="x")
        b = add_rule(self.conn, "Food", pattern="y")
        self.assertLess(a, b)

    def test_contains_case_insensitive(self):
        self.add_tx("2024-01-01", "STARBUCKS #12", -500)
        self.add_tx("2024-01-01", "Shell", -500)
        add_rule(self.conn, "Coffee", contains="starbucks")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(self.cats(), {"STARBUCKS #12": "Coffee", "Shell": None})

    def test_pattern_search_case_insensitive(self):
        self.add_tx("2024-01-01", "Payment to UBER trip", -1500)
        add_rule(self.conn, "Travel", pattern=r"uber\s+trip")
        categorize(self.conn)
        self.assertEqual(self.cats()["Payment to UBER trip"], "Travel")

    def test_amount_bounds_inclusive_absolute(self):
        for amt in (-999, -1000, -5000, -5001, 1000):
            self.add_tx("2024-01-01", "Shop %d" % amt, amt)
        add_rule(self.conn, "Mid", contains="shop", min_amount=1000, max_amount=5000)
        self.assertEqual(categorize(self.conn), 3)
        self.assertEqual(self.cats(), {"Shop -999": None, "Shop -1000": "Mid",
                                       "Shop -5000": "Mid", "Shop -5001": None,
                                       "Shop 1000": "Mid"})

    def test_all_conditions_must_hold(self):
        self.add_tx("2024-01-01", "Amazon books", -100)
        self.add_tx("2024-01-01", "Amazon fresh", -100)
        add_rule(self.conn, "Books", contains="amazon", pattern="book")
        categorize(self.conn)
        self.assertEqual(self.cats(), {"Amazon books": "Books", "Amazon fresh": None})

    def test_priority_then_insertion_order(self):
        self.add_tx("2024-01-01", "Amazon", -100)
        add_rule(self.conn, "First", contains="amazon")
        add_rule(self.conn, "Second", contains="amazon")
        categorize(self.conn)
        self.assertEqual(self.cats()["Amazon"], "First")
        add_rule(self.conn, "High", contains="amaz", priority=5)
        add_rule(self.conn, "High2", contains="amaz", priority=5)
        self.assertEqual(categorize(self.conn), 0)  # already categorized
        self.assertEqual(categorize(self.conn, recategorize=True), 1)
        self.assertEqual(self.cats()["Amazon"], "High")

    def test_recategorize_unmatched_left_alone(self):
        tx = self.add_tx("2024-01-01", "Amazon", -100)
        rid = add_rule(self.conn, "Shop", contains="amazon")
        categorize(self.conn)
        with self.conn:
            self.conn.execute("DELETE FROM rules WHERE id = ?", (rid,))
        add_rule(self.conn, "Other", contains="zzz")
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.cats()["Amazon"], "Shop")

    def test_count_only_changes(self):
        self.add_tx("2024-01-01", "Amazon", -100)
        add_rule(self.conn, "Shop", contains="amazon")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(categorize(self.conn, recategorize=True), 0)

    def test_manual_category_never_overridden(self):
        tx = self.add_tx("2024-01-01", "Amazon", -100)
        set_category(self.conn, tx, "Gifts")
        add_rule(self.conn, "Shop", contains="amazon", priority=100)
        self.assertEqual(categorize(self.conn), 0)
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.cats()["Amazon"], "Gifts")

    def test_manual_over_rule_assigned(self):
        tx = self.add_tx("2024-01-01", "Amazon", -100)
        add_rule(self.conn, "Shop", contains="amazon")
        categorize(self.conn)
        set_category(self.conn, tx, "Gifts")
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.cats()["Amazon"], "Gifts")

    def test_set_category_unknown_id(self):
        with self.assertRaises(ValueError):
            set_category(self.conn, 999, "X")
