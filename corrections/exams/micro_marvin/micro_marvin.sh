#!/bin/sh
case "$1" in
	len) printf "%s" "$2" | wc -c | tr -d " " ;;
	rev) printf "%s\n" "$2" | rev ;;
	up) printf "%s\n" "$2" | tr "a-z" "A-Z" ;;
	*) echo "KO" ; exit 1 ;;
esac

