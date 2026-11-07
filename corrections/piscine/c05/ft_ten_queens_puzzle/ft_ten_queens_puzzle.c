/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_ten_queens_puzzle.c                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static int	is_safe(int *pos, int col, int r)
{
	int	i;

	i = 0;
	while (i < col)
	{
		if (pos[i] == r || pos[i] - r == col - i || r - pos[i] == col - i)
			return (0);
		i++;
	}
	return (1);
}

static void	print_sol(int *pos, int *cnt)
{
	char	buf[11];
	int		i;

	i = 0;
	while (i < 10)
	{
		buf[i] = '0' + pos[i];
		i++;
	}
	buf[10] = '\n';
	write(1, buf, 11);
	(*cnt)++;
}

static void	solve_q(int col, int *pos, int *cnt)
{
	int	r;

	if (col == 10)
	{
		print_sol(pos, cnt);
		return ;
	}
	r = 0;
	while (r < 10)
	{
		if (is_safe(pos, col, r))
		{
			pos[col] = r;
			solve_q(col + 1, pos, cnt);
		}
		r++;
	}
}

int	ft_ten_queens_puzzle(void)
{
	int	pos[10];
	int	cnt;

	cnt = 0;
	solve_q(0, pos, &cnt);
	return (cnt);
}
