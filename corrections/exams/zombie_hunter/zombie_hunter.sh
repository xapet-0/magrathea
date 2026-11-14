#!/bin/sh
awk '$1 == "Z" { print $2; found = 1 } END { if (!found) print 0 }'
