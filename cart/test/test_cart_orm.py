#!/usr/bin/python
"""
This tests some of the cart orm class
"""
import unittest
import os
from tempfile import mkstemp
from types import MethodType
from playhouse.test_utils import test_database
from peewee import SqliteDatabase, OperationalError
from cart.cart_orm import database_setup, Cart, File
import cart.cart_orm

class TestCartOrm(unittest.TestCase):
    """
    Contains the cart orm tests
    """
    def setUp(self):
        """Create a new sqlite3 db"""
        self.sqlite_db_path = mkstemp(suffix='.sqlite3')[1]
        self.sqlite_db = SqliteDatabase(self.sqlite_db_path)

    def tearDown(self):
        """Delete the sqlite3 db"""
        os.unlink(self.sqlite_db_path)

    def test_cart_orm_db_setup(self):
        """call database_setup"""
        with test_database(self.sqlite_db, (Cart, File), create_tables=False):
            database_setup(2)
            self.assertTrue(Cart.table_exists())
            self.assertTrue(File.table_exists())

    def test_cart_orm_db_setup_error(self):
        """call database_setup"""
        def fake_database_connect(cls):
            """throw error during connect"""
            cls.throw_error = True
            raise OperationalError('Failing')
        cart.cart_orm.CartBase.orig_database_connect = cart.cart_orm.CartBase.database_connect
        cart.cart_orm.CartBase.database_connect = \
            MethodType(fake_database_connect, cart.cart_orm.CartBase)
        cart.cart_orm.CartBase.throw_error = False
        with test_database(self.sqlite_db, (Cart, File), create_tables=False):
            database_setup(2)
        self.assertTrue(cart.cart_orm.CartBase.throw_error)
