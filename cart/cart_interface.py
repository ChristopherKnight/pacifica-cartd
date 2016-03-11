#!/usr/bin/python
"""Class for the cart interface.  Allows API to file interactions"""
import json
import os
from sys import stderr
from tarfile import TarFile
import doctest
import cart.cart_interface_responses as cart_interface_responses
from cart.tasks import stage_files
from cart.cart_utils import Cartutils


BLOCK_SIZE = 1<<20

class CartInterfaceError(Exception):
    """
    CartInterfaceError - basic exception class for this module.
    Will be used to throw exceptions up to the top level of the application
    >>> CartInterfaceError()
    CartInterfaceError()
    """
    pass

def fix_cart_uid(uid):
    """Removes / from front of cart_uid

    Doc Tests

    >>> fix_cart_uid('test/')
    'test'
    >>> fix_cart_uid('test')
    'test'

    """
    if os.path.isabs(uid):
        uid = uid[1:]
    return uid

def is_valid_uid(uid):
    """checks to see if the uid is valid before using it

    Doc Tests

    >>> is_valid_uid('3434')
    'True'
    >>> is_valid_uid(None)
    'False'
    >>> is_valid_uid("")
    'False'

    """
    if not uid:
        return False
    if uid == "":
        return False

    return True


class CartGenerator(object):
    """Defines the methods that can be used for cart request types
    doctest for the cart generator class
    HPSS Doc Tests
    """
    def __init__(self):
        self._response = None

    def get(self, env, start_response):
        """Download the tar file created by the cart"""
        resp = cart_interface_responses.Responses()
        uid = fix_cart_uid(env['PATH_INFO'])
        is_valid = is_valid_uid(uid)
        if not is_valid:
            self._response = resp.invalid_uid_error_response(
                start_response, uid)
            return self.return_response()
        #get the bundle path if available
        cart_utils = Cartutils()
        cart_path = cart_utils.available_cart(uid)
        if not cart_path:
            #cart not ready
            self._response = resp.unready_cart(start_response)
            return self.return_response()
        else:
            if os.path.isdir(cart_path):
                #give back bundle here
                stderr.flush()
                try:
                    #want to stream the tar file out
                    (rpipe, wpipe) = os.pipe()
                    cpid = os.fork()
                    if cpid == 0:
                        # we are the child process
                        #write the data to the pipe
                        os.close(rpipe)
                        wfd = os.fdopen(wpipe, "wb")
                        mytar = TarFile.open(fileobj=wfd, mode='w|')
                        mytar.add(cart_path, arcname=uid)
                        mytar.close()
                        # pylint: disable=protected-access
                        os._exit(0)
                        # pylint: enable=protected-access
                    # we are the parent
                    os.close(wpipe)
                    #open the pipe as a file
                    rfd = os.fdopen(rpipe, "rb")
                    start_response('200 OK', [('Content-Type',
                                               'application/octet-stream')])
                    if 'wsgi.file_wrapper' in env:
                        return env['wsgi.file_wrapper'](rfd, BLOCK_SIZE)
                    return iter(lambda: rfd.read(BLOCK_SIZE), '')
                except IOError:
                    self._response = resp.bundle_doesnt_exist(start_response)
            else:
                self._response = resp.bundle_doesnt_exist(start_response)
                return self.return_response()


        return self.return_response()

    def status(self, env, start_response):
        """Get the status of a carts tar file"""
        resp = cart_interface_responses.Responses()
        uid = fix_cart_uid(env['PATH_INFO'])
        is_valid = is_valid_uid(uid)
        if not is_valid:
            self._response = resp.invalid_uid_error_response(
                start_response, uid)
            return self.return_response()

        cart_utils = Cartutils()
        status = cart_utils.cart_status(uid)
        self._response = resp.cart_status_response(start_response, status)
        return self.return_response()

    def stage(self, env, start_response):
        """Get all the files locally and bundled"""
        resp = cart_interface_responses.Responses()
        try:
            request_body_size = int(env.get('CONTENT_LENGTH', 0))
        except ValueError:
            request_body_size = 0

        try:
            request_body = env['wsgi.input'].read(request_body_size)
            data = json.loads(request_body)
            file_ids = data['fileids']
        except IOError:
            # is exception is probably from the read()
            self._response = resp.json_stage_error_response(start_response)
            return self.return_response()
        except ValueError:
            self._response = resp.json_stage_error_response(start_response)
            return self.return_response()

        uid = fix_cart_uid(env['PATH_INFO'])
        is_valid = is_valid_uid(uid)
        if not is_valid:
            self._response = resp.invalid_uid_error_response(
                start_response, uid)
            return self.return_response()

        stage_files.delay(file_ids, uid)
        self._response = resp.cart_proccessing_response(start_response)
        return self.return_response()

    def delete_cart(self, env, start_response):
        """Delete a cart that has been created"""
        resp = cart_interface_responses.Responses()
        uid = fix_cart_uid(env['PATH_INFO'])
        is_valid = is_valid_uid(uid)
        if not is_valid:
            self._response = resp.invalid_uid_error_response(
                start_response, uid)
            return self.return_response()

        cart_utils = Cartutils()
        message = cart_utils.remove_cart(uid)
        self._response = resp.cart_delete_response(start_response, message)
        return self.return_response()

    def return_response(self):
        """Prints all responses in a nice fashion"""
        return json.dumps(self._response, sort_keys=True, indent=4)


    def pacifica_cartinterface(self, env, start_response):
        """Parses request method type"""
        try:
            if env['REQUEST_METHOD'] == 'GET':
                return self.get(env, start_response)
            elif env['REQUEST_METHOD'] == 'HEAD':
                return self.status(env, start_response)
            elif env['REQUEST_METHOD'] == 'POST':
                return self.stage(env, start_response)
            elif env['REQUEST_METHOD'] == 'DELETE':
                return self.delete_cart(env, start_response)
            else:
                resp = cart_interface_responses.Responses()
                self._response = resp.unknown_request(start_response,
                                                      env['REQUEST_METHOD'])
            return self.return_response()
        except CartInterfaceError:
            #catching application errors
            #all exceptions set the return response
            #if the response is not set, set it as unknown
            if self._response is None:
                resp = cart_interface_responses.Responses()
                self._response = resp.unknown_exception(start_response)
            return self.return_response()


if __name__ == "__main__":
    doctest.testmod(verbose=True)
