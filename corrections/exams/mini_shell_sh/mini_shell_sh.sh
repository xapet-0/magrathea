#!/bin/sh
while IFS= read -r line; do
  [ "$line" = "exit" ] && break
  eval "$line"
done
