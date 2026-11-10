from ledger import db
from ledger.importers import import_csv
from tests.helpers import TempDirTestCase

ACME = (
    "Date,Description,Amount\n"
    "2024-01-05,  Coffee   Shop  ,-12.50\n"
    "2024-01-06,Paycheck,2000\n"
    "2024-01-07,\"Grocer, Inc\",-3.5\n"
)

ZENITH = (
    "Transaction Date,Payee,Debit,Credit\n"
    "01/15/2024,Rent,\"$1,234.56\",\n"
    "1/16/2024,Refund,,$20.00\n"
    "01/17/2024,Big\tStore,99,\n"
)


class AcmeTests(TempDirTestCase):
    def test_import(self):
        path = self.write("a.csv", ACME)
        self.assertEqual(import_csv(self.conn, path, "acme", "checking"), (3, 0))
        txs = db.list_transactions(self.conn)
        self.assertEqual(
            [(t["date"], t["description"], t["amount"], t["account"]) for t in txs],
            [("2024-01-05", "Coffee Shop", -1250, "checking"),
             ("2024-01-06", "Paycheck", 200000, "checking"),
             ("2024-01-07", "Grocer, Inc", -350, "checking")],
        )

    def test_reimport_skips_everything(self):
        path = self.write("a.csv", ACME)
        import_csv(self.conn, path, "acme", "checking")
        self.assertEqual(import_csv(self.conn, path, "acme", "checking"), (0, 3))
        self.assertEqual(len(db.list_transactions(self.conn)), 3)

    def test_duplicates_are_per_account(self):
        path = self.write("a.csv", ACME)
        import_csv(self.conn, path, "acme", "checking")
        self.assertEqual(import_csv(self.conn, path, "acme", "savings"), (3, 0))

    def test_duplicate_matches_normalized_description(self):
        import_csv(self.conn, self.write("a.csv", ACME), "acme", "checking")
        path = self.write("b.csv",
                          "Date,Description,Amount\n2024-01-05,Coffee Shop,-12.50\n"
                          "2024-01-05,Coffee Shop,-12.51\n")
        self.assertEqual(import_csv(self.conn, path, "acme", "checking"), (1, 1))

    def test_rows_within_file_are_not_duplicates(self):
        path = self.write("a.csv",
                          "Date,Description,Amount\n"
                          "2024-01-05,Coffee,-1.00\n2024-01-05,Coffee,-1.00\n")
        self.assertEqual(import_csv(self.conn, path, "acme", "checking"), (2, 0))
        # Second import: both rows are now duplicates.
        self.assertEqual(import_csv(self.conn, path, "acme", "checking"), (0, 2))

    def test_bad_amount_reports_line_and_imports_nothing(self):
        path = self.write("a.csv",
                          "Date,Description,Amount\n"
                          "2024-01-05,Coffee,-1.00\n2024-01-06,Tea,abc\n")
        with self.assertRaisesRegex(ValueError, r"line 3\b"):
            import_csv(self.conn, path, "acme", "checking")
        self.assertEqual(db.list_transactions(self.conn), [])

    def test_bad_date_reports_line(self):
        for bad in ("2024-13-01", "01/05/2024", "2024-02-30", "", "20240105"):
            with self.subTest(bad=bad):
                path = self.write("a.csv",
                                  f"Date,Description,Amount\n{bad},Coffee,-1.00\n")
                with self.assertRaisesRegex(ValueError, r"line 2\b"):
                    import_csv(self.conn, path, "acme", "checking")

    def test_bad_amounts(self):
        for bad in ("", "1.234", "$5", "1,000", "--1", "1e3"):
            with self.subTest(bad=bad):
                path = self.write("a.csv",
                                  f"Date,Description,Amount\n2024-01-01,X,\"{bad}\"\n")
                with self.assertRaisesRegex(ValueError, "line 2"):
                    import_csv(self.conn, path, "acme", "checking")

    def test_wrong_field_count(self):
        path = self.write("a.csv", "Date,Description,Amount\n2024-01-01,X\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            import_csv(self.conn, path, "acme", "checking")

    def test_line_number_counts_multiline_fields(self):
        path = self.write("a.csv",
                          "Date,Description,Amount\n"
                          "2024-01-01,\"two\nlines\",-1.00\n"
                          "2024-01-02,X,bad\n")
        with self.assertRaisesRegex(ValueError, r"line 4\b"):
            import_csv(self.conn, path, "acme", "checking")

    def test_wrong_header(self):
        path = self.write("a.csv", "Transaction Date,Payee,Debit,Credit\n")
        with self.assertRaisesRegex(ValueError, "line 1"):
            import_csv(self.conn, path, "acme", "checking")

    def test_blank_lines_ignored(self):
        path = self.write("a.csv", "Date,Description,Amount\n\n2024-01-01,X,-1\n\n")
        self.assertEqual(import_csv(self.conn, path, "acme", "checking"), (1, 0))

    def test_unknown_bank(self):
        path = self.write("a.csv", ACME)
        with self.assertRaises(ValueError):
            import_csv(self.conn, path, "nope", "checking")

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            import_csv(self.conn, self.tmp + "/missing.csv", "acme", "checking")


class ZenithTests(TempDirTestCase):
    def test_import(self):
        path = self.write("z.csv", ZENITH)
        self.assertEqual(import_csv(self.conn, path, "zenith", "card"), (3, 0))
        txs = db.list_transactions(self.conn)
        self.assertEqual(
            [(t["date"], t["description"], t["amount"]) for t in txs],
            [("2024-01-15", "Rent", -123456),
             ("2024-01-16", "Refund", 2000),
             ("2024-01-17", "Big Store", -9900)],
        )

    def test_reimport(self):
        path = self.write("z.csv", ZENITH)
        import_csv(self.conn, path, "zenith", "card")
        self.assertEqual(import_csv(self.conn, path, "zenith", "card"), (0, 3))

    def test_neither_or_both_debit_credit(self):
        for debit, credit in (("", ""), ("1.00", "2.00")):
            with self.subTest(debit=debit, credit=credit):
                path = self.write("z.csv",
                                  "Transaction Date,Payee,Debit,Credit\n"
                                  "01/01/2024,OK,1.00,\n"
                                  f"01/02/2024,X,{debit},{credit}\n")
                with self.assertRaisesRegex(ValueError, r"line 3\b"):
                    import_csv(self.conn, path, "zenith", "card")
                self.assertEqual(db.list_transactions(self.conn), [])

    def test_bad_date(self):
        for bad in ("2024-01-01", "13/01/2024", "02/30/2024"):
            with self.subTest(bad=bad):
                path = self.write("z.csv",
                                  f"Transaction Date,Payee,Debit,Credit\n{bad},X,1,\n")
                with self.assertRaisesRegex(ValueError, "line 2"):
                    import_csv(self.conn, path, "zenith", "card")

    def test_bad_amount(self):
        for bad in ("$1,23", "abc", "1.2.3", "-5"):
            with self.subTest(bad=bad):
                path = self.write("z.csv",
                                  "Transaction Date,Payee,Debit,Credit\n"
                                  f"01/01/2024,X,\"{bad}\",\n")
                with self.assertRaisesRegex(ValueError, "line 2"):
                    import_csv(self.conn, path, "zenith", "card")
