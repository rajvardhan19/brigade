"""Budgets and monthly reports."""
import re

UNCATEGORIZED = "Uncategorized"
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _check_month(month):
    if not isinstance(month, str) or not _MONTH.match(month):
        raise ValueError("month must be YYYY-MM, got %r" % (month,))


def set_budget(conn, category, month, amount):
    _check_month(month)
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise ValueError("budget amount must be an integer number of cents")
    with conn:
        conn.execute(
            "INSERT INTO budgets (category, month, amount) VALUES (?, ?, ?)"
            " ON CONFLICT(category, month) DO UPDATE SET amount = excluded.amount",
            (category, month, amount))


def monthly_report(conn, month):
    _check_month(month)
    spent = {
        row[0]: -row[1]
        for row in conn.execute(
            "SELECT COALESCE(category, ?), SUM(amount) FROM transactions"
            " WHERE amount < 0 AND substr(date, 1, 7) = ?"
            " GROUP BY COALESCE(category, ?)",
            (UNCATEGORIZED, month, UNCATEGORIZED))
    }
    budgets = dict(conn.execute(
        "SELECT category, amount FROM budgets WHERE month = ?", (month,)).fetchall())
    report = []
    for category in sorted(set(spent) | set(budgets)):
        s = spent.get(category, 0)
        b = budgets.get(category)
        report.append({
            "category": category,
            "spent": s,
            "budget": b,
            "remaining": None if b is None else b - s,
            "over": b is not None and s > b,
        })
    return report
