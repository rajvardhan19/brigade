import unittest

from ledger.money import format_cents, parse_cents


class MoneyTests(unittest.TestCase):
    def test_parse(self):
        cases = {"-12.50": -1250, "12": 1200, "$1,234.56": 123456, "0.05": 5,
                 "-$3.00": -300, " 7.1 ": 710, "1,000,000": 100000000}
        for text, cents in cases.items():
            self.assertEqual(parse_cents(text), cents, text)

    def test_parse_bad(self):
        for text in ["", "abc", "1.234", "1,23.00", "1..2", "$", "12a", "1e3", "nan"]:
            with self.assertRaises(ValueError, msg=text):
                parse_cents(text)

    def test_format(self):
        self.assertEqual(format_cents(12345), "123.45")
        self.assertEqual(format_cents(-1000), "-10.00")
        self.assertEqual(format_cents(-5), "-0.05")
        self.assertEqual(format_cents(0), "0.00")
        self.assertEqual(format_cents(None), "-")
