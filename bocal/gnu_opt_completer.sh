#!/bin/sh
set -eu

strip_opts() {
    sed -E -e "s/^[[:space:]]*//" \
        -e "s/^(-[A-Za-z0-9?],?[[:space:]]+)//" \
        -e "s/[[:space:]].*$//" \
        -e "s/=.*$/=/" \
        -e "s/\[.*$//"
}

grep -E "^[[:space:]]*-" | strip_opts | grep -E "^-" | LC_ALL=C sort -u
