import os
import shutil
import tempfile
import unittest

from ledger import db


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.db_path = os.path.join(self.tmp, "ledger.db")
        self.conn = db.connect(self.db_path)
        self.addCleanup(self.conn.close)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(text)
        return path

    def add_tx(self, date, description, amount, account="checking"):
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO transactions (account, date, description, amount)"
                " VALUES (?, ?, ?, ?)",
                (account, date, description, amount),
            )
        return cur.lastrowid
