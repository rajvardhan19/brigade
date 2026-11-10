"""Categorization rules (spec part 3). 

- add_rule(conn, category, contains=None, pattern=None, min_amount=None,
  max_amount=None, priority=0) stores a rule and returns its id. A rule needs
  at least one of `contains` and `pattern`; otherwise raise ValueError.
- A rule matches a transaction when every condition it has holds: `contains`
  is a case-insensitive substring of the description; `pattern` is a
  case-insensitive regular expression found anywhere in the description
  (re.search); `min_amount` and `max_amount` are cents, compared inclusively
  with the absolute value of the amount.
- categorize(conn, recategorize=False) applies the rules and returns the
  number of transactions whose category changed. When several rules match,
  the highest priority wins; on a tie, the rule added first wins. By default
  only uncategorized transactions are touched; with recategorize=True,
  categories that rules assigned earlier are recomputed too. Transactions
  that no rule matches are left as they are.
- set_category(conn, transaction_id, category) sets a category by hand.
  Hand-set categories are never changed by categorize, even with
  recategorize=True.
"""


import re


def add_rule(conn, category, contains=None, pattern=None, min_amount=None,
             max_amount=None, priority=0):
    """Store a rule and return its id."""
    if not contains and not pattern:
        raise ValueError("a rule needs 'contains' or 'pattern'")
    if pattern:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError("invalid pattern %r: %s" % (pattern, exc))
    for name, val in (("priority", priority), ("min_amount", min_amount),
                      ("max_amount", max_amount)):
        if val is not None and (
                not isinstance(val, int) or not -2**63 <= val <= 2**63 - 1):
            raise ValueError("%s out of range: %r" % (name, val))
    if (min_amount is not None and max_amount is not None
            and min_amount > max_amount):
        raise ValueError("min_amount is greater than max_amount")
    cur = conn.execute(
        "INSERT INTO rules (category, contains, pattern, min_amount, "
        "max_amount, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (category, contains or None, pattern or None, min_amount,
         max_amount, priority))
    conn.commit()
    return cur.lastrowid


def _matches(rule, description, amount):
    _id, _cat, contains, pattern, min_amount, max_amount, _prio = rule
    if contains and contains.casefold() not in description.casefold():
        return False
    if pattern and not re.search(pattern, description, re.IGNORECASE):
        return False
    size = abs(amount)
    if min_amount is not None and size < min_amount:
        return False
    if max_amount is not None and size > max_amount:
        return False
    return True


def categorize(conn, recategorize=False):
    """Apply rules; return the number of transactions whose category changed."""
    rules = conn.execute(
        "SELECT id, category, contains, pattern, min_amount, max_amount, "
        "priority FROM rules ORDER BY priority DESC, id ASC").fetchall()
    where = "category_source IS NULL"
    if recategorize:
        where += " OR category_source = 'rule'"
    candidates = conn.execute(
        "SELECT id, description, amount, category, category_source "
        "FROM transactions WHERE " + where).fetchall()
    changed = 0
    for tid, description, amount, category, source in candidates:
        for rule in rules:
            if _matches(rule, description, amount):
                new = rule[1]
                if source is None or new != category:
                    conn.execute(
                        "UPDATE transactions SET category = ?, "
                        "category_source = 'rule' WHERE id = ?", (new, tid))
                    changed += 1
                break
    conn.commit()
    return changed


def set_category(conn, transaction_id, category):
    """Set a transaction's category by hand (category_source='manual')."""
    cur = conn.execute(
        "UPDATE transactions SET category = ?, category_source = 'manual' "
        "WHERE id = ?", (category, transaction_id))
    if cur.rowcount == 0:
        conn.rollback()
        raise ValueError("no transaction with id %r" % (transaction_id,))
    conn.commit()
