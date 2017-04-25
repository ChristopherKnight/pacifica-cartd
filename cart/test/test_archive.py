#!/usr/bin/python
"""
Add Unit Tests for archive interface.
"""

import unittest
from json import dumps, loads
from tempfile import mkdtemp
import httpretty
import requests
from cart.archive_requests import ArchiveRequests

class TestArchiveRequests(unittest.TestCase):
    """
    Test the archive requests class
    """
    endpoint_url = 'http://localhost:8080'

    @httpretty.activate
    def test_archive_get(self):
        """
        Test pulling a file
        """
        response_body = "This is the body of the file in the archive."
        httpretty.register_uri(httpretty.GET, '%s/1'%(self.endpoint_url),
                               body=response_body,
                               content_type='application/octet-stream')
        temp_dir = mkdtemp()
        archreq = ArchiveRequests()
        hashval = '5bf018b3c598df19b5f4363fc55f2f89'
        hashtype = 'md5'
        archreq.pull_file('1', '%s/1'%(temp_dir), hashval, hashtype)
        testfd = open('%s/1'%(temp_dir), 'r')
        self.assertEqual(testfd.read(), response_body)

    @httpretty.activate
    def test_archive_stage(self):
        """
        Test staging a file
        """
        response_body = {
            'message': 'File was staged',
            'file': '1'
        }
        httpretty.register_uri(httpretty.POST, '%s/1'%(self.endpoint_url),
                               body=dumps(response_body),
                               content_type='application/json')
        archreq = ArchiveRequests()
        archreq.stage_file('1')
        self.assertEqual(httpretty.last_request().method, 'POST')

    @httpretty.activate
    def test_archive_status(self):
        """
        Test pulling a file
        """
        stage_file_obj = {
            'bytes_per_level': '0',
            'ctime': 'Sun, 06 Nov 1994 08:49:37 GMT',
            'file_storage_media': '0',
            'filesize': '8',
            'file': '1',
            'mtime': 'Sun, 06 Nov 1994 08:49:37 GMT',
            'message': 'File was found'
        }
        adding_headers = {
            'x-pacifica-messsage': 'File was found',
            'x-pacifica-ctime': 'Sun, 06 Nov 1994 08:49:37 GMT',
            'x-pacifica-bytes-per-level': '0',
            'x-pacifica-file-storage-media': '0',
            'last-modified': 'Sun, 06 Nov 1994 08:49:37 GMT'
        }
        httpretty.register_uri(httpretty.HEAD, '%s/1'%(self.endpoint_url),
                               status=200,
                               body='blahblah',
                               adding_headers=adding_headers)
        archreq = ArchiveRequests()
        status = loads(archreq.status_file('1'))
        for key in status.keys():
            self.assertEqual(status[key], stage_file_obj[key])
        self.assertEqual(httpretty.last_request().method, 'HEAD')

    @httpretty.activate
    def test_archive_stage_fail(self):
        """
        Test staging a file failure
        """
        response_body = {
            'message': 'error',
            'file': '1'
        }
        httpretty.register_uri(httpretty.POST, '%s/1'%(self.endpoint_url),
                               status=500,
                               body=dumps(response_body),
                               content_type='application/json')
        archreq = ArchiveRequests()
        with self.assertRaises(requests.exceptions.RequestException):
            archreq.stage_file('fakeFileName')
