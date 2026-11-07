#!/bin/sh
# **************************************************************************** #
#                                                                              #
#   auto_correc_main.sh — Differential C Grader (KhalfaouiDriss/grademe-42)    #
#   Compiles reference solution vs student submission and diffs outputs.       #
#                                                                              #
# **************************************************************************** #

set -eu

if [ "$#" -lt 2 ]; then
    printf "Usage: %s <student.c> <reference.c> [main.c] [args...]\n" "$0" >&2
    exit 1
fi

STUDENT_SRC="$1"
REF_SRC="$2"
shift 2

MAIN_SRC=""
if [ "$#" -ge 1 ] && [ -f "$1" ]; then
    MAIN_SRC="$1"
    shift 1
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dt_autocorrec.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

SOURCEXAM="$TMP_DIR/sourcexam"
FINALEXAM="$TMP_DIR/finalexam"
REF_OUT="$TMP_DIR/ref.output"
USR_OUT="$TMP_DIR/user.output"
COMPILER_ERR="$TMP_DIR/compiler.err"
TIMEOUT_SEC="${DT_TIMEOUT:-3}"

HEADER_DIV="= Differential Grader (sourcexam vs finalexam) ================="
printf "\033[36;1m%s\033[0m\n" "$HEADER_DIV"

# 1. Compile Reference Binary (sourcexam)
COMPILE_REF_OK=1
if [ -n "$MAIN_SRC" ]; then
    cc -Wall -Wextra -Werror -fno-builtin "$REF_SRC" "$MAIN_SRC" \
        -o "$SOURCEXAM" -lm 2>"$COMPILER_ERR" || COMPILE_REF_OK=0
else
    cc -Wall -Wextra -Werror -fno-builtin "$REF_SRC" \
        -o "$SOURCEXAM" -lm 2>"$COMPILER_ERR" || COMPILE_REF_OK=0
fi
if [ "$COMPILE_REF_OK" -eq 0 ]; then
    printf "\033[31;1m[INTERNAL ERROR]: Reference failed to compile:\033[0m\n"
    cat "$COMPILER_ERR"
    exit 2
fi

# 2. Compile Student Binary (finalexam)
BASE_STUDENT="$(basename "$STUDENT_SRC")"
BASE_MAIN=""
if [ -n "$MAIN_SRC" ]; then
    BASE_MAIN="$(basename "$MAIN_SRC")"
fi
printf "$> cc -Wall -Wextra -Werror %s %s -o finalexam\n" \
    "$BASE_STUDENT" "$BASE_MAIN"

COMPILE_STUDENT_OK=1
if [ -n "$MAIN_SRC" ]; then
    cc -Wall -Wextra -Werror -fno-builtin "$STUDENT_SRC" "$MAIN_SRC" \
        -o "$FINALEXAM" -lm 2>"$COMPILER_ERR" || COMPILE_STUDENT_OK=0
else
    cc -Wall -Wextra -Werror -fno-builtin "$STUDENT_SRC" \
        -o "$FINALEXAM" -lm 2>"$COMPILER_ERR" || COMPILE_STUDENT_OK=0
fi
if [ "$COMPILE_STUDENT_OK" -eq 0 ]; then
    cat "$COMPILER_ERR"
    printf "\n\033[31;1mDoes not compile\033[0m\nGrade: 0\n"
    exit 1
fi

# 3. Execute Reference Binary
"$SOURCEXAM" "$@" >"$REF_OUT" 2>/dev/null

# 4. Execute Student Binary with Watchdog Timer
"$FINALEXAM" "$@" >"$USR_OUT" 2>/dev/null &
PID="$!"
(
    sleep "$TIMEOUT_SEC"
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null
    fi
) &
WATCHDOG_PID="$!"
RET=0
wait "$PID" 2>/dev/null || RET="$?"
kill -9 "$WATCHDOG_PID" 2>/dev/null || true

if [ "$RET" -eq 137 ] || [ "$RET" -eq 142 ]; then
    printf "\033[33;1mTimeout (elapsed > %ss)\033[0m\nGrade: 0\n" \
        "$TIMEOUT_SEC"
    exit 1
elif [ "$RET" -gt 128 ]; then
    SIG=$((RET - 128))
    printf "\033[31;1mSignal -%d (Crash / Segfault)\033[0m\nGrade: 0\n" \
        "$SIG"
    exit 1
fi

# 5. Compare Outputs with diff -U 3
printf "$> diff -U 3 user.output ref.output | cat -e\n"
if diff -U 3 "$USR_OUT" "$REF_OUT" >"$TMP_DIR/diff.txt"; then
    printf "\n\033[32;1mDiff OK :D\033[0m\n= Final grade: 100 =============\n"
    exit 0
else
    cat "$TMP_DIR/diff.txt"
    printf "\n\033[31;1mDiff KO :(\033[0m\n= Final grade: 0 ===============\n"
    exit 1
fi
