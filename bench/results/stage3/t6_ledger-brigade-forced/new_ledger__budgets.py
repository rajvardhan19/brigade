"""Budgets and reports (spec part 4). 

- set_budget(conn, category, month, amount) sets a category's budget for a
  month in cents; month is "YYYY-MM". Setting it again replaces it.
- monthly_report(conn, month) returns a list of dicts with the keys category,
  spent, budget, remaining and over, for that month across all accounts.
  `spent` is the month's total spending in cents as a positive number (income
  is ignored). `budget` is None when no budget is set; `remaining` is budget
  minus spent, or None; `over` is True when spent is greater than budget.
  Uncategorized spending is reported under the category "Uncategorized". A
  category with a budget but no spending appears with spent 0. Rows are
  sorted by category name.
"""


import re

_MONTH_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])", re.ASCII)


def _check_month(month):
    if not isinstance(month, str) or not _MONTH_RE.fullmatch(month):
        raise ValueError("month must be YYYY-MM, got %r" % (month,))


def set_budget(conn, category, month, amount):
    """Set (or replace) a category's budget for a month, in cents."""
    _check_month(month)
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError("amount must be a non-negative integer (cents)")
    if amount > 2**63 - 1:
        raise ValueError("amount out of range: %r" % (amount,))
    conn.execute(
        "INSERT INTO budgets (category, month, amount) VALUES (?, ?, ?) "
        "ON CONFLICT(category, month) DO UPDATE SET amount = excluded.amount",
        (category, month, amount),
    )
    conn.commit()


def monthly_report(conn, month):
    """Return report rows for `month` ("YYYY-MM"), sorted by category."""
    _check_month(month)
    spent = {}
    for cat, total in conn.execute(
        "SELECT COALESCE(category, 'Uncategorized'), -SUM(amount) "
        "FROM transactions WHERE amount < 0 AND date LIKE ? "
        "GROUP BY COALESCE(category, 'Uncategorized')",
        (month + "-%",),
    ):
        spent[cat] = int(total)
    budgets = dict(
        conn.execute("SELECT category, amount FROM budgets WHERE month = ?", (month,))
    )
    rows = []
    for cat in sorted(set(spent) | set(budgets)):
        s = spent.get(cat, 0)
        b = budgets.get(cat)
        rows.append({
            "category": cat,
            "spent": s,
            "budget": b,
            "remaining": None if b is None else b - s,
            "over": b is not None and s > b,
        })
    return rows
