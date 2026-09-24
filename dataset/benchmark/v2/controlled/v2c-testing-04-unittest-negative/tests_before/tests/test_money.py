import unittest

from fmt.money import money


class MoneyTest(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(money(250), "$2.50")
