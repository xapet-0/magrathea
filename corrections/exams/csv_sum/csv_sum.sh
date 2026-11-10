#!/bin/sh
awk -F',' '$2 == "student" {s += $3} END {print s + 0}' "$FT_CSV"
