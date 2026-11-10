from helpers import LedgerTestCase

from ledger import db


class DbTests(LedgerTestCase):
    def test_empty(self):
        self.assertEqual(db.list_transactions(self.conn), [])

    def test_list_order_and_keys(self):
        b = self.add_tx("2024-02-01", "B", -100)
        a = self.add_tx("2024-01-01", "A", 200, account="savings")
        c = self.add_tx("2024-02-01", "C", -300)
        txs = db.list_transactions(self.conn)
        self.assertEqual([t["id"] for t in txs], [a, b, c])
        self.assertEqual(txs[0], {"id": a, "account": "savings", "date": "2024-01-01",
                                  "description": "A", "amount": 200, "category": None})

    def test_filter_account(self):
        self.add_tx("2024-01-01", "A", 1, account="x")
        self.add_tx("2024-01-02", "B", 2, account="y")
        self.assertEqual([t["description"] for t in db.list_transactions(self.conn, "y")], ["B"])

    def test_reconnect_keeps_data(self):
        self.add_tx("2024-01-01", "A", 1)
        self.conn.close()
        self.conn = db.connect(self.db_path)
        self.assertEqual(len(db.list_transactions(self.conn)), 1)
