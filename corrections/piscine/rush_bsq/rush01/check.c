/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   check.c                                            :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

static int	cnt_vis(int a, int b, int c, int d)
{
	int	v;
	int	m;

	v = 1;
	m = a;
	if (b > m && ++v)
		m = b;
	if (c > m && ++v)
		m = c;
	if (d > m)
		v++;
	return (v);
}

static int	check_col(int g[4][4], int *clues, int c)
{
	int	r;

	r = 0;
	while (r < 4)
	{
		if (g[r][c] == 0)
			return (1);
		r++;
	}
	if (cnt_vis(g[0][c], g[1][c], g[2][c], g[3][c]) != clues[c])
		return (0);
	if (cnt_vis(g[3][c], g[2][c], g[1][c], g[0][c]) != clues[4 + c])
		return (0);
	return (1);
}

static int	check_row(int g[4][4], int *clues, int r)
{
	int	c;

	c = 0;
	while (c < 4)
	{
		if (g[r][c] == 0)
			return (1);
		c++;
	}
	if (cnt_vis(g[r][0], g[r][1], g[r][2], g[r][3]) != clues[8 + r])
		return (0);
	if (cnt_vis(g[r][3], g[r][2], g[r][1], g[r][0]) != clues[12 + r])
		return (0);
	return (1);
}

int	is_valid_move(int g[4][4], int *clues, int pos, int val)
{
	int	r;
	int	c;
	int	i;

	r = pos / 4;
	c = pos % 4;
	i = 0;
	while (i < 4)
	{
		if (g[r][i] == val || g[i][c] == val)
			return (0);
		i++;
	}
	g[r][c] = val;
	if (!check_row(g, clues, r) || !check_col(g, clues, c))
	{
		g[r][c] = 0;
		return (0);
	}
	return (1);
}
