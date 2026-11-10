#!/bin/sh
set -eu

user_name="${1:-student}"
home_dir="${2:-/tmp/home_$user_name}"
skel_dir="${3:-}"

mkdir -p -- "$home_dir"

if [ -f "$home_dir/.reset" ]; then
    find "$home_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    if [ -n "$skel_dir" ] && [ -d "$skel_dir" ]; then
        cp -R -- "$skel_dir/." "$home_dir/"
    fi
    printf "FULL_RESET: %s\n" "$user_name"
else
    find "$home_dir" -mindepth 1 -maxdepth 1 \
        -type d -name ".cache" -exec rm -rf -- {} +
    find "$home_dir" -mindepth 1 -maxdepth 2 \
        -name "Singleton*" -exec rm -f -- {} +
    printf "CACHE_CLEANED: %s\n" "$user_name"
fi
