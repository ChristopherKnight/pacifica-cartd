"""
File used to unit test the pacifica_cart tasks.
"""
import os
import unittest
from types import MethodType
import mock
import requests
from playhouse.test_utils import test_database
from peewee import SqliteDatabase
from cart.cart_orm import Cart, File
from cart.tasks import stage_file_task, status_file_task
from cart.archive_requests import ArchiveRequests
from cart.cart_utils import Cartutils
import cart.cart_orm

class TestCartTasks(unittest.TestCase):
    """
    Contains tests for tasks that dont need all services stood up
    """
    @mock.patch.object(ArchiveRequests, 'stage_file')
    def test_bad_stage(self, mock_stage_file):
        """test the bad stage of a archive file"""
        with test_database(SqliteDatabase(':memory:'), (Cart, File)):
            test_cart = Cart.create(cart_uid='1', status='staging')
            test_file = File.create(cart=test_cart, file_name='1.txt',
                                    bundle_path='/tmp/1/1.txt')
            def fake_database_connect(cls):
                """dont error with connect"""
                return cls

            def fake_database_close(cls):
                """dont actually close"""
                return cls
            cart.cart_orm.CartBase.database_connect = MethodType(fake_database_connect, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.database_close = MethodType(fake_database_close, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.throw_error = False
            mock_stage_file.side_effect = requests.exceptions.RequestException(mock.Mock(status=500), 'Error')
            file_id = test_file.id
            stage_file_task(file_id)
            cart_file = File.get(File.id == file_id)
            status = cart_file.status
            self.assertEqual(status, 'error')

    @mock.patch.object(ArchiveRequests, 'status_file')
    @mock.patch.object(ArchiveRequests, 'stage_file')
    def test_bad_status(self, mock_stage_file, mock_status_file):
        """test the bad status of a archive file"""
        with test_database(SqliteDatabase(':memory:'), (Cart, File)):
            test_cart = Cart.create(cart_uid='1', status='staging')
            test_file = File.create(cart=test_cart, file_name='1.txt',
                                    bundle_path='/tmp/1/1.txt')
            def fake_database_connect(cls):
                """dont error with connect"""
                return cls

            def fake_database_close(cls):
                """dont actually close"""
                return cls
            cart.cart_orm.CartBase.database_connect = MethodType(fake_database_connect, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.database_close = MethodType(fake_database_close, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.throw_error = False
            mock_stage_file.return_value = True
            mock_status_file.side_effect = requests.exceptions.RequestException(mock.Mock(status=500), 'Error')
            file_id = test_file.id
            status_file_task(file_id)
            cart_file = File.get(File.id == file_id)
            status = cart_file.status
            self.assertEqual(status, 'error')

    @mock.patch.object(os, 'utime')
    @mock.patch.object(ArchiveRequests, 'pull_file')
    @mock.patch.object(ArchiveRequests, 'status_file')
    @mock.patch.object(ArchiveRequests, 'stage_file')
    def test_bad_pull(self, mock_stage_file, mock_status_file, mock_pull_file, mock_utime):
        """test the bad pull of a archive file"""
        with test_database(SqliteDatabase(':memory:'), (Cart, File)):
            test_cart = Cart.create(cart_uid='1', status='staging')
            test_file = File.create(cart=test_cart, file_name='1.txt',
                                    bundle_path='/tmp/1/1.txt')
            def fake_database_connect(cls):
                """dont error with connect"""
                return cls

            def fake_database_close(cls):
                """dont actually close"""
                return cls
            cart.cart_orm.CartBase.database_connect = MethodType(fake_database_connect, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.database_close = MethodType(fake_database_close, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.throw_error = False
            mock_stage_file.return_value = True
            mock_status_file.return_value = """{
                            "bytes_per_level": "(10L, 0L)",
                            "ctime": "1444629567",
                            "file": "1.txt",
                            "file_storage_media": "disk",
                            "filesize": "10",
                            "message": "File was found",
                            "mtime": "1444937154"
                            }"""
            mock_pull_file.side_effect = requests.exceptions.RequestException(mock.Mock(status=500), 'Error')
            mock_utime.return_value = True
            file_id = test_file.id
            stage_file_task(file_id)
            cart_file = File.get(File.id == file_id)
            status = cart_file.status
            self.assertEqual(status, 'error')

    @mock.patch.object(Cartutils, 'check_file_size_needed')
    @mock.patch.object(ArchiveRequests, 'status_file')
    @mock.patch.object(ArchiveRequests, 'stage_file')
    def test_bad_size_needed(self, mock_stage_file, mock_status_file, mock_check_file):
        """test a error in check_file_size_needed"""
        with test_database(SqliteDatabase(':memory:'), (Cart, File)):
            test_cart = Cart.create(cart_uid='1', status='staging')
            test_file = File.create(cart=test_cart, file_name='1.txt',
                                    bundle_path='/tmp/1/1.txt')
            def fake_database_connect(cls):
                """dont error with connect"""
                return cls

            def fake_database_close(cls):
                """dont actually close"""
                return cls
            cart.cart_orm.CartBase.database_connect = MethodType(fake_database_connect, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.database_close = MethodType(fake_database_close, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.throw_error = False
            mock_stage_file.return_value = True
            mock_status_file.return_value = """{
                            "bytes_per_level": "(10L, 0L)",
                            "ctime": "1444629567",
                            "file": "1.txt",
                            "file_storage_media": "disk",
                            "filesize": "10",
                            "message": "File was found",
                            "mtime": "1444937154"
                            }"""
            mock_check_file.return_value = -1
            file_id = test_file.id
            stage_file_task(file_id)
            cart_file = File.get(File.id == file_id)
            status = cart_file.status
            self.assertEqual(status, 'staging')

    @mock.patch.object(Cartutils, 'check_file_ready_pull')
    @mock.patch.object(ArchiveRequests, 'status_file')
    @mock.patch.object(ArchiveRequests, 'stage_file')
    def test_bad_ready_to_pull(self, mock_stage_file, mock_status_file, mock_check_file):
        """test a error return from a file not ready to pull"""
        with test_database(SqliteDatabase(':memory:'), (Cart, File)):
            test_cart = Cart.create(cart_uid='1', status='staging')
            test_file = File.create(cart=test_cart, file_name='1.txt',
                                    bundle_path='/tmp/1/1.txt')
            def fake_database_connect(cls):
                """dont error with connect"""
                return cls

            def fake_database_close(cls):
                """dont actually close"""
                return cls
            cart.cart_orm.CartBase.database_connect = MethodType(fake_database_connect, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.database_close = MethodType(fake_database_close, cart.cart_orm.CartBase)
            cart.cart_orm.CartBase.throw_error = False
            mock_stage_file.return_value = True
            mock_status_file.return_value = """{
                            "bytes_per_level": "(10L, 0L)",
                            "ctime": "1444629567",
                            "file": "1.txt",
                            "file_storage_media": "disk",
                            "filesize": "10",
                            "message": "File was found",
                            "mtime": "1444937154"
                            }"""
            mock_check_file.return_value = -1
            file_id = test_file.id
            stage_file_task(file_id)
            cart_file = File.get(File.id == file_id)
            status = cart_file.status
            self.assertEqual(status, 'staging')
