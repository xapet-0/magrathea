#!/bin/sh
set -eu
git log -n 5 --format="%h %an"
