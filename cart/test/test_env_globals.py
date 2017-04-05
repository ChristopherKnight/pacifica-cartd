"""
File used to unit test the pacifica_cart
"""
import unittest
import os
import sys

class TestEnvGlobals(unittest.TestCase):
    """
    Contains the tests for the global config module
    """
    def test_set_logging(self):
        """test that logging gets set for debugging"""
        os.environ['DATABASE_LOGGING'] = 'True'
        import importlib
        # first delete the module from the loaded modules
        del sys.modules['cart.cart_env_globals']
        # then we import the module
        mod = importlib.import_module('cart.cart_env_globals')
        # make sure the LOGGER attribute in the module exists
        self.assertTrue(getattr(mod, 'LOGGER'))
