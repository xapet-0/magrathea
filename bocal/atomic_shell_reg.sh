#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
    printf "Usage: %s <shells_db_file> <new_shell_path>\n" "$0" >&2
    exit 1
fi

db_file="$1"
new_shell="$2"
tmp_file="${db_file}.tmp"

if [ ! -f "$db_file" ] || [ ! -r "$db_file" ]; then
    printf "DB_NOT_FOUND: %s does not exist or is not readable\n" "$db_file" >&2
    exit 1
fi

set -o noclobber
created_lock=0

cleanup() {
    if [ "$created_lock" -eq 1 ]; then
        rm -f -- "$tmp_file"
    fi
}
trap cleanup EXIT INT TERM

if ! ( : > "$tmp_file" ) 2>/dev/null; then
    printf "LOCK_CONFLICT: %s is already locked\n" "$tmp_file" >&2
    exit 1
fi
created_lock=1
awk "{print}" "$db_file" >> "$tmp_file"

if ! grep -q -F -x -- "$new_shell" "$tmp_file"; then
    printf "%s\n" "$new_shell" >> "$tmp_file"
fi

chmod --reference="$db_file" -- "$tmp_file" 2>/dev/null || \
    chmod 0644 -- "$tmp_file"
mv -f -- "$tmp_file" "$db_file"
created_lock=0
trap - EXIT INT TERM
printf "REGISTERED_OK: %s\n" "$new_shell"
