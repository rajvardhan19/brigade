import contextlib
import io
import os
import subprocess
import sys

from helpers import LedgerTestCase

from ledger.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CliTests(LedgerTestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--db", self.db_path] + list(args))
        return code, out.getvalue(), err.getvalue()

    def ok(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 0, err)
        return out

    def fails(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip())
        self.assertNotIn("Traceback", err)
        return err

    def test_full_flow(self):
        path = self.write("a.csv", "Date,Description,Amount\n"
                          "2024-03-01,Whole Foods,-60.00\n"
                          "2024-03-02,Cinema,-15.00\n"
                          "2024-03-03,Corner shop,-7.00\n"
                          "2024-03-04,Salary,3000.00\n")
        self.assertEqual(self.ok("import", path, "--bank", "acme", "--account", "chk"),
                         "Imported 4, skipped 0\n")
        self.assertEqual(self.ok("import", path, "--bank", "acme", "--account", "chk"),
                         "Imported 0, skipped 4\n")
        self.assertEqual(self.ok("rule", "add", "Food", "--contains", "foods"), "Rule 1 added\n")
        self.assertEqual(self.ok("rule", "add", "Fun", "--pattern", "^cine", "--min", "100",
                                 "--max", "2000", "--priority", "3"), "Rule 2 added\n")
        self.assertEqual(self.ok("categorize"), "Categorized 2\n")
        self.assertEqual(self.ok("categorize", "--all"), "Categorized 0\n")
        self.assertEqual(self.ok("budget", "set", "Food", "2024-03", "50"), "Budget set\n")
        self.assertEqual(self.ok("budget", "set", "Fun", "2024-03", "20.00"), "Budget set\n")
        self.assertEqual(self.ok("budget", "set", "Rent", "2024-03", "1000"), "Budget set\n")
        self.assertEqual(self.ok("report", "2024-03"),
                         "Food\t60.00\t50.00\t-10.00\tOVER\n"
                         "Fun\t15.00\t20.00\t5.00\n"
                         "Rent\t0.00\t1000.00\t1000.00\n"
                         "Uncategorized\t7.00\t-\t-\n")

    def test_errors(self):
        good = self.write("a.csv", "Date,Description,Amount\n2024-03-01,X,-1\n")
        bad = self.write("b.csv", "Date,Description,Amount\n2024-03-01,X,oops\n")
        self.fails("import", self.tmp + "/missing.csv", "--bank", "acme", "--account", "c")
        self.fails("import", good, "--bank", "nope", "--account", "c")
        self.assertIn("line 2", self.fails("import", bad, "--bank", "acme", "--account", "c"))
        self.fails("import", good, "--bank", "acme")
        self.fails("rule", "add", "Food")
        self.fails("rule", "add", "Food", "--pattern", "(")
        self.fails("rule", "add", "Food", "--contains", "x", "--min", "abc")
        self.fails("budget", "set", "Food", "2024-3", "10")
        self.fails("budget", "set", "Food", "2024-03", "ten")
        self.fails("report", "nope")
        self.fails("frobnicate")
        self.fails()

    def test_missing_db_option(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["report", "2024-03"])
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", err.getvalue())

    def test_bad_db_path(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--db", os.path.join(self.tmp, "no", "such", "dir.db"), "report", "2024-03"])
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", err.getvalue())

    def test_python_dash_m(self):
        proc = subprocess.run(
            [sys.executable, "-m", "ledger", "--db", self.db_path, "report", "2024-03"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = subprocess.run(
            [sys.executable, "-m", "ledger", "--db", self.db_path, "report", "bad"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
