#!/usr/bin/env sh
export hostname=$1
export postfix=$2

sysbench --test=fileio --file-total-size=100M --file-test-mode=rndrw prepare
bash /code/lin.sh

gunicorn --bind 0.0.0.0:80 --workers 1 wsgi &

python3 /code/rmqserver/RPCServer.py --queue /fileio --max-length 100 --message-ttl 10000 --num-consumers 1 --heartbeat 60
