#!/bin/sh
awk '{for (i=1; i<=NF; i++) a[i,NR]=$i; if (NF>m) m=NF} END {for (i=1; i<=m; i++) {for (j=1; j<=NR; j++) printf "%s%s", a[i,j], (j==NR?"\n":" ")}}'
