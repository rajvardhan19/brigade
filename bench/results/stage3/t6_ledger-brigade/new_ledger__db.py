"""SQLite storage for ledger."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL,
    category TEXT,
    category_source TEXT CHECK (category_source IN ('rule', 'manual'))
);
CREATE INDEX IF NOT EXISTS idx_tx_account_date ON transactions(account, date);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    contains TEXT,
    pattern TEXT,
    min_amount INTEGER,
    max_amount INTEGER,
    priority INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT NOT NULL,
    month TEXT NOT NULL,
    amount INTEGER NOT NULL,
    PRIMARY KEY (category, month)
);
"""


def connect(path):
    """Open (or create) the database at path and ensure the schema exists."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def list_transactions(conn, account=None):
    sql = "SELECT id, account, date, description, amount, category FROM transactions"
    params = ()
    if account is not None:
        sql += " WHERE account = ?"
        params = (account,)
    sql += " ORDER BY date, id"
    return [
        {k: row[k] for k in ("id", "account", "date", "description", "amount", "category")}
        for row in conn.execute(sql, params)
    ]
