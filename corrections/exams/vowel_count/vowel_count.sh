#!/bin/sh
printf "%s" "$FT_LINE" | tr -cd "aeiouAEIOU" | wc -c | tr -d " "
