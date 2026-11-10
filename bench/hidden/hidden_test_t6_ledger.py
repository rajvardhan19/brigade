"""Hidden grader for task t6_ledger (greenfield personal-finance toolkit). Not visible to the sessions under test."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from ledger import budgets, cli, db, importers, rules

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACME = "Date,Description,Amount\n2026-01-05,  Corner   Coffee ,-4.50\n2026-01-03,Salary,2500.00\n2026-01-10,FreshMart Groceries,-82.15\n"
ZENITH = ("Transaction Date,Payee,Debit,Credit\n01/07/2026,Rent Co,\"$1,234.56\",\n"
          "01/20/2026,Refund Store,,$15.00\n02/01/2026,Corner Coffee,$3.75,\n")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpath = os.path.join(self.tmp.name, "l.db")
        self.conn = db.connect(self.dbpath)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def csv(self, text, name="x.csv"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", newline="") as f:
            f.write(text)
        return path

    def txs(self, account=None):
        return db.list_transactions(self.conn, account)


class StorageTests(Base):
    def test_reconnect_keeps_data(self):
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        self.conn.close()
        self.conn = db.connect(self.dbpath)
        self.assertEqual(len(self.txs()), 3)

    def test_list_shape_and_order(self):
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        t = self.txs()
        self.assertEqual([x["date"] for x in t], ["2026-01-03", "2026-01-05", "2026-01-10"])
        self.assertTrue({"id", "account", "date", "description", "amount", "category"} <= set(t[0]))
        self.assertIsNone(t[0]["category"])

    def test_filter_by_account(self):
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        importers.import_csv(self.conn, self.csv(ZENITH, "z.csv"), "zenith", "card")
        self.assertEqual(len(self.txs("card")), 3)
        self.assertTrue(all(x["account"] == "card" for x in self.txs("card")))


class ImporterTests(Base):
    def test_acme(self):
        self.assertEqual(importers.import_csv(self.conn, self.csv(ACME), "acme", "chk"), (3, 0))
        coffee = [x for x in self.txs() if x["date"] == "2026-01-05"][0]
        self.assertEqual((coffee["description"], coffee["amount"]), ("Corner Coffee", -450))
        self.assertIn(250000, [x["amount"] for x in self.txs()])

    def test_zenith(self):
        self.assertEqual(importers.import_csv(self.conn, self.csv(ZENITH), "zenith", "card"), (3, 0))
        by_desc = {x["description"]: x for x in self.txs()}
        self.assertEqual(by_desc["Rent Co"]["amount"], -123456)
        self.assertEqual(by_desc["Rent Co"]["date"], "2026-01-07")
        self.assertEqual(by_desc["Refund Store"]["amount"], 1500)

    def test_reimport_skips_everything(self):
        path = self.csv(ACME)
        importers.import_csv(self.conn, path, "acme", "chk")
        self.assertEqual(importers.import_csv(self.conn, path, "acme", "chk"), (0, 3))
        self.assertEqual(len(self.txs()), 3)

    def test_overlapping_export(self):
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        more = "Date,Description,Amount\n2026-01-10,FreshMart Groceries,-82.15\n2026-01-12,Bookshop,-20.00\n"
        self.assertEqual(importers.import_csv(self.conn, self.csv(more, "m.csv"), "acme", "chk"), (1, 1))

    def test_whitespace_variant_is_duplicate(self):
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        again = "Date,Description,Amount\n2026-01-05,Corner Coffee,-4.50\n"
        self.assertEqual(importers.import_csv(self.conn, self.csv(again, "a.csv"), "acme", "chk"), (0, 1))

    def test_other_account_not_duplicate(self):
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        self.assertEqual(importers.import_csv(self.conn, self.csv(ACME, "b.csv"), "acme", "savings"), (3, 0))

    def test_identical_rows_in_one_file_both_kept(self):
        two = "Date,Description,Amount\n2026-01-05,Coffee,-3.00\n2026-01-05,Coffee,-3.00\n"
        self.assertEqual(importers.import_csv(self.conn, self.csv(two), "acme", "chk"), (2, 0))

    def test_unknown_bank(self):
        with self.assertRaises(ValueError):
            importers.import_csv(self.conn, self.csv(ACME), "megabank", "chk")

    def test_bad_amount_is_atomic_and_names_line(self):
        bad = "Date,Description,Amount\n2026-01-01,Ok,-1.00\n2026-01-02,Bad,abc\n"
        with self.assertRaises(ValueError) as ctx:
            importers.import_csv(self.conn, self.csv(bad), "acme", "chk")
        self.assertIn("line 3", str(ctx.exception))
        self.assertEqual(self.txs(), [])

    def test_bad_date_names_line(self):
        bad = "Date,Description,Amount\n01/02/2026,Wrong format,-1.00\n"
        with self.assertRaises(ValueError) as ctx:
            importers.import_csv(self.conn, self.csv(bad), "acme", "chk")
        self.assertIn("line 2", str(ctx.exception))

    def test_zenith_needs_exactly_one_of_debit_credit(self):
        both = "Transaction Date,Payee,Debit,Credit\n01/07/2026,X,1.00,2.00\n"
        with self.assertRaises(ValueError):
            importers.import_csv(self.conn, self.csv(both), "zenith", "card")
        neither = "Transaction Date,Payee,Debit,Credit\n01/07/2026,X,,\n"
        with self.assertRaises(ValueError):
            importers.import_csv(self.conn, self.csv(neither, "n.csv"), "zenith", "card")


class RuleTests(Base):
    def setUp(self):
        super().setUp()
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        importers.import_csv(self.conn, self.csv(ZENITH, "z.csv"), "zenith", "card")

    def cat(self, desc):
        return [x["category"] for x in self.txs() if x["description"] == desc]

    def test_contains_case_insensitive(self):
        rules.add_rule(self.conn, "Coffee", contains="coffee")
        self.assertEqual(rules.categorize(self.conn), 2)
        self.assertEqual(self.cat("Corner Coffee"), ["Coffee", "Coffee"])

    def test_pattern(self):
        rules.add_rule(self.conn, "Groceries", pattern=r"fresh\s*mart")
        rules.categorize(self.conn)
        self.assertEqual(self.cat("FreshMart Groceries"), ["Groceries"])

    def test_amount_range_uses_absolute_value_inclusive(self):
        rules.add_rule(self.conn, "Small", contains="coffee", max_amount=375)
        rules.categorize(self.conn)
        by_amount = {x["amount"]: x["category"] for x in self.txs() if x["description"] == "Corner Coffee"}
        self.assertEqual(by_amount, {-450: None, -375: "Small"})

    def test_priority_then_age(self):
        rules.add_rule(self.conn, "Low", contains="coffee", priority=1)
        rules.add_rule(self.conn, "High", contains="corner", priority=5)
        rules.add_rule(self.conn, "HighLater", contains="coffee", priority=5)
        rules.categorize(self.conn)
        self.assertEqual(self.cat("Corner Coffee"), ["High", "High"])

    def test_default_only_uncategorized(self):
        rules.add_rule(self.conn, "Coffee", contains="coffee")
        rules.categorize(self.conn)
        rules.add_rule(self.conn, "Treats", contains="coffee", priority=10)
        self.assertEqual(rules.categorize(self.conn), 0)
        self.assertEqual(self.cat("Corner Coffee"), ["Coffee", "Coffee"])

    def test_recategorize(self):
        rules.add_rule(self.conn, "Coffee", contains="coffee")
        rules.categorize(self.conn)
        rules.add_rule(self.conn, "Treats", contains="coffee", priority=10)
        self.assertEqual(rules.categorize(self.conn, recategorize=True), 2)
        self.assertEqual(self.cat("Corner Coffee"), ["Treats", "Treats"])

    def test_manual_category_never_overwritten(self):
        tid = [x["id"] for x in self.txs() if x["description"] == "Rent Co"][0]
        rules.set_category(self.conn, tid, "Housing")
        rules.add_rule(self.conn, "Other", contains="rent", priority=100)
        rules.categorize(self.conn, recategorize=True)
        self.assertEqual(self.cat("Rent Co"), ["Housing"])

    def test_unmatched_left_alone(self):
        rules.add_rule(self.conn, "Coffee", contains="coffee")
        rules.categorize(self.conn)
        self.assertEqual(self.cat("Salary"), [None])

    def test_rule_needs_condition(self):
        with self.assertRaises(ValueError):
            rules.add_rule(self.conn, "Nothing")

    def test_add_rule_returns_id(self):
        a = rules.add_rule(self.conn, "A", contains="a")
        b = rules.add_rule(self.conn, "B", contains="b")
        self.assertIsInstance(a, int)
        self.assertNotEqual(a, b)


class BudgetTests(Base):
    def setUp(self):
        super().setUp()
        importers.import_csv(self.conn, self.csv(ACME), "acme", "chk")
        importers.import_csv(self.conn, self.csv(ZENITH, "z.csv"), "zenith", "card")
        rules.add_rule(self.conn, "Coffee", contains="coffee")
        rules.add_rule(self.conn, "Groceries", contains="freshmart")
        rules.add_rule(self.conn, "Housing", contains="rent")
        rules.categorize(self.conn)

    def test_report(self):
        budgets.set_budget(self.conn, "Groceries", "2026-01", 10000)
        budgets.set_budget(self.conn, "Housing", "2026-01", 100000)
        budgets.set_budget(self.conn, "Travel", "2026-01", 5000)
        rows = budgets.monthly_report(self.conn, "2026-01")
        self.assertEqual([r["category"] for r in rows], ["Coffee", "Groceries", "Housing", "Travel"])
        by = {r["category"]: r for r in rows}
        self.assertEqual(by["Coffee"], {"category": "Coffee", "spent": 450, "budget": None, "remaining": None, "over": False})
        self.assertEqual(by["Groceries"], {"category": "Groceries", "spent": 8215, "budget": 10000, "remaining": 1785, "over": False})
        self.assertEqual(by["Housing"], {"category": "Housing", "spent": 123456, "budget": 100000, "remaining": -23456, "over": True})
        self.assertEqual(by["Travel"]["spent"], 0)

    def test_income_ignored_and_uncategorized(self):
        extra = "Date,Description,Amount\n2026-01-15,Mystery,-9.99\n"
        importers.import_csv(self.conn, self.csv(extra, "e.csv"), "acme", "chk")
        rows = {r["category"]: r for r in budgets.monthly_report(self.conn, "2026-01")}
        self.assertEqual(rows["Uncategorized"]["spent"], 999)
        self.assertNotIn(None, rows)
        self.assertEqual(sum(r["spent"] for r in rows.values()), 450 + 8215 + 123456 + 999)

    def test_month_filter_and_budget_replace(self):
        budgets.set_budget(self.conn, "Coffee", "2026-02", 100)
        budgets.set_budget(self.conn, "Coffee", "2026-02", 500)
        rows = budgets.monthly_report(self.conn, "2026-02")
        self.assertEqual(rows, [{"category": "Coffee", "spent": 375, "budget": 500, "remaining": 125, "over": False}])


class CliTests(Base):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(["--db", self.dbpath, *args])
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, out.getvalue(), err.getvalue()

    def test_end_to_end(self):
        code, out, _ = self.run_cli("import", self.csv(ACME), "--bank", "acme", "--account", "chk")
        self.assertEqual((code, out.strip()), (0, "Imported 3, skipped 0"))
        code, out, _ = self.run_cli("import", self.csv(ZENITH, "z.csv"), "--bank", "zenith", "--account", "card")
        self.assertEqual(out.strip(), "Imported 3, skipped 0")
        code, out, _ = self.run_cli("rule", "add", "Coffee", "--contains", "coffee")
        self.assertEqual(code, 0)
        self.assertRegex(out.strip(), r"^Rule \d+ added$")
        self.run_cli("rule", "add", "Housing", "--pattern", "^rent", "--priority", "2")
        code, out, _ = self.run_cli("categorize")
        self.assertEqual(out.strip(), "Categorized 3")
        code, out, _ = self.run_cli("budget", "set", "Housing", "2026-01", "1000")
        self.assertEqual((code, out.strip()), (0, "Budget set"))
        self.run_cli("budget", "set", "Coffee", "2026-01", "20.50")
        code, out, _ = self.run_cli("report", "2026-01")
        self.assertEqual(code, 0)
        lines = [line.split("\t") for line in out.strip().splitlines()]
        self.assertEqual(lines, [
            ["Coffee", "4.50", "20.50", "16.00"],
            ["Housing", "1234.56", "1000.00", "-234.56", "OVER"],
            ["Uncategorized", "82.15", "-", "-"],
        ])

    def test_categorize_all_flag(self):
        self.run_cli("import", self.csv(ACME), "--bank", "acme", "--account", "chk")
        self.run_cli("rule", "add", "Coffee", "--contains", "coffee")
        self.run_cli("categorize")
        self.run_cli("rule", "add", "Treat", "--contains", "coffee", "--priority", "9")
        self.assertEqual(self.run_cli("categorize")[1].strip(), "Categorized 0")
        self.assertEqual(self.run_cli("categorize", "--all")[1].strip(), "Categorized 1")

    def test_rule_amount_options(self):
        self.run_cli("import", self.csv(ACME), "--bank", "acme", "--account", "chk")
        self.run_cli("rule", "add", "Big", "--pattern", ".", "--min", "5000")
        self.run_cli("categorize")
        cats = {x["description"]: x["category"] for x in self.txs()}
        self.assertEqual(cats, {"Salary": "Big", "FreshMart Groceries": "Big", "Corner Coffee": None})

    def assert_clean_error(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip(), "expected a message on stderr")
        self.assertNotIn("Traceback", err + out)

    def test_errors_are_clean(self):
        self.assert_clean_error("import", os.path.join(self.tmp.name, "missing.csv"), "--bank", "acme", "--account", "chk")
        self.assert_clean_error("import", self.csv(ACME), "--bank", "megabank", "--account", "chk")
        self.assert_clean_error("import", self.csv("Date,Description,Amount\n2026-01-01,x,abc\n", "bad.csv"),
                                "--bank", "acme", "--account", "chk")
        self.assert_clean_error("frobnicate")

    def test_python_dash_m(self):
        p = subprocess.run([sys.executable, "-m", "ledger", "--db", self.dbpath, "report", "2026-01"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == "__main__":
    unittest.main()
