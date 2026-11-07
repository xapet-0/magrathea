#!/bin/sh
grep -v '^$' | tr 'A-Z' 'a-z' | sort -u
