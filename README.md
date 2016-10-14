# Pacifica Data Cart
[![Build Status](https://travis-ci.org/EMSL-MSC/pacifica-cartd.svg?branch=master)](https://travis-ci.org/EMSL-MSC/pacifica-cartd)
[![Code Climate](https://codeclimate.com/github/EMSL-MSC/pacifica-cartd/badges/gpa.svg)](https://codeclimate.com/github/EMSL-MSC/pacifica-cartd)
[![Test Coverage](https://codeclimate.com/github/EMSL-MSC/pacifica-cartd/badges/coverage.svg)](https://codeclimate.com/github/EMSL-MSC/pacifica-cartd/coverage)
[![Issue Count](https://codeclimate.com/github/EMSL-MSC/pacifica-cartd/badges/issue_count.svg)](https://codeclimate.com/github/EMSL-MSC/pacifica-cartd)
[![Docker Stars](https://img.shields.io/docker/stars/pacifica/cartd.svg?maxAge=2592000)](https://hub.docker.com/r/pacifica/cartd)
[![Docker Pulls](https://img.shields.io/docker/pulls/pacifica/cartd.svg?maxAge=2592000)](https://hub.docker.com/r/pacifica/cartd)
[![Docker Automated build](https://img.shields.io/docker/automated/pacifica/cartd.svg?maxAge=2592000)](https://hub.docker.com/r/pacifica/cartd)


Pacifica data cart for bundling and transfer of data sets.

This manages the bundling of data from the [archive interface]
(https://github.com/EMSL-MSC/pacifica-archiveinterface) and presents
APIs for users to use.

# Building and Installing

This code depends on the following libraries and python modules:

Docker/docker-compose

Peewee

Celery

MySQL-Python

psutil

requests

This is a standard python distutils build process.

```
python ./setup.py build
python ./setup.py install
```

# Running It

To bring up a test instance use docker-compose from the directory
the pacifica cart was checked out into

```
docker-compose up
```

# API Examples

Every cart has a unique ID associated with it. For the examples
following we used a uuid generated by standard Linux utilities.

```
MY_CART_UUID=`uuidgen`
```

## Create a Cart

Post a file to create a new cart.

Contents of file (foo.json).

id =  the id being used on the Archive

path = internal structure of bundle for file placement 

```
{
  "fileids": [
    {"id":"foo.txt", "path":"1/2/3/foo.txt"},
    {"id":"bar.csv", "path":"1/2/3/bar.csv"},
    {"id":"baz.ini", "path":"2/3/4/baz.ini"}
  ]
}
```

Post the file to the following URL.
```
curl -X POST --upload-file /tmp/foo.json http://127.0.0.1:8081/$MY_CART_UUID
```

## Status a Cart

Head on the cart to find whether its created and ready for download.

```
curl -X HEAD http://127.0.0.1:8081/$MY_CART_UUID
```

Data returned should be json telling you status of cart.

If the cart is waiting to be processed and there is no current state.
```
{
  "status": "waiting"
}
```

If the cart is being processed and waiting for files to be staged locally.
```
{
  "status": "staging"
}
```

If the cart has the files locally and is currently creating the tarfile.
```
{
  "status": "bundling"
}
```

If the cart is finally ready for download.
```
{
  "status": "ready"
}
```

If the cart has an error (such as no space available to create the tarfile).
```
{
  "status": "error"
  "message": "No Space Available"
}
```

## Get a cart

To download the tarfile for the cart.

```
curl http://127.0.0.1:8081/$MY_CART_UUID
```
To save to file
```
curl -O http://127.0.0.1:8081/$MY_CART_UUID
```

## Delete a Cart

Delete a created cart.

```
curl -X DELETE http://127.0.0.1:8081/$MY_CART_UUID
```

Data returned should be json telling you status of cart deletion.


# docker-compose.yml breakdown

Discuss the various components that make up the docker-compose file
including environment variables, containers, and images

## cartrabbit - RabbitMQ

The amqp preference for the cart.  Used to handle all the tasks.

When Linking use: cartrabbit:amqp

Specifically use "amqp" as the environemnt variable prefix when linking

## cartmysql - MySQL

The sql preference for the cart.  Used to handle all cart creation and storage
statistics.
Accessed via Peewee ORM

When Linking use: cartmysql:mysql

Specifically use "mysql" as the environemnt variable prefix when linking

Other required options are MYSQL_ROOT_PASSWORD, MYSQL_DATABASE, MYSQL_USER,
MYSQL_PASSWORD

On container startup the MYSQL_DATABASE will be created with MYSQL_USER, 
and MYSQL_PASSWORD having access.  On web server startup necessary table
creation will happen if the tables do not already exist

## Pacifica Archive Interface (optional)

The expected backend Archive manager API the pacifica cart uses

When Linking use: archiveinterface:archivei

Specifically use "archivei" as the environemnt variable prefix when linking

Other required options are ports, specifically which port you want exposed

Optional option but recommended is volumes.  Creating a shared volume makes
sure that even after the Archive Interface container is removed the file data
stays in case the Archive Interface needs to be restarted after removal

**NOTE** if not using the Archive Interface inside a container (case such as 
deployed on different server) set the following Environment variable in the
cart server/workers:
ARCHIVE_INTERFACE_URL: urltointerface:port/

Remember to include the port and ending /


## cartworkers

The backside of the cartserver which handles requesting/storing of files and
provides statuses

Needs to build its image using the Dockerfile

Linked in Containers: cartrabbit:amqp, cartmysql:mysql, (optional 
archiveinterface:archivei)
Specifically use "amqp", "mysql", "archivei" as the environemnt variable prefix
respectively when linking.

Optional option but recommended is volumes.  Creating a shared volume makes
sure that even after the cart workers container is removed the file data  stays
in case the workers need to be restarted after removal

Environment variables:
VOLUME_PATH - Required - Used as the root directory for all file storage.

LRU_BUFFER_TIME - Optional - Time, in seconds, that you want carts to be safe
from the least recently used buffer deletion.  If a cart was last used since
current time minus that buffer it is safe from deletion.  Not specified or a
0 given will result in no buffer

ARCHIVE_INTERFACE_URL - Optional - Needs to be set if not using the Pacifica 
Archive Interface as a linked in container. This will be the url to the
archive interface. Should be in the form of:

urltointerface:port/

Remember to include the port and ending /

DATABASE_LOGGING - Optional - Set if you want to debug the Peewee queries.
Causes the queries to be printed out

DATABASE_CONNECT_ATTEMPTS - Optional - Set the number of times the application
tries to connect to the database if a failure occurs. Default 3

DATABASE_WAIT - Optional - Set the amount of time (in seconds) the application will
take between trying to reconnect to the database.  Default 10 seconds

## cartserver

The wsgi web server for the cart which provides the API 

Needs to build its image using the Dockerfile.wsgi

Linked in Containers: cartrabbit:amqp, cartmysql:mysql, (optional 
archiveinterface:archivei)
Specifically use "amqp", "mysql", "archivei" as the environemnt variable prefix
respectively when linking.

Other required options are ports, specifically which port you want exposed

Optional option but recommended is volumes.  Creating a shared volume makes
sure that even after the cart workers container is removed the file data  stays
in case the workers need to be restarted after removal

Environment variables:
VOLUME_PATH - Required - Used as the root directory for all file storage.

LRU_BUFFER_TIME - Optional - Time, in seconds, that you want carts to be safe
from the least recently used buffer deletion.  If a cart was last used since
current time minus that buffer it is safe from deletion.  Not specified or a
0 given will result in no buffer

ARCHIVE_INTERFACE_URL - Optional - Needs to be set if not using the Pacifica 
Archive Interface as a linked in container. This will be the url to the
archive interface. Should be in the form of:

urltointerface:port/

Remember to include the port and ending /

DATABASE_CONNECT_ATTEMPTS - Optional - Set the number of times the application
tries to connect to the database if a failure occurs. Default 3

DATABASE_WAIT - Optional - Set the amount of time (in seconds) the application will
take between trying to reconnect to the database.  Default 10 seconds

The environment variables should be exactly the same as those used for the
cartworkers container
