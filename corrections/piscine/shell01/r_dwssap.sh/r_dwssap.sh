#!/bin/sh
grep -v '^#' /etc/passwd | awk 'NR % 2 == 0' | cut -d ':' -f 1 | rev \
    | sort -fnr | awk -v s="$FT_LINE1" -v e="$FT_LINE2" 'NR >= s && NR <= e' \
    | paste -sd ',' - | sed 's/,/, /g; s/$/./' | tr -d '\n'
