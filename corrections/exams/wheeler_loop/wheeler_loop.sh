#!/bin/sh
for f in ./*; do
    [ -e "$f" ] || continue
    printf '%s\n' "$f"
done
