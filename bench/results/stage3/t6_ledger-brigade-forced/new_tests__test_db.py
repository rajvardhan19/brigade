import os
import sqlite3
import tempfile
import unittest

from ledger import db


def insert(conn, account, date, description, amount, category=None,
           source=None):
    cur = conn.execute(
        "INSERT INTO transactions"
        " (account, date, description, amount, category, category_source)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (account, date, description, amount, category, source))
    conn.commit()
    return cur.lastrowid


class SchemaTest(unittest.TestCase):
    def test_creates_tables(self):
        conn = db.connect(":memory:")
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"transactions", "rules", "budgets"} <= names)

    def test_transaction_columns(self):
        conn = db.connect(":memory:")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(transactions)")]
        self.assertEqual(cols, ["id", "account", "date", "description",
                                "amount", "category", "category_source"])

    def test_rules_priority_default_and_budget_pk(self):
        conn = db.connect(":memory:")
        conn.execute("INSERT INTO rules (category, contains) VALUES ('A', 'x')")
        self.assertEqual(
            conn.execute("SELECT priority FROM rules").fetchone()[0], 0)
        conn.execute(
            "INSERT INTO budgets (category, month, amount) VALUES ('A', '2024-01', 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO budgets (category, month, amount)"
                         " VALUES ('A', '2024-01', 2)")

    def test_rows_are_tuples(self):
        conn = db.connect(":memory:")
        self.assertIsNone(conn.row_factory)

    def test_reconnect_keeps_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.db")
            conn = db.connect(path)
            insert(conn, "checking", "2024-01-05", "Coffee", -350)
            conn.close()
            conn = db.connect(path)
            rows = db.list_transactions(conn)
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"], "Coffee")
        self.assertEqual(rows[0]["amount"], -350)


class ListTransactionsTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_empty(self):
        self.assertEqual(db.list_transactions(self.conn), [])

    def test_exact_keys_and_category_none(self):
        insert(self.conn, "checking", "2024-01-05", "Coffee", -350)
        insert(self.conn, "checking", "2024-01-06", "Lunch", -1200,
               "Food", "rule")
        rows = db.list_transactions(self.conn)
        for row in rows:
            self.assertEqual(set(row), {"id", "account", "date",
                                        "description", "amount", "category"})
        self.assertIsNone(rows[0]["category"])
        self.assertEqual(rows[1]["category"], "Food")
        self.assertIsInstance(rows[0]["amount"], int)

    def test_ordering_date_then_id(self):
        a = insert(self.conn, "checking", "2024-02-01", "Later", -1)
        b = insert(self.conn, "checking", "2024-01-15", "Tie one", -2)
        c = insert(self.conn, "savings", "2024-01-15", "Tie two", 3)
        d = insert(self.conn, "checking", "2023-12-31", "Earliest", 4)
        ids = [r["id"] for r in db.list_transactions(self.conn)]
        self.assertEqual(ids, [d, b, c, a])

    def test_account_filter(self):
        a = insert(self.conn, "checking", "2024-01-02", "A", -1)
        insert(self.conn, "savings", "2024-01-01", "B", 2)
        c = insert(self.conn, "checking", "2024-01-01", "C", -3)
        rows = db.list_transactions(self.conn, account="checking")
        self.assertEqual([r["id"] for r in rows], [c, a])
        self.assertTrue(all(r["account"] == "checking" for r in rows))
        self.assertEqual(db.list_transactions(self.conn, account="none"), [])


if __name__ == "__main__":
    unittest.main()
