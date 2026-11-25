#!/bin/sh
# Node-side starter for the phcc distributed compile worker.
# Deployed alongside the phccd binary in ~/phcc-dist-node/.
cd "$HOME/phcc-dist-node" || exit 1
mkdir -p cache
if [ -f phccd.pid ] && kill -0 "$(cat phccd.pid)" 2>/dev/null; then
    echo "phccd already running (pid $(cat phccd.pid))"
    exit 0
fi
nohup ./phccd 4711 "$HOME/phcc-dist-node/cache" > phccd.log 2>&1 &
echo $! > phccd.pid
echo "phccd started (pid $!)"
