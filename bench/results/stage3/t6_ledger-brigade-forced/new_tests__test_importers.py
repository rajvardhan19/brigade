import os
import tempfile
import unittest

from ledger import db, importers

ACME = "Date,Description,Amount\n"
ZEN = "Transaction Date,Payee,Debit,Credit\n"


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = db.connect(":memory:")
        self.n = 0

    def write(self, text):
        self.n += 1
        p = os.path.join(self.tmp.name, "f%d.csv" % self.n)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def rows(self, account=None):
        return [(t["date"], t["description"], t["amount"])
                for t in db.list_transactions(self.conn, account)]

    def test_acme(self):
        p = self.write(ACME + "2024-01-05,Coffee,-12.50\n2024-01-06,Pay,100\n")
        self.assertEqual(importers.import_csv(self.conn, p, "acme", "a"), (2, 0))
        self.assertEqual(self.rows(), [("2024-01-05", "Coffee", -1250),
                                       ("2024-01-06", "Pay", 10000)])
        self.assertIsNone(db.list_transactions(self.conn)[0]["category"])

    def test_zenith(self):
        p = self.write(ZEN + '01/31/2024,Rent,"$1,234.56",\n02/01/2024,Pay,,$10\n')
        self.assertEqual(importers.import_csv(self.conn, p, "zenith", "z"), (2, 0))
        self.assertEqual(self.rows(), [("2024-01-31", "Rent", -123456),
                                       ("2024-02-01", "Pay", 1000)])

    def test_whitespace(self):
        p = self.write(ACME + '2024-01-05,"  A   big\t  cafe ",-1\n')
        importers.import_csv(self.conn, p, "acme", "a")
        self.assertEqual(self.rows()[0][1], "A big cafe")

    def test_reimport(self):
        p = self.write(ACME + "2024-01-05,X,-1\n2024-01-06,Y,-2\n")
        importers.import_csv(self.conn, p, "acme", "a")
        self.assertEqual(importers.import_csv(self.conn, p, "acme", "a"), (0, 2))
        self.assertEqual(len(self.rows()), 2)

    def test_identical_rows_in_file(self):
        p = self.write(ACME + "2024-01-05,X,-1\n2024-01-05,X,-1\n")
        self.assertEqual(importers.import_csv(self.conn, p, "acme", "a"), (2, 0))
        self.assertEqual(len(self.rows()), 2)

    def test_db_row_duplicated_in_file(self):
        p1 = self.write(ACME + "2024-01-05,X,-1\n")
        importers.import_csv(self.conn, p1, "acme", "a")
        p2 = self.write(ACME + "2024-01-05,X,-1\n2024-01-05, X ,-1\n")
        self.assertEqual(importers.import_csv(self.conn, p2, "acme", "a"), (0, 2))
        self.assertEqual(len(self.rows()), 1)

    def test_per_account(self):
        p = self.write(ACME + "2024-01-05,X,-1\n")
        importers.import_csv(self.conn, p, "acme", "a")
        self.assertEqual(importers.import_csv(self.conn, p, "acme", "b"), (1, 0))

    def test_unknown_bank(self):
        with self.assertRaises(ValueError):
            importers.import_csv(self.conn, "/nonexistent.csv", "nope", "a")

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            importers.import_csv(self.conn, "/nonexistent.csv", "acme", "a")

    def assert_bad(self, bank, text, line="line 3"):
        p = self.write(text)
        with self.assertRaises(ValueError) as cm:
            importers.import_csv(self.conn, p, bank, "a")
        self.assertIn(line, str(cm.exception))
        self.assertEqual(db.list_transactions(self.conn), [])

    def test_bad_rows(self):
        good = "2024-01-05,X,-1\n"
        self.assert_bad("acme", ACME + good + "2024-02-30,X,-1\n")
        self.assert_bad("acme", ACME + good + "2024-01-05,X,abc\n")
        self.assert_bad("acme", ACME + good + "2024-01-05,X,1.234\n")
        self.assert_bad("acme", ACME + good + "2024-01-05,X,NaN\n")
        self.assert_bad("acme", ACME + good + "2024-01-05,X\n")
        self.assert_bad("acme", ACME + good + "2024-01-05,X,$5\n")

    def test_bad_zenith(self):
        good = "01/05/2024,X,1,\n"
        self.assert_bad("zenith", ZEN + good + "01/05/2024,X,,\n")
        self.assert_bad("zenith", ZEN + good + "01/05/2024,X,1,2\n")
        self.assert_bad("zenith", ZEN + good + "13/05/2024,X,1,\n")
        self.assert_bad("zenith", ZEN + good + "01/05/2024,X,-1,\n")

    def test_bad_line_first_row(self):
        self.assert_bad("acme", ACME + "\n2024-01-05,X,1.234\n")

    def test_bad_header(self):
        self.assert_bad("acme", "Date,Desc,Amount\n2024-01-05,X,1\n", "line 1")
        self.assert_bad("acme", "", "line 1")
        self.assert_bad("zenith", ACME, "line 1")

    def test_huge_amounts_rejected(self):
        for digits in (20, 29):
            amt = "9" * (digits - 2) + ".00"
            p = self.write(ACME + "2024-01-05,OK,-1.00\n2024-01-06,Big,%s\n" % amt)
            with self.assertRaises(ValueError) as cm:
                importers.import_csv(self.conn, p, "acme", "a")
            self.assertIn("line 3", str(cm.exception))
            self.assertIn("malformed amount", str(cm.exception))
            self.assertEqual(self.rows(), [])

    def test_huge_zenith_rejected(self):
        p = self.write(ZEN + "01/05/2024,Big,%s,\n" % ("9" * 25))
        with self.assertRaisesRegex(ValueError, "line 2"):
            importers.import_csv(self.conn, p, "zenith", "a")
        self.assertEqual(self.rows(), [])

    def test_non_ascii_digits_rejected(self):
        p = self.write(ACME + "2024-01-05,X,-\u0661\u0662.50\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            importers.import_csv(self.conn, p, "acme", "a")
        p = self.write(ACME + "\u0662\u0660\u0662\u0664-01-05,X,-1.00\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            importers.import_csv(self.conn, p, "acme", "a")
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
