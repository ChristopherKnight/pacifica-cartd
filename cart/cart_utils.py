from __future__ import absolute_import
from cart.cart_orm import Cart, File, DB, database_connect, database_close
from os import path
from cart.cart_env_globals import VOLUME_PATH, ARCHIVE_INTERFACE_URL, LRU_BUFFER_TIME
import os
import time
import json
import datetime
import errno
import psutil
import pycurl
from StringIO import StringIO
import shutil


class cart_utils:
    @staticmethod
    def fix_absolute_path(filepath):
        """Removes / from front of path"""
        if os.path.isabs(filepath):
            filepath = filepath[1:]
        return filepath

    @classmethod
    def updateCartFiles(cls, cart, fileIds):
        """Update the files associated to a cart"""
        with DB.atomic():
            for fId in fileIds:
                filepath = cls.fix_absolute_path(fId["path"])
                File.create(cart=cart, file_name=fId["id"], bundle_path=filepath)
                cart.updated_date = datetime.datetime.now()
                cart.save()

    @staticmethod
    def create_bundle_directories(filepath):
        """Creates all the directories in the given path
        if they do not already exist.
        """
        try:
            os.makedirs(filepath, 0777)
        except OSError as exception:
            #dont worry about error if the directory already exists
            #other errors are a problem however so push them up
            if exception.errno != errno.EEXIST:
                raise exception
        
    @staticmethod
    def check_file_size_needed(response, cart_file, mycart):
        """Checks response (should be from Archive Interface head request) for file size """
        try:
            decoded = json.loads(response)
            filesize = decoded['filesize']
            return long(filesize)
        except (ValueError, KeyError, TypeError) as ex:
            cart_file.status = "error"
            cart_file.error = "Failed to decode json for file size with error: " + str(ex)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return (-1)

    @staticmethod
    def check_file_ready_pull(response, cart_file, mycart):
        """Checks response (should be from Archive Interface head request) for bytes per level
           then returns True or False based on if the file is at level 1 (downloadable)"""
        try:
            decoded = json.loads(response)
            media = decoded['file_storage_media']
            if media == "disk":
                return True
            else:
                return False
        except (ValueError, KeyError, TypeError):
            cart_file.status = "error"
            cart_file.error = "Failed to decode json for file status with error: " + str(ex)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return (-1)


    @staticmethod
    def check_space_requirements(cart_file, mycart, size_needed, deleted_flag):
        """Checks to make sure there is enough space available on disk for the file
        to be downloaded
        Note it will recursively call itself if there isnt enough
        space. It will delete a cart first, then call  itself
        until either there is enough space or there is no carts to delete""" 
        try:
            #available space is in bytes
            available_space = long(psutil.disk_usage(VOLUME_PATH).free)
        except Exception as ex:
            cart_file.status = "error"
            cart_file.error = "Failed to get available file space with error: " + str(ex)
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return False

        if(size_needed > available_space):
            if deleted_flag:
                cart_deleted = lru_cart_delete(mycart)
                return check_space_requirements(cart_file, mycart, size_needed, cart_deleted)
            cart_file.status = "error"
            cart_file.error = "Not enough space to download file"
            cart_file.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return False

        #there is enough space so return true
        return True

    @classmethod
    def create_download_path(cls,f, mycart, abs_cart_file_path):
        """ Create the directories that the file will be pulled to"""
        try:          
            cart_file_dirs = os.path.dirname(abs_cart_file_path)
            cls.create_bundle_directories(cart_file_dirs)
        except Exception as ex:
            f.status = "error"
            f.error = "Failed to create directories with error: " + str(ex)
            f.save()
            mycart.updated_date = datetime.datetime.now()
            mycart.save()
            return False

        return True

    @staticmethod
    def get_path_size(source):
        """Returns the size of a specific directory, including
        all subdirectories and files
        """
        total_size = os.path.getsize(source)
        for item in os.listdir(source):
            itempath = os.path.join(source, item)
            if os.path.isfile(itempath):
                total_size += os.path.getsize(itempath)
            elif os.path.isdir(itempath):
                total_size += get_path_size(itempath)
        return total_size

    @classmethod
    def remove_cart(cls,uid):
        """Call when a DELETE request comes in. Verifies there is a cart
        to delete then removes it
        """
        deleted_flag = True
        iterator = 0 #used to verify at least one cart deleted
        database_connect()
        try:
            for cart in  Cart.select().where((Cart.cart_uid == str(uid)) & (Cart.deleted_date.is_null(True))):
                iterator += 1
                success = cls.delete_cart_bundle(cart)
                if success == False:
                    deleted_flag = False
            database_close()
            if deleted_flag and iterator > 0:
                return "Cart Deleted Successfully"
            elif deleted_flag:
                return "Cart with uid: " + str(uid) + " was previously deleted or no longer exists"
            else:
                return "Error with deleting Cart"
        except Exception as ex:
            #case if record no longer exists
            database_close()
            return "Error Deleteing Cart with uid: " + str(uid)

    @staticmethod
    def delete_cart_bundle(cart):
        """ Gets the path to where a carts file are and 
        attempts to delete the file tree"""
        try:
            path_to_files = os.path.join(VOLUME_PATH, str(cart.id))
            shutil.rmtree(path_to_files)
            cart.status = "deleted"
            cart.deleted_date = datetime.datetime.now()
            cart.save()
            return True
        except Exception as ex:
            return False

    @classmethod
    def lru_cart_delete(cls, mycart):
        """Delete the least recently used cart that isnt this one.
        Only delete one cart per call
        """
        try:
            lru_time = datetime.datetime.now() - datetime.timedelta(seconds=int(LRU_BUFFER_TIME))
            del_cart = (Cart.select().where((Cart.id != mycart.id) & (Cart.deleted_date.is_null(True)) & (Cart.updated_date < lru_time) ).order_by(Cart.creation_date).get())
            return cls.delete_cart_bundle(del_cart)
        except Exception as ex:
            #case if no cart exists that can be deleted
            return False

    @staticmethod
    def cartStatus(uid):
        """Get the status of a specified cart"""
        database_connect()
        status = None
        try:
            mycart = (Cart.select().where((Cart.cart_uid == str(uid)) & (Cart.deleted_date.is_null(True))).order_by(Cart.creation_date.desc()).get())
        except Exception as ex:
            #case if no record exists yet in database
            mycart = None
            status = ["error","No cart with uid " + uid + " found"] 
        
        if mycart:
            #send the status and any available error text
            status = [mycart.status, mycart.error]

        database_close()
        return status

    @staticmethod
    def availableCart(uid):
        """Checks if the asked for cart tar is available
           returns the path to tar if yes, false if not"""
        database_connect()
        cartBundlePath = False
        try:
            mycart = (Cart.select().where((Cart.cart_uid == str(uid)) & (Cart.deleted_date.is_null(True))).order_by(Cart.creation_date.desc()).get())
        except Exception as ex:
            #case if no record exists yet in database
            mycart = None

        if mycart and mycart.status == "ready":
            cartBundlePath = mycart.bundle_path
        database_close()
        return cartBundlePath
    