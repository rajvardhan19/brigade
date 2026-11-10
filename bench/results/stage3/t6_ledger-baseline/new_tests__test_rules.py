from ledger import db
from ledger.rules import add_rule, categorize, set_category
from tests.helpers import TempDirTestCase


class RuleTests(TempDirTestCase):
    def categories(self):
        return {t["id"]: t["category"] for t in db.list_transactions(self.conn)}

    def test_add_rule_returns_ids(self):
        a = add_rule(self.conn, "Food", contains="cafe")
        b = add_rule(self.conn, "Food", pattern="^grocer")
        self.assertNotEqual(a, b)

    def test_add_rule_requires_contains_or_pattern(self):
        with self.assertRaises(ValueError):
            add_rule(self.conn, "Food")
        with self.assertRaises(ValueError):
            add_rule(self.conn, "Food", min_amount=100)

    def test_add_rule_rejects_bad_regex(self):
        with self.assertRaises(ValueError):
            add_rule(self.conn, "Food", pattern="(")

    def test_contains_is_case_insensitive(self):
        t = self.add_tx("2024-01-01", "BLUE BOTTLE CAFE", -500)
        add_rule(self.conn, "Coffee", contains="Cafe")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(self.categories()[t], "Coffee")

    def test_pattern_is_case_insensitive_search(self):
        t1 = self.add_tx("2024-01-01", "Pay: UBER *trip 123", -500)
        t2 = self.add_tx("2024-01-01", "Lyft", -500)
        add_rule(self.conn, "Transport", pattern=r"uber \*trip")
        self.assertEqual(categorize(self.conn), 1)
        self.assertEqual(self.categories(), {t1: "Transport", t2: None})

    def test_amount_bounds_inclusive_on_absolute_value(self):
        ts = [self.add_tx("2024-01-01", "Shop", a) for a in (-999, -1000, -5000, -5001, 3000)]
        add_rule(self.conn, "Mid", contains="shop", min_amount=1000, max_amount=5000)
        self.assertEqual(categorize(self.conn), 3)
        self.assertEqual([self.categories()[t] for t in ts],
                         [None, "Mid", "Mid", None, "Mid"])

    def test_all_conditions_must_hold(self):
        t1 = self.add_tx("2024-01-01", "Amazon Prime", -1000)
        t2 = self.add_tx("2024-01-01", "Amazon Books", -1000)
        add_rule(self.conn, "Subs", contains="amazon", pattern="prime")
        categorize(self.conn)
        self.assertEqual(self.categories(), {t1: "Subs", t2: None})

    def test_priority_then_insertion_order(self):
        t = self.add_tx("2024-01-01", "Costco Gas", -4000)
        add_rule(self.conn, "Shopping", contains="costco")
        add_rule(self.conn, "Gas", contains="gas", priority=5)
        add_rule(self.conn, "Other", contains="gas", priority=5)
        categorize(self.conn)
        self.assertEqual(self.categories()[t], "Gas")

    def test_tie_first_added_wins(self):
        t = self.add_tx("2024-01-01", "Costco Gas", -4000)
        add_rule(self.conn, "Shopping", contains="costco")
        add_rule(self.conn, "Gas", contains="gas")
        categorize(self.conn)
        self.assertEqual(self.categories()[t], "Shopping")

    def test_default_only_touches_uncategorized(self):
        t = self.add_tx("2024-01-01", "Costco", -4000)
        add_rule(self.conn, "Shopping", contains="costco")
        categorize(self.conn)
        add_rule(self.conn, "Bulk", contains="costco", priority=10)
        self.assertEqual(categorize(self.conn), 0)
        self.assertEqual(self.categories()[t], "Shopping")

    def test_recategorize_recomputes_rule_categories(self):
        t = self.add_tx("2024-01-01", "Costco", -4000)
        add_rule(self.conn, "Shopping", contains="costco")
        categorize(self.conn)
        add_rule(self.conn, "Bulk", contains="costco", priority=10)
        self.assertEqual(categorize(self.conn, recategorize=True), 1)
        self.assertEqual(self.categories()[t], "Bulk")
        # Nothing changes on a second pass.
        self.assertEqual(categorize(self.conn, recategorize=True), 0)

    def test_unmatched_left_alone(self):
        t = self.add_tx("2024-01-01", "Mystery", -100)
        add_rule(self.conn, "Food", contains="cafe")
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertIsNone(self.categories()[t])

    def test_manual_category_never_changed(self):
        t = self.add_tx("2024-01-01", "Costco", -4000)
        set_category(self.conn, t, "Gifts")
        add_rule(self.conn, "Shopping", contains="costco")
        self.assertEqual(categorize(self.conn), 0)
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.categories()[t], "Gifts")

    def test_manual_overrides_rule_category(self):
        t = self.add_tx("2024-01-01", "Costco", -4000)
        add_rule(self.conn, "Shopping", contains="costco")
        categorize(self.conn)
        set_category(self.conn, t, "Gifts")
        self.assertEqual(categorize(self.conn, recategorize=True), 0)
        self.assertEqual(self.categories()[t], "Gifts")

    def test_set_category_unknown_id(self):
        with self.assertRaises(ValueError):
            set_category(self.conn, 999, "X")
