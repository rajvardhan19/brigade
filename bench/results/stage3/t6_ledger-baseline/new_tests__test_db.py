import os
import sqlite3

from ledger import db
from tests.helpers import TempDirTestCase


class DbTests(TempDirTestCase):
    def test_connect_returns_connection_and_creates_file(self):
        self.assertIsInstance(self.conn, sqlite3.Connection)
        self.assertTrue(os.path.exists(self.db_path))

    def test_empty_database(self):
        self.assertEqual(db.list_transactions(self.conn), [])

    def test_reconnect_keeps_data(self):
        self.add_tx("2024-01-01", "Coffee", -350)
        self.conn.close()
        conn2 = db.connect(self.db_path)
        self.addCleanup(conn2.close)
        txs = db.list_transactions(conn2)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["description"], "Coffee")

    def test_list_shape_and_order(self):
        b = self.add_tx("2024-01-02", "B", -200)
        a = self.add_tx("2024-01-01", "A", 100, account="savings")
        c = self.add_tx("2024-01-02", "C", -300)
        txs = db.list_transactions(self.conn)
        self.assertEqual([t["id"] for t in txs], [a, b, c])
        self.assertEqual(txs[0], {
            "id": a, "account": "savings", "date": "2024-01-01",
            "description": "A", "amount": 100, "category": None,
        })

    def test_list_filter_by_account(self):
        self.add_tx("2024-01-01", "A", 100, account="savings")
        self.add_tx("2024-01-01", "B", -100, account="checking")
        txs = db.list_transactions(self.conn, account="checking")
        self.assertEqual([t["description"] for t in txs], ["B"])
        self.assertEqual(db.list_transactions(self.conn, account="nope"), [])
