#!/bin/sh
# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    compare_subjects.sh                                :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: 1337/42 Bocal Systems Suite                +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/10/20 01:10:00 by bocal             #+#    #+#              #
#    Updated: 2026/11/09 00:48:00 by bocal            ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

set -eu
IFS="$(printf '\n\t')"

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd -P)"
KIT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
export MAGRATHEA_ROOT="${KIT_ROOT}"
export PYTHONPATH="${KIT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m deepthought.subject_comparer "$@"
