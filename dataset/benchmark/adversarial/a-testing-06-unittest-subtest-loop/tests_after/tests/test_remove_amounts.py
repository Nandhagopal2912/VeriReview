import unittest

from inventory.remove import remove_stock


class RemoveAmountTest(unittest.TestCase):
    def test_non_positive_amounts_are_rejected(self):
        for amount in (0, -3):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    remove_stock({"a": 10}, "a", amount)
