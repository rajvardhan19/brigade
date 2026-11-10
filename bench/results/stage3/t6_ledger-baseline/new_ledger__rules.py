"""Rule-based categorization."""

import re


def add_rule(conn, category, contains=None, pattern=None, min_amount=None,
             max_amount=None, priority=0):
    """Store a categorization rule and return its id."""
    if not category:
        raise ValueError("a rule needs a category")
    if contains is None and pattern is None:
        raise ValueError("a rule needs at least one of contains and pattern")
    if pattern is not None:
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"invalid pattern {pattern!r}: {e}") from None
    for name, value in (("min_amount", min_amount), ("max_amount", max_amount)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"{name} must be an integer number of cents")
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("priority must be an integer")
    with conn:
        cur = conn.execute(
            "INSERT INTO rules (category, contains, pattern, min_amount,"
            " max_amount, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (category, contains, pattern, min_amount, max_amount, priority),
        )
    return cur.lastrowid


class _Rule:
    def __init__(self, row):
        (self.id, self.category, contains, pattern,
         self.min_amount, self.max_amount, self.priority) = row
        self.contains = contains.casefold() if contains is not None else None
        self.regex = re.compile(pattern, re.IGNORECASE) if pattern is not None else None

    def matches(self, description, amount):
        if self.contains is not None and self.contains not in description.casefold():
            return False
        if self.regex is not None and not self.regex.search(description):
            return False
        magnitude = abs(amount)
        if self.min_amount is not None and magnitude < self.min_amount:
            return False
        if self.max_amount is not None and magnitude > self.max_amount:
            return False
        return True


def _load_rules(conn):
    rows = conn.execute(
        "SELECT id, category, contains, pattern, min_amount, max_amount, priority"
        " FROM rules ORDER BY priority DESC, id ASC"
    )
    return [_Rule(tuple(r)) for r in rows]


def categorize(conn, recategorize=False):
    """Apply rules; return the number of transactions whose category changed."""
    rules = _load_rules(conn)
    if not rules:
        return 0
    where = "category_source IS NULL"
    if recategorize:
        where = "(category_source IS NULL OR category_source = 'rule')"
    txs = conn.execute(
        f"SELECT id, description, amount, category FROM transactions WHERE {where}"
    ).fetchall()
    changed = 0
    with conn:
        for tx_id, desc, amount, current in txs:
            for rule in rules:
                if rule.matches(desc, amount):
                    if rule.category != current:
                        conn.execute(
                            "UPDATE transactions SET category = ?,"
                            " category_source = 'rule' WHERE id = ?",
                            (rule.category, tx_id),
                        )
                        changed += 1
                    break
    return changed


def set_category(conn, transaction_id, category):
    """Set a transaction's category by hand; rules will never override it."""
    with conn:
        cur = conn.execute(
            "UPDATE transactions SET category = ?, category_source = ?"
            " WHERE id = ?",
            (category, "manual" if category is not None else None, transaction_id),
        )
    if cur.rowcount == 0:
        raise ValueError(f"no transaction with id {transaction_id}")
