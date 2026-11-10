#!/bin/sh
cd -P -- "$1" 2>/dev/null && pwd -P || exit 1

