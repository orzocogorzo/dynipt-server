#!/bin/bash

cd $(dirname $0) && cd ..

if [ -f var/process.pid ]; then
    echo "Another process is running"
fi

nohup .venv/bin/gunicorn -w 2 -b :8080 app:app > /dev/null &
echo $! > var/process.pid
exit 0
