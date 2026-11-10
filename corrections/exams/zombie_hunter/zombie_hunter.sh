#!/bin/sh
awk '$1 == "Z" {print $2}'
