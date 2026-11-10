#!/bin/sh
set -eu

full_ver="${1:-5.15.0-76-generic}"
flavour_abi="${full_ver#*-}"
flavour="${flavour_abi#*-}"
version="${full_ver%-$flavour}"
major="${full_ver%%.*}"

printf 'KERNEL=%s MAJOR=%s VER=%s ABI_FLAV=%s FLAV=%s\n' \
    "$full_ver" "$major" "$version" "$flavour_abi" "$flavour"
