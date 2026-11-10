#!/bin/sh
sort | uniq -c | awk '{print $1, $2}' | sort -k1,1nr -k2,2
