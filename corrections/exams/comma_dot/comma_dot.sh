#!/bin/sh
awk '{a[NR]=$0} END {for(i=1;i<=NR;i++) printf "%s%s", a[i], (i<NR?", ":".")}'
