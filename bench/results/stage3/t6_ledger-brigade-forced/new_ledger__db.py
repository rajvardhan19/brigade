"""Storage (spec part 1).

connect(path) opens or creates a SQLite database, creates the schema if it
doesn't exist, and returns a sqlite3.Connection. Connecting again to the same
file keeps the existing data.

list_transactions(conn, account=None) returns a list of dicts with the keys
id, account, date, description, amount (cents) and category (None if
uncategorized), ordered by date then id. With an account, only that
account's transactions.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL,
    category TEXT NULL,
    category_source TEXT NULL
        CHECK (category_source IS NULL OR category_source IN ('rule', 'manual'))
);
CREATE INDEX IF NOT EXISTS transactions_account_date
    ON transactions (account, date);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    contains TEXT NULL,
    pattern TEXT NULL,
    min_amount INTEGER NULL,
    max_amount INTEGER NULL,
    priority INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT NOT NULL,
    month TEXT NOT NULL,
    amount INTEGER NOT NULL,
    PRIMARY KEY (category, month)
);
"""

_COLUMNS = ("id", "account", "date", "description", "amount", "category")


def connect(path):
    """Open (or create) the database at `path` and ensure the schema exists.

    The returned connection has the default row_factory (rows are tuples).
    """
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def list_transactions(conn, account=None):
    """Return transactions as dicts, ordered by date then id."""
    sql = "SELECT {} FROM transactions".format(", ".join(_COLUMNS))
    params = ()
    if account is not None:
        sql += " WHERE account = ?"
        params = (account,)
    sql += " ORDER BY date, id"
    cur = conn.execute(sql, params)
    return [dict(zip(_COLUMNS, row)) for row in cur.fetchall()]
