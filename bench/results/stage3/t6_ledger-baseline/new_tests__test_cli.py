import contextlib
import io
import os
import subprocess
import sys

from ledger.cli import format_money, main
from tests.helpers import TempDirTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CliTests(TempDirTestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--db", self.db_path, *args])
        return code, out.getvalue(), err.getvalue()

    def assertFails(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip())
        self.assertNotIn("Traceback", err)
        return err

    def test_format_money(self):
        self.assertEqual(format_money(12345), "123.45")
        self.assertEqual(format_money(-1000), "-10.00")
        self.assertEqual(format_money(-5), "-0.05")
        self.assertEqual(format_money(0), "0.00")
        self.assertEqual(format_money(None), "-")

    def test_full_workflow(self):
        acme = self.write("a.csv",
                          "Date,Description,Amount\n"
                          "2024-03-01,Corner Market,-50.00\n"
                          "2024-03-02,Cafe Luna,-30.00\n"
                          "2024-03-03,Salary,1000.00\n"
                          "2024-03-04,Mystery,-1.23\n")
        self.assertEqual(self.run_cli("import", acme, "--bank", "acme",
                                      "--account", "checking"),
                         (0, "Imported 4, skipped 0\n", ""))
        self.assertEqual(self.run_cli("import", acme, "--bank", "acme",
                                      "--account", "checking")[1],
                         "Imported 0, skipped 4\n")
        self.assertEqual(self.run_cli("rule", "add", "Groceries",
                                      "--contains", "market")[1], "Rule 1 added\n")
        self.assertEqual(self.run_cli("rule", "add", "Dining", "--pattern", "^cafe",
                                      "--min", "100", "--max", "10000",
                                      "--priority", "2")[1], "Rule 2 added\n")
        self.assertEqual(self.run_cli("categorize")[1], "Categorized 2\n")
        self.assertEqual(self.run_cli("categorize", "--all")[1], "Categorized 0\n")
        self.assertEqual(self.run_cli("budget", "set", "Groceries", "2024-03", "250")[1],
                         "Budget set\n")
        self.assertEqual(self.run_cli("budget", "set", "Dining", "2024-03", "20.00")[1],
                         "Budget set\n")
        code, out, _ = self.run_cli("report", "2024-03")
        self.assertEqual(code, 0)
        self.assertEqual(out,
                         "Dining\t30.00\t20.00\t-10.00\tOVER\n"
                         "Groceries\t50.00\t250.00\t200.00\n"
                         "Uncategorized\t1.23\t-\t-\n")

    def test_errors(self):
        self.assertFails("import", os.path.join(self.tmp, "missing.csv"),
                         "--bank", "acme", "--account", "x")
        good = self.write("a.csv", "Date,Description,Amount\n2024-01-01,X,-1\n")
        self.assertFails("import", good, "--bank", "nope", "--account", "x")
        bad = self.write("b.csv", "Date,Description,Amount\n2024-01-01,X,oops\n")
        err = self.assertFails("import", bad, "--bank", "acme", "--account", "x")
        self.assertIn("line 2", err)
        self.assertFails("import", good, "--account", "x")
        self.assertFails("rule", "add", "Food")
        self.assertFails("rule", "add", "Food", "--pattern", "(")
        self.assertFails("rule", "add", "Food", "--contains", "x", "--min", "abc")
        self.assertFails("budget", "set", "Food", "2024-01", "abc")
        self.assertFails("budget", "set", "Food", "2024-13", "10")
        self.assertFails("report", "nope")
        self.assertFails("frobnicate")
        self.assertFails()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertNotEqual(main(["report", "2024-01"]), 0)  # missing --db

    def test_python_dash_m(self):
        f = self.write("a.csv", "Date,Description,Amount\n2024-01-01,X,-1\n")
        proc = subprocess.run(
            [sys.executable, "-m", "ledger", "--db", self.db_path, "import", f,
             "--bank", "acme", "--account", "x"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "Imported 1, skipped 0\n")
        proc = subprocess.run(
            [sys.executable, "-m", "ledger", "--db", self.db_path, "import",
             f, "--bank", "nope", "--account", "x"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)
