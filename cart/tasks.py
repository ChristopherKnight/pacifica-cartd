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
    file_id_error = cart_utils.update_cart_files(mycart, file_ids)
    if not file_id_error:
        get_files_locally.delay(mycart.id)
    else:
        mycart.status = 'error'
        mycart.error = 'Error parsing file Ids with error: ' + str(file_id_error)
        mycart.updated_date = datetime.datetime.now()
        mycart.save()
    Cart.database_close()

@CART_APP.task(ignore_result=True)
def get_files_locally(cartid):
    """Pull the files to the local system from the backend """
    #tell each file to be pulled
    Cart.database_connect()
    for cart_file in File.select().where(File.cart == cartid):
        stage_file_tasl.delay(cart_file.id)
    Cart.database_close()

@CART_APP.task(ignore_result=True)
def stage_file_task(file_id):
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
    try:
        archive_request.stage_file(cart_file.file_name)
    except requests.exceptions.RequestException as ex:
        error_msg = 'Failed to stage with error: ' + str(ex)
        cart_utils.set_file_status(cart_file, mycart, 'error', error_msg)
        Cart.database_close()
        cart_utils.prepare_bundle(mycart.id)
        return
    #successful stage so move on to status
    Cart.database_close()
    status_file_task.delay(file_id)

@CART_APP.task(ignore_result=True)
def status_file_task(file_id):
    Cart.database_connect()
    try:
        cart_file = File.get(File.id == file_id)
        mycart = cart_file.cart
        cart_utils = Cartutils()
        #make sure cart wasnt deleted before pulling file
        if mycart.deleted_date:
            return
    except DoesNotExist:
        Cart.database_close()
        return
    #check to see if file is available to pull from archive interface
    archive_request = ArchiveRequests()
    try:
        response = archive_request.status_file(cart_file.file_name)
    except requests.exceptions.RequestException as ex:
        error_msg = 'Failed to status file with error: ' + str(ex)
        cart_utils.set_file_status(cart_file, mycart, 'error', error_msg)
        Cart.database_close()
        cart_utils.prepare_bundle(mycart.id)
        return

    ready = cart_utils.check_file_ready_pull(response, cart_file, mycart)

    #Check to see if ready to pull.  If not recall this to check again
    # error on less then 0. No coverage on recall since it just calls the method again
    if ready < 0 or not ready['path_created'] or not ready['enough_space']:
        Cart.database_close()
        cart_utils.prepare_bundle(mycart.id)
        return
    elif not ready: # pragma: no cover
        Cart.database_close()
        status_file_task.delay(file_id)
        return
    #ready so try to pull file
    pull_file.delay(file_id, ready['filepath'], ready['modtime'], False)

@CART_APP.task(ignore_result=True)
def pull_file(file_id, filepath, modtime, record_error):
    """Pull a file from the archive  """
    Cart.database_connect()
    try:
        cart_file = File.get(File.id == file_id)
        mycart = cart_file.cart
        cart_utils = Cartutils()
        #make sure cart wasnt deleted before pulling file
        if mycart.deleted_date:
            return
    except DoesNotExist:
        Cart.database_close()
        return

    archive_request = ArchiveRequests()
    try:
        archive_request.pull_file(cart_file.file_name, filepath, cart_file.hash_value, cart_file.hash_type)
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
            pull_file.delay(file_id, filepath, modtime, True)
            Cart.database_close()

    except ValueError as ex:
        error_msg = 'Failed to pull with error: ' + str(ex)
        cart_utils.set_file_status(cart_file, mycart, 'error', error_msg)
        Cart.database_close()
        cart_utils.prepare_bundle(mycart.id)

    os.utime(filepath, (int(float(modtime)), int(float(modtime))))
    cart_utils.prepare_bundle(mycart.id)
