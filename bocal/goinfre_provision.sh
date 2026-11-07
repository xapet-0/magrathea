#!/bin/sh
set -eu

user_name="${1:-student}"
home_dir="${2:-/tmp/home_$user_name}"
goinfre_root="${3:-/tmp/goinfre}"

mkdir -p -- "$home_dir" "$goinfre_root"
user_goinfre="$goinfre_root/$user_name"

mkdir -p -m 0700 -- "$user_goinfre"
chmod 0700 -- "$user_goinfre"

if [ ! -e "$home_dir/goinfre" ] && [ ! -L "$home_dir/goinfre" ]; then
    ln -ns -- "$user_goinfre" "$home_dir/goinfre"
fi

mode_octal="$(stat -c "%a" -- "$user_goinfre" 2>/dev/null || printf "700")"
printf "GOINFRE_OK: %s -> %s (mode=%s)\n" \
    "$home_dir/goinfre" "$user_goinfre" "$mode_octal"
