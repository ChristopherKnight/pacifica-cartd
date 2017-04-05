#!/usr/bin/python
"""
Pacifica Cart Interface database creation
"""

from cart.cart_orm import database_setup

def main():
    """Main function when running from the command line. Creates database"""
    database_setup()


if __name__ == '__main__':
    main()
