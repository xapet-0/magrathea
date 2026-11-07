#!/bin/sh
# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    unminimize_man_restore.sh                          :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: marvin <marvin@1337.ma>                    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/10/14 12:00:00 by marvin            #+#    #+#              #
#    Updated: 2026/10/14 12:00:00 by marvin           ###   ########.fr        #
#                                                                              #
# **************************************************************************** #
set -eu
IFS="$(printf '\n\t')"

root_dir="${1:-/}"
excludes_cfg="${root_dir}/etc/dpkg/dpkg.cfg.d/excludes"
man_bin="${root_dir}/usr/bin/man"
man_real="${root_dir}/usr/bin/man.REAL"

if [ -f "${excludes_cfg}" ]; then
    mv -- "${excludes_cfg}" "${excludes_cfg}.dpkg-tmp"
fi

if [ -f "${man_real}" ]; then
    rm -f -- "${man_bin}"
    mv -- "${man_real}" "${man_bin}"
    printf 'MAN_RESTORED=%s\n' "${man_bin}"
else
    printf 'MAN_STATUS=OK\n'
fi
