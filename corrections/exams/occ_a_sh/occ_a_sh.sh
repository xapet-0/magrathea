#!/bin/sh
printf '%s' "$FT_LINE" | tr -cd 'a' | wc -c | tr -d ' '
