#!/bin/bash

cd $(dirname $0) && cd ..

if [ -f var/process.pid ]; then
    kill -9 $(cat var/process.pid)
    rm var/process.pid
else
    echo "No running process"
fi

exit 0
