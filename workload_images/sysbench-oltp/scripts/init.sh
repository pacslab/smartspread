#!/usr/bin/env bash
export hostname=$1
export postfix=$2

/usr/local/bin/docker-entrypoint.sh mysqld &

# wait until the mysql is ready
until bash /code/lin.sh
do
    sleep 1s
    echo "."
done

gunicorn --bind 0.0.0.0:80 --workers 1 wsgi &

python3 /code/rmqserver/RPCServer.py --queue /oltp --max-length 100 --message-ttl 10000 --num-consumers 1 --heartbeat 60
