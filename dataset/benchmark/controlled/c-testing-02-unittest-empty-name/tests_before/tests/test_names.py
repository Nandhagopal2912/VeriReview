import unittest

from people.names import greeting


class GreetingTest(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(greeting("Ada"), "Hello, Ada!")
