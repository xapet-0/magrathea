#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    exit 1
fi

py='import sys; p=sys.argv[1].encode()'
py="$py; i=sys.stdin.buffer.read()"
py="$py; sys.stdout.buffer.write(i.replace(p, b'*'*len(p)))"
exec python3 -c "$py" "$1"
