#!/bin/sh
input="${1:-}"
[ -z "$input" ] && [ ! -t 0 ] && read -r input
while [ -n "$input" ]; do
    case "$input" in
        *:*)
            field="${input%%:*}"
            input="${input#*:}"
            ;;
        *)
            field="$input"
            input=""
            ;;
    esac
    printf '%s
' "$field"
done
