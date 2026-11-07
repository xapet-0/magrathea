#!/bin/sh
printf '%s\n' "$FT_LINE" | awk '{$1=$1; print}'
