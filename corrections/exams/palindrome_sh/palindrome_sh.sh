#!/bin/sh
rev_s=$(printf '%s' "$FT_LINE" | rev)
if [ "$FT_LINE" = "$rev_s" ]; then echo 1; else echo 0; fi
