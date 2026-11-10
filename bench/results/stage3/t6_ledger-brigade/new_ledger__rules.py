"""Categorization rules."""
import re


def add_rule(conn, category, contains=None, pattern=None, min_amount=None,
             max_amount=None, priority=0):
    if not category:
        raise ValueError("a rule needs a category")
    if not contains and not pattern:
        raise ValueError("a rule needs at least one of contains and pattern")
    if pattern:
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError("invalid pattern %r: %s" % (pattern, e))
    for name, v in (("min_amount", min_amount), ("max_amount", max_amount)):
        if v is not None and (not isinstance(v, int) or isinstance(v, bool)):
            raise ValueError("%s must be an integer number of cents" % name)
    with conn:
        cur = conn.execute(
            "INSERT INTO rules (category, contains, pattern, min_amount, max_amount, priority)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (category, contains or None, pattern or None, min_amount, max_amount, priority))
    return cur.lastrowid


class _Rule:
    def __init__(self, row):
        self.id = row["id"]
        self.category = row["category"]
        self.contains = row["contains"].lower() if row["contains"] else None
        self.regex = re.compile(row["pattern"], re.IGNORECASE) if row["pattern"] else None
        self.min_amount = row["min_amount"]
        self.max_amount = row["max_amount"]

    def matches(self, description, amount):
        if self.contains is not None and self.contains not in description.lower():
            return False
        if self.regex is not None and not self.regex.search(description):
            return False
        size = abs(amount)
        if self.min_amount is not None and size < self.min_amount:
            return False
        if self.max_amount is not None and size > self.max_amount:
            return False
        return True


def _load_rules(conn):
    rows = conn.execute("SELECT * FROM rules ORDER BY priority DESC, id ASC")
    return [_Rule(r) for r in rows]


def categorize(conn, recategorize=False):
    """Apply rules; return the number of transactions whose category changed."""
    rules = _load_rules(conn)
    if not rules:
        return 0
    sql = "SELECT id, description, amount, category FROM transactions WHERE "
    if recategorize:
        sql += "category IS NULL OR category_source = 'rule'"
    else:
        sql += "category IS NULL"
    changed = 0
    with conn:
        for tx in conn.execute(sql).fetchall():
            for rule in rules:
                if rule.matches(tx["description"], tx["amount"]):
                    if rule.category != tx["category"]:
                        conn.execute(
                            "UPDATE transactions SET category = ?, category_source = 'rule'"
                            " WHERE id = ?", (rule.category, tx["id"]))
                        changed += 1
                    break
    return changed


def set_category(conn, transaction_id, category):
    """Set a category by hand; categorize() never overrides it."""
    with conn:
        cur = conn.execute(
            "UPDATE transactions SET category = ?, category_source = 'manual' WHERE id = ?",
            (category, transaction_id))
    if cur.rowcount == 0:
        raise ValueError("no transaction with id %r" % (transaction_id,))
