#!/bin/sh
# Cross-OS requirement checker, installer, and symlink updater for Magrathea.
set -eu

KIT_ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)"
LOCAL_BIN="${HOME}/.local/bin"
CHECK_ONLY=0
AUTO_YES=0
MISSING_PKGS=""
NEED_PY310=0
NORM_BROKEN=0
STALE_LINKS=0
NEEDS_PATH=0
HAS_SUDO=""

detect_pm() {
    if command -v apt-get >/dev/null 2>&1; then
        printf 'apt-get\n'
    elif command -v dnf >/dev/null 2>&1; then
        printf 'dnf\n'
    elif command -v yum >/dev/null 2>&1; then
        printf 'yum\n'
    elif command -v pacman >/dev/null 2>&1; then
        printf 'pacman\n'
    elif command -v zypper >/dev/null 2>&1; then
        printf 'zypper\n'
    elif command -v xbps-install >/dev/null 2>&1; then
        printf 'xbps-install\n'
    elif command -v apk >/dev/null 2>&1; then
        printf 'apk\n'
    elif command -v brew >/dev/null 2>&1; then
        printf 'brew\n'
    else
        printf 'unknown\n'
    fi
}

find_py310() {
    for b in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
        cand="$(command -v "${b}" 2>/dev/null || true)"
        [ -n "${cand}" ] || continue
        chk='import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
        if "${cand}" -c "${chk}" >/dev/null 2>&1; then
            printf '%s\n' "${cand}"
            return 0
        fi
    done
    if command -v uv >/dev/null 2>&1; then
        uv_py="$(uv python find '>=3.10' 2>/dev/null || true)"
        if [ -n "${uv_py}" ] && [ -x "${uv_py}" ]; then
            printf '%s\n' "${uv_py}"
            return 0
        fi
    fi
    return 1
}

run_pm_install() {
    pm="${1}"
    sudo_pfx="${2}"
    pkgs="${3}"
    case "${pm}" in
        apt-get)
            run_words "${sudo_pfx}" apt-get update ""
            pm_args="install -y ${pkgs}"
            ;;
        dnf | yum | zypper) pm_args="install -y ${pkgs}" ;;
        pacman) pm_args="-Sy --noconfirm ${pkgs}" ;;
        xbps-install) pm_args="-Sy ${pkgs}" ;;
        apk) pm_args="add ${pkgs}" ;;
        brew)
            pm_args="install ${pkgs}"
            sudo_pfx=""
            ;;
        *)
            printf '[WARN] Unknown PM; install manually: %s\n' "${pkgs}"
            return 1
            ;;
    esac
    run_words "${sudo_pfx}" "${pm}" "${pm_args}"
}

run_words() {
    sudo_pfx="${1}"
    bin_cmd="${2}"
    words="${3}"
    set --
    while [ -n "${words}" ]; do
        w="${words%% *}"
        [ "${w}" = "${words}" ] && words="" || words="${words#* }"
        [ -n "${w}" ] && set -- "$@" "${w}"
    done
    if [ -n "${sudo_pfx}" ]; then
        "${sudo_pfx}" "${bin_cmd}" "$@"
    else
        "${bin_cmd}" "$@"
    fi
}

sync_links() {
    check_mode="${1}"
    count=0
    tools="moulinette deepthought examshell norminette shnorm ft_lock bc"
    tools="${tools} ifconfig pforge audit_testers"
    [ "${check_mode}" -eq 0 ] && mkdir -p "${LOCAL_BIN}"
    while [ -n "${tools}" ]; do
        t="${tools%% *}"
        [ "${t}" = "${tools}" ] && tools="" || tools="${tools#* }"
        src="${KIT_ROOT}/bin/${t}"
        dst="${LOCAL_BIN}/${t}"
        [ -e "${src}" ] || continue
        cur="$(readlink -f "${dst}" 2>/dev/null || true)"
        want="$(readlink -f "${src}" 2>/dev/null || printf '%s' "${src}")"
        if [ -L "${dst}" ] && [ "${cur}" = "${want}" ] && [ -x "${dst}" ]; then
            continue
        fi
        if [ "${check_mode}" -eq 1 ]; then
            printf '[STALE/MISSING] %s -> %s\n' "${dst}" "${src}" >&2
            count=$((count + 1))
        else
            ln -sf "${src}" "${dst}"
            printf '[LINKED] %s -> %s\n' "${dst}" "${src}" >&2
        fi
    done
    printf '%s\n' "${count}"
}

for arg in "$@"; do
    case "${arg}" in
        --check | -c) CHECK_ONLY=1 ;;
        --yes | -y) AUTO_YES=1 ;;
        --help | -h)
            printf 'Usage: ./install.sh [--check] [--yes]\n'
            printf '  --check, -c   Audit requirements and symlinks only\n'
            printf '  --yes,   -y   Install missing packages and update links\n'
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "${arg}" >&2
            exit 2
            ;;
    esac
done

PM="$(detect_pm)"
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && HAS_SUDO="sudo"
printf '===> Magrathea setup check (package manager: %s)\n' "${PM}"

if command -v cc >/dev/null 2>&1 || command -v gcc >/dev/null 2>&1; then
    printf '[OK] C compiler\n'
else
    MISSING_PKGS="${MISSING_PKGS} gcc"
    [ "${PM}" = "apk" ] && MISSING_PKGS="${MISSING_PKGS} musl-dev"
    printf '[MISSING] C compiler (cc / gcc)\n'
fi

for TOOL in make bc git diff tar; do
    PKG="${TOOL}"
    [ "${TOOL}" = "diff" ] && PKG="diffutils"
    if command -v "${TOOL}" >/dev/null 2>&1; then
        printf '[OK] %s\n' "${TOOL}"
    else
        MISSING_PKGS="${MISSING_PKGS} ${PKG}"
        printf '[MISSING] %s\n' "${TOOL}"
    fi
done

if PY3="$(find_py310)"; then
    VER="$("${PY3}" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    printf '[OK] python3 %s (%s)\n' "${VER}" "${PY3}"
    NORM_OUT="$("${KIT_ROOT}/bin/norminette" --version 2>/dev/null || true)"
    if [ -n "${NORM_OUT}" ]; then
        printf '[OK] %s\n' "${NORM_OUT}"
    else
        NORM_BROKEN=1
        printf '[MISSING] official norminette failed\n'
    fi
else
    NEED_PY310=1
    printf '[MISSING] python3 >= 3.10 (needed by official norminette)\n'
fi

STALE_LINKS="$(sync_links "${CHECK_ONLY}")"
[ "${CHECK_ONLY}" -eq 1 ] && [ "${STALE_LINKS}" -eq 0 ] &&
    printf '[OK] %s symlinks point to this repo\n' "${LOCAL_BIN}"

case ":${PATH:-}:" in
    *":${LOCAL_BIN}:"*)
        printf '[OK] %s is in PATH\n' "${LOCAL_BIN}"
        ;;
    *)
        NEEDS_PATH=1
        printf '[WARN] %s is not in PATH\n' "${LOCAL_BIN}"
        if [ "${CHECK_ONLY}" -eq 0 ]; then
            RC="${HOME}/.profile"
            C1="${HOME}/.zshrc"
            C2="${HOME}/.bashrc"
            C3="${HOME}/.profile"
            for CAND in "${C1}" "${C2}" "${C3}"; do
                [ -f "${CAND}" ] && RC="${CAND}" && break
            done
            LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""
            if ! grep -F '.local/bin' "${RC}" >/dev/null 2>&1; then
                printf '\n%s\n' "${LINE}" >>"${RC}"
                printf '[UPDATED] Added %s to %s\n' "${LOCAL_BIN}" "${RC}"
            fi
        fi
        ;;
esac

if [ "${NEED_PY310}" -eq 1 ]; then
    PY_PKG="python3"
    [ "${PM}" = "pacman" ] && PY_PKG="python"
    [ "${PM}" = "brew" ] && PY_PKG="python@3.12"
    MISSING_PKGS="${MISSING_PKGS} ${PY_PKG}"
fi
MISSING_PKGS="${MISSING_PKGS# }"

if [ "${CHECK_ONLY}" -eq 1 ]; then
    FAIL_CHK=0
    [ -n "${MISSING_PKGS}" ] && FAIL_CHK=1
    [ "${NORM_BROKEN}" -eq 1 ] && FAIL_CHK=1
    [ "${STALE_LINKS}" -gt 0 ] && FAIL_CHK=1
    [ "${NEEDS_PATH}" -eq 1 ] && FAIL_CHK=1
    if [ "${FAIL_CHK}" -eq 1 ]; then
        if [ -n "${MISSING_PKGS}" ]; then
            SFX=""
            [ -n "${HAS_SUDO}" ] && [ "${PM}" != "brew" ] && SFX="sudo "
            printf 'Missing packages: %s\n' "${MISSING_PKGS}"
            [ "${PM}" = "apt-get" ] &&
                printf '  %sapt-get update && %sapt-get install -y %s\n' \
                    "${SFX}" "${SFX}" "${MISSING_PKGS}"
            [ "${PM}" = "xbps-install" ] &&
                printf '  %sxbps-install -S %s\n' "${SFX}" "${MISSING_PKGS}"
            [ "${PM}" = "dnf" ] &&
                printf '  %sdnf install -y %s\n' "${SFX}" "${MISSING_PKGS}"
            [ "${PM}" = "zypper" ] &&
                printf '  %szypper install -y %s\n' "${SFX}" "${MISSING_PKGS}"
            [ "${PM}" = "pacman" ] &&
                printf '  %spacman -S %s\n' "${SFX}" "${MISSING_PKGS}"
            [ "${PM}" = "apk" ] &&
                printf '  %sapk add %s\n' "${SFX}" "${MISSING_PKGS}"
            [ "${PM}" = "brew" ] &&
                printf '  brew install %s\n' "${MISSING_PKGS}"
        fi
        if [ "${STALE_LINKS}" -gt 0 ]; then
            printf 'Update links: ./install.sh --yes\n'
        fi
        exit 1
    fi
    printf '[OK] Environment is ready.\n'
    exit 0
fi

if [ -n "${MISSING_PKGS}" ]; then
    DO_INST=0
    if [ "${AUTO_YES}" -eq 1 ]; then
        DO_INST=1
    else
        printf 'Install (%s) via %s? [y/N] ' "${MISSING_PKGS}" "${PM}"
        if read -r ANS; then
            case "${ANS}" in
                y | Y | yes | YES) DO_INST=1 ;;
                *) DO_INST=0 ;;
            esac
        fi
    fi
    if [ "${DO_INST}" -eq 1 ]; then
        if [ "${NEED_PY310}" -eq 1 ] && command -v uv >/dev/null 2>&1; then
            uv python install 3.12
            UV_PY="$(uv python find '>=3.10' 2>/dev/null || true)"
            if [ -n "${UV_PY}" ]; then
                mkdir -p "${LOCAL_BIN}"
                ln -sf "${UV_PY}" "${LOCAL_BIN}/python3"
                NEED_PY310=0
            fi
        fi
        [ -n "${MISSING_PKGS}" ] && run_pm_install "${PM}" "${HAS_SUDO}" \
            "${MISSING_PKGS}" || true
    fi
fi

if command -v cc >/dev/null 2>&1 || command -v gcc >/dev/null 2>&1; then
    if find_py310 >/dev/null 2>&1 && command -v bc >/dev/null 2>&1; then
        printf '[OK] Magrathea installation and symlinks updated.\n'
        exit 0
    fi
fi
printf '[WARN] Some requirements remain missing; inspect [MISSING] lines.\n'
exit 1
