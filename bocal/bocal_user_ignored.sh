#!/bin/sh
set -eu

target_user="${FT_USER:-${1:-}}"
ignored_list="${FT_IGNORED_USERS:-exam checkin bocal}"

if [ -z "$target_user" ]; then
    printf "ACTIVE\n"
    exit 1
fi

if printf "%s\n" "$ignored_list" | tr " \t" "\n\n" | \
    grep -q -F -x -- "$target_user"; then
    printf "IGNORED\n"
    exit 0
fi

printf "ACTIVE\n"
exit 1
