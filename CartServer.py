#!/usr/bin/python
"""
Pacifica Cart Interface
This is the main program that starts the WSGI server.
The core of the server code is in cart_interface.py.
"""
import signal
import sys
from argparse import ArgumentParser
from wsgiref.simple_server import make_server
from cart.cart_orm import database_setup
from cart.cart_interface import CartGenerator

# pylint: disable=unused-argument
def exit_handler(signum, frame):
    """Catch term and exit cleanly"""
    print 'Exiting cleanly from {0}'.format(signum)
    sys.exit(signum)
# pylint: enable=unused-argument

signal.signal(signal.SIGTERM, exit_handler)

def main():
    """Main function when running from the command line."""
    parser = ArgumentParser(description='Run the cart interface.')

    parser.add_argument('-p', '--port', metavar='PORT', type=int,
                        default=8080, dest='port',
                        help='port to listen on')
    parser.add_argument('-a', '--address', metavar='ADDRESS',
                        default='localhost', dest='address',
                        help='address to listen on')

    args = parser.parse_args()
    generator = CartGenerator()
    #make sure the database is up
    database_setup()
    srv = make_server(args.address, args.port,
                      generator.pacifica_cartinterface)

    srv.serve_forever()


# pylint doesn't realize that application is actually a callable
# pylint: disable=invalid-name
application = CartGenerator().pacifica_cartinterface
# pylint: enable=invalid-name

if __name__ == '__main__':
    main()
