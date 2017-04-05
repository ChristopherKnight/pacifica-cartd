"""
File used to unit test the pacifica_cart
"""
import os
from types import MethodType
import unittest
from json import loads, dumps
from tempfile import mkstemp, mkdtemp
from playhouse.test_utils import test_database
from peewee import SqliteDatabase
from cart.cart_orm import Cart, File
from cart.cart_interface import fix_cart_uid, is_valid_uid, CartGenerator, CartInterfaceError
from cart.cart_env_globals import VOLUME_PATH
from cart.celery import CART_APP

CART_APP.conf.CELERY_ALWAYS_EAGER = True

# there's a lot of testing with this class suckit pylint
#pylint: disable=too-many-public-methods
class TestCartInterface(unittest.TestCase):
    """
    Contains all the tests for the Cart Interface
    """
    endpoint_url = 'http://localhost:8080'
    def setUp(self):
        """Create a new sqlite3 db"""
        self.sqlite_db_path = mkstemp(suffix='.sqlite3')[1]
        self.sqlite_db = SqliteDatabase(self.sqlite_db_path)
    def tearDown(self):
        """Delete the sqlite3 db"""
        os.unlink(self.sqlite_db_path)
    def test_cart_int_get_no_file_fd(self):
        """Testing the cart interface get method w/o file_wrapper"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '200 OK')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/octet-stream')
        env = {
            'PATH_INFO': '/123',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            sample_cart = Cart()
            sample_cart.cart_uid = 123
            sample_cart.bundle_path = mkdtemp()
            sample_cart.status = 'ready'
            sample_cart.save(force_insert=True)
            self.sqlite_db.close()
            cgen = CartGenerator()
            tarfile_read = cgen.get(env, start_response)
            for buf in tarfile_read:
                self.assertTrue(len(buf) > 0)

    def test_cart_int_get(self):
        """Testing the cart interface get method"""
        saved_state = {}
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '200 OK')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/octet-stream')
        def file_wrapper(rfd, blksize):
            """stub for file_wrapper to do some checking"""
            self.assertEqual(blksize, 1<<20)
            self.assertEqual(type(rfd), file)
            saved_state['fd'] = rfd
            return iter(lambda: rfd.read(blksize), '')
        env = {
            'PATH_INFO': '/123',
            'wsgi.file_wrapper': file_wrapper,
            'QUERY_STRING' : 'filename=my_file.tar'
        }
        with test_database(self.sqlite_db, (Cart, File)):
            sample_cart = Cart()
            sample_cart.cart_uid = 123
            sample_cart.bundle_path = mkdtemp()
            sample_cart.status = 'ready'
            sample_cart.save(force_insert=True)
            self.sqlite_db.close()
            cgen = CartGenerator()
            tarfile_read = cgen.get(env, start_response)
            for buf in tarfile_read:
                self.assertTrue(len(buf) > 0)
            saved_state['fd'].close()

    def test_invalid_cart_uid(self):
        """Testing the cart interface get against not valid cart uid"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '400 Bad Request')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.get(env, start_response)
            self.assertEqual(loads(data)['message'], 'The uid was not valid')

    def test_not_valid_cart(self):
        """Testing the cart interface get against not ready cart"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '404 Not Found')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/123',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            sample_cart = Cart()
            sample_cart.cart_uid = 123
            sample_cart.bundle_path = mkstemp()
            sample_cart.status = 'ready'
            sample_cart.save(force_insert=True)
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.get(env, start_response)
            self.assertEqual(loads(data)['message'], 'The cart bundle does not exist')

    def test_not_ready_cart(self):
        """Testing the cart interface get against not ready cart"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '202 Accepted')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/123',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            sample_cart = Cart()
            sample_cart.cart_uid = 123
            sample_cart.bundle_path = mkdtemp()
            sample_cart.save(force_insert=True)
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.get(env, start_response)
            self.assertEqual(loads(data)['message'], 'The cart is not ready for download')

    def test_read_cart_ioerrror(self):
        """Testing the cart interface get against not ready cart"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '404 Not Found')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/123',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            sample_cart = Cart()
            sample_cart.cart_uid = 123
            sample_cart.bundle_path = mkdtemp()
            sample_cart.status = 'ready'
            sample_cart.save(force_insert=True)
            self.sqlite_db.close()
            cgen = CartGenerator()
            orig_fork = os.fork
            def bad_fork():
                """The get method trys to fork so replacing it with a method that fails.
                """
                raise IOError('failed to fork')
            os.fork = bad_fork
            data = cgen.get(env, start_response)
            self.assertEqual(loads(data)['message'], 'The cart bundle does not exist')
            os.fork = orig_fork

    def test_status_invalid_uid(self):
        """Testing the cart interface status"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '400 Bad Request')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.status(env, start_response)
            self.assertEqual(loads(data)['message'], 'The uid was not valid')

    def test_cart_int_stage_nojson(self):
        """Testing the cart interface stage bad json input"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '400 Bad Request')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        one_up_self = self
        #pylint: disable=too-few-public-methods
        class FakeReader(object):
            """fake reader class for wsgi.input"""
            sent_content = ''
            def read(self, size):
                """Fake out the wsgi.input object bits"""
                one_up_self.assertEqual(size, 0)
                return self.sent_content
        #pylint: enable=too-few-public-methods
        env = {
            'PATH_INFO': '/123',
            'CONTENT_LENGTH': 'blah',
            'QUERY_STRING' : '',
            'wsgi.input': FakeReader()
        }
        with test_database(self.sqlite_db, (Cart, File)):
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.stage(env, start_response)
            self.assertEqual(loads(data)['message'], 'JSON content could not be read')

    def test_cart_int_stage_invalid_uid(self):
        """Testing the cart interface stage invalid cart uid"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '400 Bad Request')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        one_up_self = self
        #pylint: disable=too-few-public-methods
        class FakeReader(object):
            """fake reader class for wsgi.input"""
            sent_content = {
                'fileids': [1]
            }
            def read(self, size):
                """Fake out the wsgi.input object bits"""
                one_up_self.assertEqual(size, len(dumps(self.sent_content)))
                return dumps(self.sent_content)
        #pylint: enable=too-few-public-methods
        env = {
            'PATH_INFO': '/',
            'CONTENT_LENGTH': len(dumps(FakeReader.sent_content)),
            'QUERY_STRING' : '',
            'wsgi.input': FakeReader()
        }
        with test_database(self.sqlite_db, (Cart, File)):
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.stage(env, start_response)
            self.assertEqual(loads(data)['message'], 'The uid was not valid')

    def test_cart_int_stage_ioerror(self):
        """Testing the cart interface stage"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '400 Bad Request')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        one_up_self = self
        #pylint: disable=too-few-public-methods
        class FakeReader(object):
            """fake reader class for wsgi.input"""
            size = 47
            def read(self, size):
                """Fake out the wsgi.input object bits"""
                one_up_self.assertEqual(size, self.size)
                raise IOError('failed to read')
        #pylint: enable=too-few-public-methods
        env = {
            'PATH_INFO': '/123',
            'CONTENT_LENGTH': FakeReader.size,
            'QUERY_STRING' : '',
            'wsgi.input': FakeReader()
        }
        with test_database(self.sqlite_db, (Cart, File)):
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.stage(env, start_response)
            self.assertEqual(loads(data)['message'], 'JSON content could not be read')

    def test_cart_int_delete(self):
        """Testing the cart interface delete"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '200 OK')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/123',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            sample_cart = Cart()
            sample_cart.cart_uid = 123
            sample_cart.bundle_path = mkdtemp()
            sample_cart.status = 'ready'
            sample_cart.save(force_insert=True)
            sample_cart.reload()
            path_to_files = os.path.join(VOLUME_PATH, str(sample_cart.id))
            os.makedirs(path_to_files)
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.delete_cart(env, start_response)
            self.assertEqual(loads(data)['message'], 'Cart Deleted Successfully')

    def test_delete_invalid_uid(self):
        """Testing the cart interface delete with invalid uid"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '400 Bad Request')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'PATH_INFO': '/',
            'QUERY_STRING' : ''
        }
        with test_database(self.sqlite_db, (Cart, File)):
            self.sqlite_db.close()
            cgen = CartGenerator()
            data = cgen.delete_cart(env, start_response)
            self.assertEqual(loads(data)['message'], 'The uid was not valid')

    def test_pacifica_cartinterface(self):
        """test pacifica cart interface"""
        ####
        # this is going to be tricky we need to override the methods we tested
        # above so we don't need to make an super test harness
        # used to validate start_response, not actually calling it so no coverage
        # Stubs out the response
        ####
        # pylint: disable=unused-argument
        def start_response(*args):  # pragma no cover
            """stub for start_response to do some checking"""
            pass
        # pylint: enable=unused-argument
        env = {
            'REQUEST_METHOD': '',
            'called_get': False,
            'called_status': False,
            'called_stage': False,
            'called_delete': False
        }
        def fake_get(other_self, env, other_start_response):
            """fake the get method"""
            self.assertTrue(not other_self is None)
            self.assertEqual(env['REQUEST_METHOD'], 'GET')
            self.assertEqual(start_response, other_start_response)
            env['called_get'] = True
            return 'this is get()'
        def fake_status(other_self, env, other_start_response):
            """fake the get method"""
            self.assertTrue(not other_self is None)
            self.assertEqual(env['REQUEST_METHOD'], 'HEAD')
            self.assertEqual(start_response, other_start_response)
            env['called_status'] = True
            return 'this is status()'
        def fake_stage(other_self, env, other_start_response):
            """fake the stage method"""
            self.assertTrue(not other_self is None)
            self.assertEqual(env['REQUEST_METHOD'], 'POST')
            self.assertEqual(start_response, other_start_response)
            env['called_stage'] = True
            return 'this is stage()'
        def fake_delete(other_self, env, other_start_response):
            """fake the delete method"""
            self.assertTrue(not other_self is None)
            self.assertEqual(env['REQUEST_METHOD'], 'DELETE')
            self.assertEqual(start_response, other_start_response)
            env['called_delete'] = True
            return 'this is delete()'
        cgen = CartGenerator()
        cgen.get = MethodType(fake_get, cgen)
        cgen.status = MethodType(fake_status, cgen)
        cgen.stage = MethodType(fake_stage, cgen)
        cgen.delete_cart = MethodType(fake_delete, cgen)
        for method, message in [('GET', 'this is get()'),
                                ('HEAD', 'this is status()'),
                                ('POST', 'this is stage()'),
                                ('DELETE', 'this is delete()')]:
            env['REQUEST_METHOD'] = method
            chk_message = cgen.pacifica_cartinterface(env, start_response)
            self.assertEqual(message, chk_message)
        self.assertTrue(env['called_get'])
        self.assertTrue(env['called_stage'])
        self.assertTrue(env['called_status'])
        self.assertTrue(env['called_delete'])

    def test_pacifica_ci_throw_error(self):
        """test pacifica cart interface throw exception"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '500 Internal Server Error')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        def fake_get(other_self, env, other_start_response):
            """fake the get method"""
            self.assertTrue(not other_self is None)
            self.assertEqual(env['REQUEST_METHOD'], 'GET')
            self.assertEqual(start_response, other_start_response)
            raise CartInterfaceError('This is an error')
        env = {
            'REQUEST_METHOD': 'GET',
            'QUERY_STRING' : ''
        }
        cgen = CartGenerator()
        cgen.get = MethodType(fake_get, cgen)
        message = cgen.pacifica_cartinterface(env, start_response)
        self.assertEqual(loads(message)['message'], 'Unknown Exception Occured')

    def test_pacifica_ci_bad_request(self):
        """test pacifica cart interface bad request method"""
        def start_response(*args):
            """stub for start_response to do some checking"""
            self.assertEqual(args[0], '501 Not Implemented')
            self.assertEqual(args[1][0][0], 'Content-Type')
            self.assertEqual(args[1][0][1], 'application/json')
        env = {
            'REQUEST_METHOD': 'IMNOTREAL',
            'QUERY_STRING' : ''
        }
        cgen = CartGenerator()
        message = cgen.pacifica_cartinterface(env, start_response)
        self.assertEqual(loads(message)['message'], 'Unknown request method')

    def test_fix_cart_uid(self):
        """ Testing the create filepath cleanup"""
        path = fix_cart_uid('test/')
        self.assertEqual(path, 'test/')
        path = fix_cart_uid('test')
        self.assertEqual(path, 'test')
        path = fix_cart_uid('/test')
        self.assertEqual(path, 'test')

    def test_is_valid_uid(self):
        """ Testing if the passed guids are valid"""
        valid = is_valid_uid('3434')
        self.assertEqual(valid, True)
        valid = is_valid_uid(None)
        self.assertEqual(valid, False)
        valid = is_valid_uid('')
        self.assertEqual(valid, False)
        valid = is_valid_uid('foo')
        self.assertEqual(valid, True)
        valid = is_valid_uid('')
        self.assertEqual(valid, False)
