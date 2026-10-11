import unittest

from jobs.batches import split_batches


class SplitBatchesTest(unittest.TestCase):
    def test_exactly_one_hundred_items(self):
        batches = split_batches(list(range(100)))
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 100)
