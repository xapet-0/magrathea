#!/bin/sh
# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    seat_hostname_sync.sh                              :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: marvin <marvin@1337.ma>                    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/10/14 12:00:00 by marvin            #+#    #+#              #
#    Updated: 2026/10/14 12:00:00 by marvin           ###   ########.fr        #
#                                                                              #
# **************************************************************************** #
set -eu
IFS="$(printf '\n\t')"

seat_name="${1:-c1r1p1}"
banner_file="${2:-/tmp/01-banner-message}"

current_banner=""
if [ -f "${banner_file}" ]; then
    current_banner="$(grep 'banner-message-text=' "${banner_file}" \
        | cut -d "'" -f 2 || true)"
fi

if [ "${current_banner}" != "${seat_name}" ]; then
    printf '[org/gnome/login-screen]\nbanner-message-enable=true\n' \
        > "${banner_file}"
    printf "banner-message-text='%s'\n" "${seat_name}" >> "${banner_file}"
    printf 'BANNER_UPDATED=%s\n' "${seat_name}"
else
    printf 'BANNER_UNCHANGED=%s\n' "${seat_name}"
fi
