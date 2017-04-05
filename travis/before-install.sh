#!/bin/bash
sudo service mysql stop
if [ -z "$RUN_LINTS" ]; then
  docker-compose up -d cartrabbit cartmysql archiveinterface
fi
pip install requests
if [ "$RUN_LINTS" = "true" ]; then
  pip install pre-commit
else
  python travis/archiveinterfacepreload.py
  pip install codeclimate-test-reporter coverage nose pytest
fi
