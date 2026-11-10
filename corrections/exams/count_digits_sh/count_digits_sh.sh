#!/bin/sh
printf '%s' "$FT_LINE" | tr -cd '0-9' | wc -c | tr -d ' '
