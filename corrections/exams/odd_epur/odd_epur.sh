#!/bin/sh
awk 'NR % 2 == 1 {$1=$1; print}'
