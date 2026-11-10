#!/bin/sh
set -eu
mkdir -p box
chmod 0750 box
rm -f box/key shortcut
dd if=/dev/zero of=box/key bs=1 count=42 2>/dev/null
chmod 0440 box/key
ln -s box/key shortcut
