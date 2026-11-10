#!/bin/sh
set -eu

grep -E "^[[:space:]]*-" | \
    sed -E -e "s/^[[:space:]]*//" \
        -e "s/^(-[A-Za-z0-9?],?[[:space:]]+)//" \
        -e "s/[[:space:]].*$//" \
        -e "s/=.*$/=/" \
        -e "s/\[.*$//" | \
    grep -E "^-" | LC_ALL=C sort -u
