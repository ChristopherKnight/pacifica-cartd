"""Module that has the utility functionality for
the cart
"""
from __future__ import absolute_import
import os
import json
import datetime
import errno
import shutil
import psutil
from peewee import DoesNotExist
from cart.cart_orm import Cart, File
from cart.cart_env_globals import VOLUME_PATH, LRU_BUFFER_TIME



class Cartutils(object):
    """Class used to provide utility functions for the
    cart to use.
    """
    def __init__(self):
        self._vol_path = VOLUME_PATH
        self._lru_buff = LRU_BUFFER_TIME

    ###########################################################################
    #
    # Helper methods for handling cart path creation
    #
    ###########################################################################
    @staticmethod
    def fix_absolute_path(filepath):
        """Removes / from front of path"""
        if os.path.isabs(filepath):
            filepath = filepath[1:]
        return filepath


    @staticmethod
    def create_bundle_directories(filepath):
        """Creates all the directories in the given path
        if they do not already exist.
        """
        try:
            os.makedirs(filepath, 0o777)
        except OSError as exception:
            #dont worry about error if the directory already exists
            #other errors are a problem however so push them up
            if exception.errno != errno.EEXIST:
                raise exception

    @classmethod
    def create_download_path(cls, cart_file, mycart, abs_cart_file_path):
        """ Create the directories that the file will be pulled to"""
        try:
            cart_file_dirs = os.path.dirname(abs_cart_file_path)
            cls.create_bundle_directories(cart_file_dirs)
        except OSError as ex:
            cart_file.status = 'error'
            cart_file.error = 'Failed directory create with error: ' + str(ex)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return False

        return True


    ###########################################################################
    #
    # Helper methods that determine space available/size
    # needed for the cart and files
    #
    ###########################################################################

    @staticmethod
    def check_file_size_needed(response, cart_file, mycart):
        """Checks response (should be from Archive Interface head request)
         for file size """
        try:
            decoded = json.loads(response)
            filesize = decoded['filesize']
            return long(filesize)
        except (ValueError, KeyError, TypeError) as ex:
            cart_file.status = 'error'
            cart_file.error = """Failed to decode file size
            json with error: """ + str(ex) + """ Response received from the
            Archive is: """ + str(response)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return -1


    def check_space_requirements(
            self, cart_file, mycart, size_needed, deleted_flag):
        """Checks to make sure there is enough space available on disk
        for the file to be downloaded
        Note it will recursively call itself if there isnt enough
        space. It will delete a cart first, then call  itself
        until either there is enough space or there is no carts to delete"""
        try:
            #available space is in bytes
            available_space = long(psutil.disk_usage(self._vol_path).free)
        except psutil.Error as ex:
            cart_file.status = 'error'
            cart_file.error = """Failed to get available file
            space with error: """ + str(ex)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return False

        if size_needed > available_space:
            if deleted_flag:
                cart_deleted = self.lru_cart_delete(mycart)
                return self.check_space_requirements(cart_file, mycart,
                                                     size_needed, cart_deleted)
            cart_file.status = 'error'
            cart_file.error = 'Not enough space to download file'
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return False

        #there is enough space so return true
        return True

    @classmethod
    def get_path_size(cls, source):
        """Returns the size of a specific directory, including
        all subdirectories and files
        """
        total_size = os.path.getsize(source)
        for item in os.listdir(source):
            itempath = os.path.join(source, item)
            if os.path.isfile(itempath):
                total_size += os.path.getsize(itempath)
            elif os.path.isdir(itempath):
                total_size += cls.get_path_size(itempath)
        return total_size


    ###########################################################################
    #
    # Helper methods that parse the Archive Interface Responses
    #
    ###########################################################################
    def check_file_ready_pull(self, response, cart_file, mycart):
        """Checks response (should be from Archive Interface head request)
        for bytes per level then returns True or False based on if the file
        is at level 1 (downloadable)"""
        size_needed = self.check_file_size_needed(response, cart_file, mycart)
        mod_time = self.check_file_modified_time(response, cart_file, mycart)
        #Return from function if the values couldnt be parsed (-1 return)
        if size_needed < 0 or mod_time < 0:
            return -1
        try:
            decoded = json.loads(response)
            media = decoded['file_storage_media']
            if media == 'disk':
                #set up saving path and return dictionary
                abs_cart_file_path = os.path.join(
                    VOLUME_PATH, str(mycart.id), mycart.cart_uid, cart_file.bundle_path)
                path_created = self.create_download_path(cart_file, mycart, abs_cart_file_path)
                #Check size here and make sure enough space is available.
                enough_space = self.check_space_requirements(cart_file, mycart, size_needed, True)
                return {'modtime': mod_time, 'filepath': abs_cart_file_path,
                        'path_created': path_created, 'enough_space': enough_space}
            return False
        except (ValueError, KeyError, TypeError) as ex:
            cart_file.status = 'error'
            cart_file.error = """Failed to decode json for file status
            with error: """ + str(ex) + """ Response received from the
            Archive is: """ + str(response)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return -1

    @staticmethod
    def check_file_modified_time(response, cart_file, mycart):
        """Checks response (should be from Archive Interface head request)
         for file modified time """
        try:
            decoded = json.loads(response)
            mod_time = decoded['mtime']
            return mod_time
        except (ValueError, KeyError, TypeError) as ex:
            cart_file.status = 'error'
            cart_file.error = """Failed to decode file mtime
            json with error: """ + str(ex) + """ Response received from the
            Archive is: """ + str(response)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return -1



    ###########################################################################
    #
    # Helper methods used to delete carts
    #
    ###########################################################################
    @classmethod
    def remove_cart(cls, uid):
        """Call when a DELETE request comes in. Verifies there is a cart
        to delete then removes it
        """
        deleted_flag = True
        iterator = 0 #used to verify at least one cart deleted
        Cart.database_connect()
        carts = (Cart
                 .select()
                 .where(
                     (Cart.cart_uid == str(uid)) &
                     (Cart.deleted_date.is_null(True))))
        for cart in  carts:
            iterator += 1
            success = cls.delete_cart_bundle(cart)
            if not success:
                deleted_flag = False
        Cart.database_close()
        if deleted_flag and iterator > 0:
            return 'Cart Deleted Successfully'
        elif deleted_flag:
            return False #already deleted
        return None #unknown error

    @staticmethod
    def delete_cart_bundle(cart):
        """ Gets the path to where a carts file are and
        attempts to delete the file tree"""
        try:
            path_to_files = os.path.join(VOLUME_PATH, str(cart.id))
            shutil.rmtree(path_to_files)
            cart.status = 'deleted'
            cart.deleted_date = datetime.datetime.now()
            cart.save()
            return True
        except OSError:
            return False

    @classmethod
    def lru_cart_delete(cls, mycart):
        """Delete the least recently used cart that isnt this one.
        Only delete one cart per call
        """
        try:
            lru_time = datetime.datetime.now() - datetime.timedelta(
                seconds=int(LRU_BUFFER_TIME))
            del_cart = (Cart
                        .select()
                        .where(
                            (Cart.id != mycart.id) &
                            (Cart.deleted_date.is_null(True)) &
                            (Cart.updated_date < lru_time))
                        .order_by(Cart.creation_date)
                        .get())
            return cls.delete_cart_bundle(del_cart)
        except DoesNotExist:
            #case if no cart exists that can be deleted
            return False



    ###########################################################################
    #
    # Cart Interface helpers for returning status/download paths
    #
    ###########################################################################
    @staticmethod
    def cart_status(uid):
        """Get the status of a specified cart"""
        Cart.database_connect()
        status = None
        try:
            mycart = (Cart
                      .select()
                      .where(
                          (Cart.cart_uid == str(uid)) &
                          (Cart.deleted_date.is_null(True)))
                      .order_by(Cart.creation_date.desc())
                      .get())
        except DoesNotExist:
            #case if no record exists yet in database
            mycart = None
            status = ['error', 'No cart with uid ' + uid + ' found']

        if mycart:
            #send the status and any available error text
            status = [mycart.status, mycart.error]

        Cart.database_close()
        return status

    @staticmethod
    def available_cart(uid):
        """Checks if the asked for cart tar is available
           returns the path to tar if yes, false if not. None if no cart"""
        Cart.database_connect()
        cart_bundle_path = False
        try:
            mycart = (Cart
                      .select()
                      .where(
                          (Cart.cart_uid == str(uid)) &
                          (Cart.deleted_date.is_null(True)))
                      .order_by(Cart.creation_date.desc())
                      .get())
        except DoesNotExist:
            #case if no record exists yet in database
            mycart = None
            cart_bundle_path = None

        if mycart and mycart.status == 'ready':
            cart_bundle_path = mycart.bundle_path
        Cart.database_close()
        return cart_bundle_path


    ###########################################################################
    #
    # Helpers that update a carts files and a cart/file error
    #
    ###########################################################################
    @staticmethod
    def set_file_status(cart_file, cart, status, error):
        """Sets the status and/or error for a cart"""
        cart_file.status = str(status)
        if error:
            cart_file.error = str(error)
        cart_file.save()
        cart.updated_date = datetime.datetime.now()
        cart.save()


    @classmethod
    def update_cart_files(cls, cart, file_ids):
        """Update the files associated to a cart"""
        with Cart.atomic():
            for f_id in file_ids:
                try:
                    filepath = cls.fix_absolute_path(f_id['path'])
                    hashtype = f_id['hashtype']
                    hashval = f_id['hashsum']
                    File.create(cart=cart, file_name=f_id['id'], bundle_path=filepath,
                                hash_type=hashtype, hash_value=hashval)
                    cart.updated_date = datetime.datetime.now()
                    cart.save()
                except NameError as ex:
                    return ex #return error so that the cart can be updated
            return None


    @classmethod
    def prepare_bundle(cls, cartid):
        """Checks to see if all the files are staged locally
        before calling the bundling action.  If not will call
        itself to continue the waiting process
        """
        Cart.database_connect()
        bundle_flag = True
        for c_file in File.select().where(File.cart == cartid):
            if c_file.status == 'error':
                #error pulling file so set cart error and return
                try:
                    mycart = Cart.get(Cart.id == cartid)
                    mycart.status = 'error'
                    mycart.error = 'Failed to pull file(s)'
                    mycart.updated_date = datetime.datetime.now()
                    mycart.save()
                    Cart.database_close()
                    return
                except DoesNotExist: # pragma: no cover
                    #case if record no longer exists
                    #creating this case in unit testing requires deletion and creation
                    #occuring nearly simultaneously, as such cant create unit test
                    Cart.database_close()
                    return

            elif c_file.status != 'staged':
                bundle_flag = False

        cls.tar_files(cartid, bundle_flag)
        Cart.database_close()

    @staticmethod
    def tar_files(cartid, bundle_flag):
        """Start to bundle all the files together
        Due to streaming the tar we dont need to try and bundle
        everything together"""

        if bundle_flag:
            Cart.database_connect()
            try:
                mycart = Cart.get(Cart.id == cartid)
                bundle_path = os.path.join(
                    VOLUME_PATH, str(mycart.id), (mycart.cart_uid))
                mycart.status = 'ready'
                mycart.bundle_path = bundle_path
                mycart.updated_date = datetime.datetime.now()
                mycart.save()
            except DoesNotExist:
                #case if record no longer exists
                Cart.database_close()
                return

            Cart.database_close()
