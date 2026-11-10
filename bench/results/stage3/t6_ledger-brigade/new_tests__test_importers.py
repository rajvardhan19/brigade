from helpers import LedgerTestCase

from ledger import db
from ledger.importers import import_csv

ACME = ("Date,Description,Amount\n"
        "2024-01-05,  Coffee   Shop ,-4.50\n"
        "2024-01-06,Paycheck,2000.00\n"
        "2024-01-07,\"Grocery\tStore, Main St\",-55.25\n")

ZENITH = ("Transaction Date,Payee,Debit,Credit\n"
          "01/15/2024,Rent,\"$1,234.56\",\n"
          "01/16/2024,Refund,,$20.00\n")


class ImportTests(LedgerTestCase):
    def test_acme(self):
        path = self.write("a.csv", ACME)
        self.assertEqual(import_csv(self.conn, path, "acme", "chk"), (3, 0))
        txs = db.list_transactions(self.conn)
        self.assertEqual([(t["date"], t["description"], t["amount"], t["account"]) for t in txs], [
            ("2024-01-05", "Coffee Shop", -450, "chk"),
            ("2024-01-06", "Paycheck", 200000, "chk"),
            ("2024-01-07", "Grocery Store, Main St", -5525, "chk"),
        ])

    def test_zenith(self):
        path = self.write("z.csv", ZENITH)
        self.assertEqual(import_csv(self.conn, path, "zenith", "card"), (2, 0))
        txs = db.list_transactions(self.conn)
        self.assertEqual([(t["date"], t["description"], t["amount"]) for t in txs], [
            ("2024-01-15", "Rent", -123456), ("2024-01-16", "Refund", 2000)])

    def test_reimport_skips_all(self):
        path = self.write("a.csv", ACME)
        import_csv(self.conn, path, "acme", "chk")
        self.assertEqual(import_csv(self.conn, path, "acme", "chk"), (0, 3))
        self.assertEqual(len(db.list_transactions(self.conn)), 3)

    def test_same_rows_other_account_not_duplicates(self):
        path = self.write("a.csv", ACME)
        import_csv(self.conn, path, "acme", "chk")
        self.assertEqual(import_csv(self.conn, path, "acme", "other"), (3, 0))

    def test_rows_within_file_not_duplicates(self):
        path = self.write("a.csv", "Date,Description,Amount\n"
                          "2024-01-05,Coffee,-4.50\n2024-01-05,Coffee,-4.50\n")
        self.assertEqual(import_csv(self.conn, path, "acme", "chk"), (2, 0))
        self.assertEqual(import_csv(self.conn, path, "acme", "chk"), (0, 2))

    def test_duplicate_uses_normalized_description(self):
        import_csv(self.conn, self.write("a.csv", "Date,Description,Amount\n"
                                         "2024-01-05,Coffee Shop,-4.50\n"), "acme", "chk")
        path = self.write("b.csv", "Date,Description,Amount\n"
                          "2024-01-05,  Coffee    Shop,-4.50\n2024-01-05,Coffee Shop,-4.51\n")
        self.assertEqual(import_csv(self.conn, path, "acme", "chk"), (1, 1))

    def test_unknown_bank(self):
        with self.assertRaises(ValueError):
            import_csv(self.conn, self.write("a.csv", ACME), "nope", "chk")

    def assertLineError(self, text, bank, line):
        path = self.write("bad.csv", text)
        with self.assertRaises(ValueError) as cm:
            import_csv(self.conn, path, bank, "chk")
        self.assertIn("line %d" % line, str(cm.exception))
        self.assertEqual(db.list_transactions(self.conn), [])

    def test_bad_acme_date(self):
        self.assertLineError("Date,Description,Amount\n2024-01-05,A,-1\n01/05/2024,B,-1\n",
                             "acme", 3)

    def test_bad_acme_amount(self):
        self.assertLineError("Date,Description,Amount\n2024-01-05,A,-1\n2024-01-05,B,x\n",
                             "acme", 3)

    def test_bad_zenith_both(self):
        self.assertLineError("Transaction Date,Payee,Debit,Credit\n01/15/2024,A,1.00,2.00\n",
                             "zenith", 2)

    def test_bad_zenith_neither(self):
        self.assertLineError("Transaction Date,Payee,Debit,Credit\n"
                             "01/15/2024,A,1.00,\n01/15/2024,B,,\n", "zenith", 3)

    def test_bad_zenith_date(self):
        self.assertLineError("Transaction Date,Payee,Debit,Credit\n2024-01-15,A,1.00,\n",
                             "zenith", 2)

    def test_line_number_counts_quoted_newlines(self):
        self.assertLineError('Date,Description,Amount\n2024-01-05,"multi\nline",-1\n'
                             "2024-01-05,B,bad\n", "acme", 4)

    def test_wrong_header(self):
        with self.assertRaises(ValueError):
            import_csv(self.conn, self.write("z.csv", ZENITH), "acme", "chk")

    def test_missing_file(self):
        with self.assertRaises(OSError):
            import_csv(self.conn, self.tmp + "/missing.csv", "acme", "chk")
