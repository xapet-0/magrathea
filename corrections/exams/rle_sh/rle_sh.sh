#!/bin/sh
printf '%s\n' "$FT_LINE" | awk '{
  s=$0; out=""; i=1;
  while (i <= length(s)) {
    c = substr(s, i, 1); cnt = 1;
    while (i + cnt <= length(s) && substr(s, i + cnt, 1) == c) cnt++;
    out = out cnt c;
    i += cnt;
  }
  print out;
}'
