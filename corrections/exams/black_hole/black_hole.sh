#!/bin/sh
set -eu
ls /nonexistent_black_hole_path 2>/dev/null || true
printf 'OK
'
