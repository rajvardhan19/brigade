import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from ledger.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "t.db")
        self.n = 0

    def write(self, text):
        self.n += 1
        p = os.path.join(self.tmp.name, "f%d.csv" % self.n)
        with open(p, "w", newline="") as f:
            f.write(text)
        return p

    def run_cli(self, *args, db=True):
        argv = (["--db", self.db] if db else []) + list(args)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        self.assertNotIn("Traceback", err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def ok(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertEqual((code, err), (0, ""))
        return out

    def fails(self, *args, db=True):
        code, out, err = self.run_cli(*args, db=db)
        self.assertNotEqual(code, 0)
        self.assertTrue(err)
        return err

    ACME = ("Date,Description,Amount\n2024-01-05,Coffee Shop,-5.00\n"
            "2024-01-06,Grocery Store,-60.50\n2024-01-07,Paycheck,1000.00\n")

    def test_import_twice(self):
        p = self.write(self.ACME)
        a = ["import", p, "--bank", "acme", "--account", "a"]
        self.assertEqual(self.ok(*a), "Imported 3, skipped 0\n")
        self.assertEqual(self.ok(*a), "Imported 0, skipped 3\n")

    def test_zenith(self):
        p = self.write("Transaction Date,Payee,Debit,Credit\n"
                       "01/05/2024,Coffee,$5.00,\n01/06/2024,Pay,,\"$1,000.00\"\n")
        self.assertEqual(
            self.ok("import", p, "--bank", "zenith", "--account", "z"),
            "Imported 2, skipped 0\n")

    def test_rule_add(self):
        self.assertEqual(self.ok("rule", "add", "Food", "--contains", "cof"),
                         "Rule 1 added\n")
        self.assertEqual(
            self.ok("rule", "add", "Pay", "--pattern", "pay", "--min", "100",
                    "--max", "5000", "--priority", "2"), "Rule 2 added\n")

    def test_categorize(self):
        p = self.write(self.ACME)
        self.ok("import", p, "--bank", "acme", "--account", "a")
        self.ok("rule", "add", "Food", "--contains", "coffee")
        self.assertEqual(self.ok("categorize"), "Categorized 1\n")
        self.assertEqual(self.ok("categorize"), "Categorized 0\n")
        self.ok("rule", "add", "Eats", "--contains", "coffee", "--priority", "5")
        self.assertEqual(self.ok("categorize"), "Categorized 0\n")
        self.assertEqual(self.ok("categorize", "--all"), "Categorized 1\n")

    def test_budget_set(self):
        self.assertEqual(self.ok("budget", "set", "Food", "2024-01", "250"),
                         "Budget set\n")
        self.assertEqual(self.ok("budget", "set", "Food", "2024-01", "250.00"),
                         "Budget set\n")
        self.assertEqual(self.ok("report", "2024-01"), "Food\t0.00\t250.00\t250.00\n")
        self.ok("budget", "set", "Food", "2024-01", "250.0")
        self.assertEqual(self.ok("report", "2024-01"), "Food\t0.00\t250.00\t250.00\n")

    def test_budget_bad(self):
        for bad in ["12.345", "abc", "-5", "nan", "inf"]:
            self.fails("budget", "set", "Food", "2024-01", bad)

    def test_report(self):
        p = self.write(self.ACME + "2024-01-08,Rent,-0.50\n")
        self.ok("import", p, "--bank", "acme", "--account", "a")
        self.ok("rule", "add", "Food", "--contains", "coffee")
        self.ok("rule", "add", "Food", "--contains", "grocery")
        self.ok("rule", "add", "Misc", "--contains", "rent")
        self.ok("categorize")
        self.ok("budget", "set", "Food", "2024-01", "50")
        self.ok("budget", "set", "Fun", "2024-01", "10")
        lines = self.ok("report", "2024-01").splitlines()
        self.assertIn("Food\t65.50\t50.00\t-15.50\tOVER", lines)
        self.assertIn("Fun\t0.00\t10.00\t10.00", lines)
        self.assertIn("Misc\t0.50\t-\t-", lines)

    def test_report_empty(self):
        self.assertEqual(self.ok("report", "2024-01"), "")

    def test_missing_file(self):
        self.assertIn("error:", self.fails(
            "import", "/nonexistent/x.csv", "--bank", "acme", "--account", "a"))

    def test_unknown_bank(self):
        p = self.write(self.ACME)
        self.assertIn("error:", self.fails(
            "import", p, "--bank", "nope", "--account", "a"))

    def test_malformed_csv(self):
        p = self.write("Date,Description,Amount\n2024-01-05,X,-1.00\n"
                       "2024-13-45,Y,-2.00\n")
        err = self.fails("import", p, "--bank", "acme", "--account", "a")
        self.assertIn("line 3", err)

    def test_arg_errors(self):
        self.fails("report", "2024-01", db=False)
        self.fails("frobnicate")
        self.fails("report", "2024-1")
        self.fails("rule", "add", "Food")
        self.fails("rule", "add", "Food", "--contains", "x", "--min", "abc")

    def assert_clean_fail(self, *argv):
        err = self.fails(*argv)
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)

    def test_budget_bad_amounts(self):
        for amt in ("1e30", "1e3", "-5", "+5", "99999999999999999999999999999",
                    "\u0661\u0662"):
            self.assert_clean_fail("budget", "set", "Food", "2024-01", amt)
        self.assertEqual(main(["--db", self.db, "budget", "set", "Food",
                               "2024-01", "250.000"]), 0)
        self.assert_clean_fail("budget", "set", "Food", "2024-01", "250.001")

    def test_rule_huge_numbers(self):
        big = "99999999999999999999"
        self.assert_clean_fail("rule", "add", "X", "--contains", "y",
                               "--priority", big)
        self.assert_clean_fail("rule", "add", "X", "--contains", "y",
                               "--min", big)


    def test_help_returns_zero(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--help"]), 0)

    def test_subprocess(self):
        r = subprocess.run(
            [sys.executable, "-m", "ledger", "--db", self.db, "report", "2024-01"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
