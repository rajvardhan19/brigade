"""Budgets and monthly reports."""

import re

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
UNCATEGORIZED = "Uncategorized"


def _check_month(month):
    if not isinstance(month, str) or not _MONTH.match(month):
        raise ValueError(f"malformed month {month!r}, expected YYYY-MM")


def set_budget(conn, category, month, amount):
    """Set (or replace) a category's budget for a month, in cents."""
    _check_month(month)
    if not category:
        raise ValueError("a budget needs a category")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValueError("budget amount must be an integer number of cents")
    with conn:
        conn.execute(
            "INSERT INTO budgets (category, month, amount) VALUES (?, ?, ?)"
            " ON CONFLICT (category, month) DO UPDATE SET amount = excluded.amount",
            (category, month, amount),
        )


def monthly_report(conn, month):
    """Per-category spending vs. budget for *month* across all accounts."""
    _check_month(month)
    spent = {}
    for category, total in conn.execute(
        "SELECT COALESCE(category, ?), -SUM(amount) FROM transactions"
        " WHERE amount < 0 AND substr(date, 1, 7) = ?"
        " GROUP BY COALESCE(category, ?)",
        (UNCATEGORIZED, month, UNCATEGORIZED),
    ):
        spent[category] = total
    budgets = dict(
        conn.execute(
            "SELECT category, amount FROM budgets WHERE month = ?", (month,)
        ).fetchall()
    )
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
