#! /usr/bin/env bash

cd $(dirname $0) && cd ..

if [ -f var/process.pid ]; then
    kill -9 $(cat var/process.pid)
    rm var/process.pid
    truncate -s 0 var/state
    echo "DynIPt server stopped"
else
    echo "No DynIPt server running"
fi

exit 0
