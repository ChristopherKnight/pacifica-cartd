import os, sys
import requests
from StringIO import StringIO

FILENAME1 = 'foo.txt'
FILENAME2 = 'bar.csv'
FILENAME3 = 'baz.ini'
ARCHIVEURL = 'http://127.0.0.1:8080/'

def write():

    file1 = open(FILENAME1,'w')   # Trying to create a new file or open one
    file1.write('Writing content for first file')
    file1.close()

    file2 = open(FILENAME2,'w')   # Trying to create a new file or open one
    file2.write('Writing,content,for,second,file')
    file2.close()

    file3 = open(FILENAME3,'w')   # Trying to create a new file or open one
    file3.write('Writing content for the third and final file')
    file3.close()


def remove():
    os.remove(FILENAME1)
    os.remove(FILENAME2)
    os.remove(FILENAME3)


def push2archive(filename):
    filesize = os.path.getsize(filename)
    f = open(filename,'rb')

    requests.put(str(ARCHIVEURL+filename), data=f)
    f.close()

write()
push2archive(FILENAME1)
push2archive(FILENAME2)
push2archive(FILENAME3)
remove()
