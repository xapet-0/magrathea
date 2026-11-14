/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   solve.c                                            :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "bsq.h"

static int	min3(int a, int b, int c)
{
	int	m;

	m = a;
	if (b < m)
		m = b;
	if (c < m)
		m = c;
	return (m);
}

static void	fill_best(t_map *m, int best_sz, int best_r, int best_c)
{
	int	r;
	int	c;

	r = best_r - best_sz + 1;
	while (r <= best_r)
	{
		c = best_c - best_sz + 1;
		while (c <= best_c)
		{
			m->grid[r * (m->cols + 1) + c] = m->full;
			c++;
		}
		r++;
	}
}

static void	dp_step(t_map *m, int *dp, int pos, int *best)
{
	int	r;
	int	c;

	r = pos / m->cols;
	c = pos % m->cols;
	if (m->grid[r * (m->cols + 1) + c] == m->oider)
		dp[pos] = 0;
	else if (r == 0 || c == 0)
		dp[pos] = 1;
	else
		dp[pos] = 1 + min3(dp[(r - 1) * m->cols + c],
				dp[r * m->cols + c - 1], dp[(r - 1) * m->cols + c - 1]);
	if (dp[pos] > best[0])
	{
		best[0] = dp[pos];
		best[1] = r;
		best[2] = c;
	}
}

static int	valid_grid(t_map *m)
{
	int	r;
	int	c;
	int	idx;

	if (m->rows <= 0 || m->cols <= 0)
		return (0);
	r = 0;
	while (r < m->rows)
	{
		c = 0;
		while (c < m->cols)
		{
			idx = r * (m->cols + 1) + c;
			if (m->grid[idx] != m->empty && m->grid[idx] != m->oider)
				return (0);
			c++;
		}
		if (m->grid[r * (m->cols + 1) + m->cols] != '\n')
			return (0);
		r++;
	}
	return (m->grid[m->rows * (m->cols + 1)] == '\0');
}

void	solve_and_print(t_map *m)
{
	int	*dp;
	int	best[3];
	int	i;

	if (!valid_grid(m))
	{
		write(2, "map error\n", 10);
		return ;
	}
	dp = (int *)malloc(sizeof(int) * m->rows * m->cols);
	if (!dp)
		return ;
	best[0] = 0;
	best[1] = 0;
	best[2] = 0;
	i = 0;
	while (i < m->rows * m->cols)
	{
		dp_step(m, dp, i, best);
		i++;
	}
	if (best[0] > 0)
		fill_best(m, best[0], best[1], best[2]);
	write(1, m->grid, m->rows * (m->cols + 1));
	free(dp);
}
