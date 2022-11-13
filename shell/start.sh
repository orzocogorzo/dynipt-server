#! /usr/bin/env bash

cd $(dirname $0) && cd ..

if [ -f var/process.pid ]; then
    echo "Another process is running"
fi

source .env

if [ "$DYNIPT_FRONT_SERVER" = 'true' ]; then
    host="127.0.0.1"
else
    host="0.0.0.0"
fi

nohup .venv/bin/gunicorn -w 2 -b $host:8080 app:app > /dev/null &
echo $! > var/process.pid
exit 0
