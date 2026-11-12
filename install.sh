#!/bin/sh
# **************************************************************************** #
#                                                                              #
#    install.sh — 42 / 1337 ExamShell & Moulinette Pro Edition Installer       #
#                                                                              #
# **************************************************************************** #

set -eu

REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOCAL_BIN="${HOME}/.local/bin"

DIV="========================================================================"

printf "\033[1;36m%s\033[0m\n" "$DIV"
printf "\033[1;32m  42 / 1337 EXAMSHELL & MOULINETTE INSTALLER\033[0m\n"
printf "\033[1;36m%s\033[0m\n\n" "$DIV"

# 1. Check required system tools
printf "\033[1;34m[1/4] Checking system dependencies...\033[0m\n"
MISSING=0
for tool in python3 cc git make tar diff; do
    if command -v "$tool" >/dev/null 2>&1; then
        T_PATH="$(command -v "$tool")"
        printf "  \033[1;32m[OK]\033[0m %-10s -> %s\n" "$tool" "$T_PATH"
    else
        printf "  \033[1;31m[MISSING]\033[0m %-10s\n" "$tool"
        MISSING=1
    fi
done

if [ "$MISSING" -ne 0 ]; then
    printf "\n\033[1;33mWarning: Some system tools are missing.\033[0m\n"
fi

# The official 42 norminette ships in third_party/norminette: nothing to download or build.
# It needs Python 3.10+; on an older Python the line below names the built-in fallback.
NORM_IN_USE="$(python3 "${REPO_DIR}/bin/norminette" --version 2>/dev/null | head -n 1 || true)"
printf "  \033[1;32m[OK]\033[0m %-10s -> %s\n" "norminette" "${NORM_IN_USE:-python3 not found}"

# 2. Ensure executable permissions on all CLI tools
printf "\n\033[1;34m[2/4] Setting tool permissions...\033[0m\n"
chmod +x "${REPO_DIR}/examshell" "${REPO_DIR}/moulinette"
chmod +x "${REPO_DIR}/bin/"* "${REPO_DIR}/bocal/"*.sh 2>/dev/null || true
printf "  \033[1;32m[OK]\033[0m Enabled +x permissions on CLI tools\n"

# 3. Create symlinks in ~/.local/bin so user can run commands from anywhere
printf "\n\033[1;34m[3/4] Installing command symlinks into %s ...\033[0m\n" \
    "$LOCAL_BIN"
mkdir -p "$LOCAL_BIN"
for cmd in examshell moulinette norminette shnorm pforge deepthought; do
    ln -sf "${REPO_DIR}/bin/${cmd}" "${LOCAL_BIN}/${cmd}"
    printf "  \033[1;32m[OK]\033[0m Linked %-12s -> ~/.local/bin/%s\n" \
        "$cmd" "$cmd"
done

# 4. Check if ~/.local/bin is in PATH
printf "\n\033[1;34m[4/4] Verifying PATH configuration...\033[0m\n"
case ":${PATH}:" in
    *":${LOCAL_BIN}:"*)
        printf "  \033[1;32m[OK]\033[0m %s is already in your PATH!\n" \
            "$LOCAL_BIN"
        ;;
    *)
        printf "  \033[1;33m[TIP]\033[0m Add this line to ~/.bashrc:\n"
        printf "        export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
        ;;
esac

printf "\n\033[1;36m%s\033[0m\n" "$DIV"
printf "\033[1;32m  INSTALLATION COMPLETE! QUICK START:\033[0m\n"
printf "  ./examshell              # Start an interactive exam session\n"
printf "  ./moulinette             # Interactive curriculum navigator\n"
printf "  ./moulinette piscine     # List all 17 C Piscine modules\n"
printf "\033[1;36m%s\033[0m\n" "$DIV"
