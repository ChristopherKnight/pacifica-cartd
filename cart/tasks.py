"""Module that contains all the amqp tasks that support the
cart infrastructure
"""

from __future__ import absolute_import
import os
import requests
from peewee import DoesNotExist
from cart.celery import CART_APP
from cart.cart_orm import Cart, File
from cart.cart_utils import Cartutils
from cart.archive_requests import ArchiveRequests


@CART_APP.task(ignore_result=True)
def create_cart(file_ids, uid):
    """Create the cart or update previous"""
    Cart.database_connect()
    mycart = Cart(cart_uid=uid, status='staging')
    mycart.save()
    stage_files.delay(file_ids, mycart.id)
    Cart.database_close()

@CART_APP.task(ignore_result=True)
def stage_files(file_ids, mycart_id):
    """Tell the files to be staged on the backend system """
    Cart.database_connect()
    #with update or new, need to add in files
    mycart = Cart.get(Cart.id == mycart_id)
    cart_utils = Cartutils()
    cart_utils.update_cart_files(mycart, file_ids)

    get_files_locally.delay(mycart.id)
    Cart.database_close()

@CART_APP.task(ignore_result=True)
def get_files_locally(cartid):
    """Pull the files to the local system from the backend """
    #tell each file to be pulled
    Cart.database_connect()
    for cart_file in File.select().where(File.cart == cartid):
        pull_file.delay(cart_file.id, False)
    Cart.database_close()



@CART_APP.task(ignore_result=True)
def pull_file(file_id, record_error):
    """Pull a file from the archive  """
    Cart.database_connect()
    try:
        cart_file = File.get(File.id == file_id)
        mycart = cart_file.cart
        cart_utils = Cartutils()
        cart_utils.set_file_status(cart_file, mycart, 'staging', False)
        #make sure cart wasnt deleted before pulling file
        if mycart.deleted_date:
            return
    except DoesNotExist:
        Cart.database_close()
        return

    archive_request = ArchiveRequests()
    #stage the file on the archive.  True on success, False on fail
    try:
        archive_request.stage_file(cart_file.file_name)
    except requests.exceptions.RequestException as ex:
        error_msg = 'Failed to stage with error: ' + str(ex)
        cart_utils.set_file_status(cart_file, mycart, 'error', error_msg)
        Cart.database_close()
        cart_utils.prepare_bundle(mycart.id)
        return

    #check to see if file is available to pull from archive interface
    try:
        response = archive_request.status_file(cart_file.file_name)
    except requests.exceptions.RequestException as ex:
        error_msg = 'Failed to status file with error: ' + str(ex)
        cart_utils.set_file_status(cart_file, mycart, 'error', error_msg)
        response = 'False'

    ready = cart_utils.check_file_ready_pull(response, cart_file, mycart)

    #Check to see if ready to pull.  If not recall this to check again
    # error on less then 0. No coverage on recall since it just calls the method again
    if ready < 0 or not ready['path_created'] or not ready['enough_space']:
        Cart.database_close()
        cart_utils.prepare_bundle(mycart.id)
        return
    elif not ready: # pragma: no cover
        pull_file.delay(file_id, False)
        Cart.database_close()
        return

    try:
        archive_request.pull_file(cart_file.file_name, ready['filepath'])
        cart_utils.set_file_status(cart_file, mycart, 'staged', False)
        Cart.database_close()
    except requests.exceptions.RequestException as ex:
        #if request fails...try a second time, if that fails write error
        if record_error:
            error_msg = 'Failed to pull with error: ' + str(ex)
            cart_utils.set_file_status(cart_file, mycart, 'error', error_msg)
            Cart.database_close()
            cart_utils.prepare_bundle(mycart.id)

        else:
            pull_file.delay(file_id, True)
            Cart.database_close()

    os.utime(ready['filepath'], (int(float(ready['modtime'])), int(float(ready['modtime']))))
    cart_utils.prepare_bundle(mycart.id)
