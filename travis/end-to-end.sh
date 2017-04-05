#!/bin/bash
coverage run --include='cart/*' -p -m celery -A cart worker -l info &
CELERY_PID=$!
coverage run --include='cart/*' -p CartServer.py --port 8081 --address 0.0.0.0 &
SERVER_PID=$!
coverage run --include='cart/*' -a -m pytest cart/test/cart_end_to_end_tests.py -v
sleep 4
celery control shutdown || true
kill $SERVER_PID
wait $SERVER_PID $CELERY_PID
coverage combine -a .coverage*
coverage report -m --fail-under 100
if [[ $CODECLIMATE_REPO_TOKEN ]] ; then
  codeclimate-test-reporter
fi
